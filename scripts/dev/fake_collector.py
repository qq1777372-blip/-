"""Stand-in for the 生意参谋 collector program, for local debugging.

The real collector is a separate Windows program that drives a logged-in 生意参谋
browser session; it is not in this repo. Without it the 工作台's 「同步数据」 button
queues a request that nobody ever claims, so the whole sync path is undebuggable
locally.

This script speaks the same three endpoints the real collector does:

    POST /api/sycm/sync-requests/claim          take the queued request
    POST /api/sycm/upload                       one call per shop
    POST /api/sycm/sync-requests/{id}/complete  report per-shop results

It fabricates the metrics instead of scraping, reusing the generators in
seed_dev_data.py so the payload shape stays defined in exactly one place.

Usage (needs the same token the backend runs with):

    python scripts/dev/fake_collector.py --watch     poll forever
    python scripts/dev/fake_collector.py             drain once and exit
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from seed_dev_data import sycm_overview, sycm_source_tree  # noqa: E402

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_DEVICE_ID = "dev-device-a"
DEFAULT_DEVICE_NAME = "本地假采集端"


def discover_shops(db_path: Path) -> list[tuple[str, str]]:
    """(account_id, shop_name) pairs the dev database knows about.

    Read from the seeded snapshots rather than hardcoded here: the seed owns
    which shops exist, including the main/sub account pair that has to fold
    together.
    """
    if not db_path.is_file():
        return []
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT DISTINCT shop_id, shop_name FROM sycm_snapshots ORDER BY shop_id"
        ).fetchall()
        aliases = connection.execute(
            "SELECT account_id, shop_name FROM sycm_shop_aliases"
        ).fetchall()
    finally:
        connection.close()

    shops = {str(row["shop_id"]): str(row["shop_name"]) for row in rows}
    # Sub-accounts only live in the alias table, but the collector sees them as
    # separate logins, so it must offer them at claim time too.
    for alias in aliases:
        shops.setdefault(str(alias["account_id"]), str(alias["shop_name"]))
    return sorted(shops.items())


def build_snapshot(
    rng: random.Random,
    shop_id: str,
    shop_name: str,
    device_id: str,
    period: str,
    day: datetime,
) -> dict[str, object]:
    uv = float(rng.randint(600, 4200))
    pv = round(uv * rng.uniform(1.6, 3.4), 2)
    cart = float(rng.randint(20, 190))
    buyers = float(rng.randint(8, 120))
    pay_amt = round(buyers * rng.uniform(45, 420), 2)
    return {
        "shopId": shop_id,
        "shopName": shop_name,
        "deviceId": device_id,
        # UNIQUE(shop_id, collected_at) upserts, so a distinct stamp per row is
        # what makes repeated runs add history instead of overwriting one row.
        "collectedAt": day.isoformat(timespec="seconds"),
        "period": period,
        "dateStart": day.date().isoformat(),
        "dateEnd": day.date().isoformat(),
        "overview": json.loads(sycm_overview(rng, uv, pv, cart, buyers, pay_amt)),
        "sourceTree": json.loads(sycm_source_tree(rng, uv, buyers, pay_amt)),
    }


class Collector:
    def __init__(self, base_url: str, token: str, device_id: str, device_name: str, db_path: Path):
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id
        self.device_name = device_name
        self.db_path = db_path
        self.client = httpx.Client(timeout=20.0, headers={"X-Sycm-Upload-Token": token})
        self.rng = random.Random()

    def close(self) -> None:
        self.client.close()

    def claim(self, shop_ids: list[str]) -> dict[str, object] | None:
        response = self.client.post(
            f"{self.base_url}/api/sycm/sync-requests/claim",
            json={
                "deviceId": self.device_id,
                "deviceName": self.device_name,
                "shopIds": shop_ids,
            },
        )
        if response.status_code == 503:
            raise SystemExit(
                "backend rejected the claim: SYCM_UPLOAD_TOKEN is not configured on it.\n"
                "Start the backend with the same token this script uses "
                "(scripts/dev/start_all.py does that for you)."
            )
        response.raise_for_status()
        payload = response.json()
        # null means either nothing queued, or every shop belongs to another
        # device that is still alive -- both are normal, not errors.
        return payload if isinstance(payload, dict) else None

    def upload(self, snapshot: dict[str, object]) -> tuple[bool, str]:
        response = self.client.post(f"{self.base_url}/api/sycm/upload", json=snapshot)
        if response.status_code >= 400:
            try:
                detail = str(response.json().get("detail", ""))
            except ValueError:
                detail = response.text[:200]
            return False, f"HTTP {response.status_code} {detail}"
        return True, ""

    def complete(self, request_id: int, results: list[dict[str, object]], error: str) -> None:
        response = self.client.post(
            f"{self.base_url}/api/sycm/sync-requests/{request_id}/complete",
            json={
                "success": not error,
                "error": error,
                "results": results,
            },
        )
        response.raise_for_status()

    def run_once(self, history_days: int) -> bool:
        """Claim one request and fulfil it. False when there was nothing to do."""
        shops = discover_shops(self.db_path)
        if not shops:
            raise SystemExit(
                f"no shops found in {self.db_path}.\n"
                "Run: python scripts/seed_dev_data.py --force"
            )
        names = dict(shops)
        task = self.claim([shop_id for shop_id, _ in shops])
        if task is None:
            return False

        request_id = int(task["id"])
        allowed = [str(value) for value in (task.get("allowedShopIds") or [])]
        canonical = {str(value) for value in (task.get("canonicalShopIds") or [])}
        # Upload once per canonical shop: sub-account IDs resolve to the same row
        # server-side, so sending both just overwrites the same snapshot.
        targets = [shop_id for shop_id in allowed if shop_id in canonical] or allowed
        print(f"claimed request #{request_id} -> {len(targets)} shop(s)")

        results: list[dict[str, object]] = []
        failures: list[str] = []
        now = datetime.now()
        for shop_id in targets:
            shop_name = names.get(shop_id, shop_id)
            ok_all = True
            last_error = ""
            # today plus a run of yesterday rows: 近7天/近30天 are aggregated from
            # period='yesterday' server-side, so they stay empty without these.
            plan = [("today", now)]
            plan += [
                ("yesterday", now - timedelta(days=offset))
                for offset in range(1, history_days + 1)
            ]
            for period, day in plan:
                snapshot = build_snapshot(
                    self.rng, shop_id, shop_name, self.device_id, period, day
                )
                ok, error = self.upload(snapshot)
                if not ok:
                    ok_all = False
                    last_error = error
                    break
            results.append({"shopId": shop_id, "shopName": shop_name, "success": ok_all})
            status = "ok" if ok_all else f"FAILED {last_error}"
            print(f"  {shop_id} {shop_name} ... {status}")
            if not ok_all:
                failures.append(f"{shop_name}: {last_error}")

        self.complete(request_id, results, "; ".join(failures)[:500])
        print(f"request #{request_id} -> {'completed' if not failures else 'failed'}")
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--token", default="")
    parser.add_argument("--device-id", default=DEFAULT_DEVICE_ID)
    parser.add_argument("--device-name", default=DEFAULT_DEVICE_NAME)
    parser.add_argument("--sycm-db", default=str(PROJECT_ROOT / "dev_sycm.db"))
    parser.add_argument(
        "--history-days",
        type=int,
        default=7,
        help="how many 'yesterday' rows to upload per shop (feeds 近7天/近30天)",
    )
    parser.add_argument("--watch", action="store_true", help="keep polling instead of exiting")
    parser.add_argument("--interval", type=float, default=3.0)
    args = parser.parse_args()

    import os

    token = args.token or os.getenv("SYCM_UPLOAD_TOKEN", "").strip()
    if not token:
        print(
            "no token: pass --token or set SYCM_UPLOAD_TOKEN to the value the backend uses.",
            file=sys.stderr,
        )
        return 2

    collector = Collector(
        args.base_url, token, args.device_id, args.device_name, Path(args.sycm_db)
    )
    try:
        if not args.watch:
            if not collector.run_once(args.history_days):
                print("nothing queued. Click 同步数据 in the 工作台 first, or use --watch.")
            return 0

        print(f"watching {args.base_url} as {args.device_id} (ctrl-c to stop)")
        while True:
            try:
                if not collector.run_once(args.history_days):
                    time.sleep(args.interval)
            except httpx.HTTPError as exc:
                print(f"backend unreachable: {exc}", file=sys.stderr)
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nstopped")
        return 0
    finally:
        collector.close()


if __name__ == "__main__":
    raise SystemExit(main())
