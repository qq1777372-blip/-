"""Stand in for the license server during local development.

In production the backend reaches this service over an SSH tunnel to the legacy
Aliyun box (`fastapiproject-old-server-tunnel.service`), so nothing answers on
127.0.0.1 locally and every 卡密 page fails with 502 "License server is
unavailable". This serves the seven paths main.py calls, with the response
envelope its callers expect:

  GET  /api/admin/stats                          -> {"stats": {...}}
  GET  /api/admin/licenses                       -> {"items": [...]}
  POST /api/admin/licenses/create                -> {"items": [...]}
  POST /api/admin/licenses/{key}/status          -> {"item": {...}}
  POST /api/admin/licenses/{key}/unbind          -> {"item": {...}}
  POST /api/license/validate                     -> {"license": {...}}
  POST /api/license/activate                     -> {"license": {...}}

Admin paths require the X-Admin-Token header to match LICENSE_ADMIN_TOKEN, the
same check the real server does -- main.py turns a 401 into a 502, so getting
this wrong looks like an outage rather than a bad token.

Note main.py treats a body of {"status": "error"} as a failure regardless of the
HTTP code, so success payloads here never use that value.

Run:
  python scripts/dev/license_server_stub.py --port 15000
"""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

SHANGHAI = timezone(timedelta(hours=8))

STATE_LOCK = threading.Lock()
# license_key -> record. Seeded so the 卡密 list is not empty on first load.
LICENSES: dict[str, dict[str, Any]] = {}


def now_iso() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def make_license(
    key: str,
    *,
    plan_name: str,
    status: str,
    days_left: int | None,
    device_id: str = "",
) -> dict[str, Any]:
    activated_at = now_iso() if status == "active" else None
    expire_at = (
        (datetime.now(SHANGHAI) + timedelta(days=days_left)).isoformat(timespec="seconds")
        if days_left is not None
        else None
    )
    return {
        "license_key": key,
        "plan_name": plan_name,
        # Read by sync_software_license_payload; "active" is what
        # is_software_user_activated() accepts.
        "status": status,
        "activated_at": activated_at,
        "expire_at": expire_at,
        "device_id": device_id,
        "device_name": "开发设备" if device_id else "",
        "max_devices": 3,
        "bound_devices": 1 if device_id else 0,
        "created_at": now_iso(),
        "note": "开发桩数据，非真实卡密",
    }


def seed_licenses() -> None:
    with STATE_LOCK:
        if LICENSES:
            return
        rows = [
            ("DEV-LIC-0001-AAAA", "年度版", "active", 300, "dev-device-a"),
            ("DEV-LIC-0002-BBBB", "季度版", "active", 60, ""),
            ("DEV-LIC-0003-CCCC", "月度版", "expired", -5, "dev-device-b"),
            ("DEV-LIC-0004-DDDD", "年度版", "unused", None, ""),
            ("DEV-LIC-0005-EEEE", "永久版", "disabled", None, ""),
        ]
        for key, plan, status, days, device in rows:
            LICENSES[key] = make_license(
                key, plan_name=plan, status=status, days_left=days, device_id=device
            )


def build_stats() -> dict[str, Any]:
    with STATE_LOCK:
        values = list(LICENSES.values())
    counts: dict[str, int] = {}
    for row in values:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {
        "total": len(values),
        "active": counts.get("active", 0),
        "expired": counts.get("expired", 0),
        "unused": counts.get("unused", 0),
        "disabled": counts.get("disabled", 0),
        "bound_devices": sum(int(row.get("bound_devices") or 0) for row in values),
        "generated_at": now_iso(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "DevLicenseStub/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"  [license-stub] {fmt % args}", flush=True)

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            parsed = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _admin_authorized(self) -> bool:
        expected = os.getenv("LICENSE_ADMIN_TOKEN", "").strip()
        if not expected:
            # Mirror the real server: no token configured means refuse, so the
            # dev setup fails loudly instead of silently accepting anything.
            return False
        return self.headers.get("X-Admin-Token", "") == expected

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", 1)[0]
        if path == "/api/admin/stats":
            if not self._admin_authorized():
                self._send(401, {"status": "error", "message": "invalid admin token"})
                return
            self._send(200, {"status": "ok", "stats": build_stats()})
            return
        if path == "/api/admin/licenses":
            if not self._admin_authorized():
                self._send(401, {"status": "error", "message": "invalid admin token"})
                return
            with STATE_LOCK:
                items = list(LICENSES.values())
            self._send(200, {"status": "ok", "items": items})
            return
        if path in {"/api/health", "/health"}:
            self._send(200, {"status": "ok", "service": "dev-license-stub"})
            return
        self._send(404, {"status": "error", "message": f"no stub for GET {path}"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = self.path.split("?", 1)[0]
        payload = self._read_json()

        if path == "/api/admin/licenses/create":
            if not self._admin_authorized():
                self._send(401, {"status": "error", "message": "invalid admin token"})
                return
            count = payload.get("count") or payload.get("quantity") or 1
            try:
                count = max(1, min(int(count), 50))
            except (TypeError, ValueError):
                count = 1
            plan_name = str(payload.get("plan_name") or "年度版")
            created = []
            with STATE_LOCK:
                start = len(LICENSES) + 1
                for offset in range(count):
                    key = f"DEV-LIC-{start + offset:04d}-NEW{offset:01d}"
                    record = make_license(key, plan_name=plan_name, status="unused", days_left=None)
                    LICENSES[key] = record
                    created.append(record)
            self._send(200, {"status": "ok", "items": created})
            return

        status_match = re.fullmatch(r"/api/admin/licenses/([^/]+)/status", path)
        if status_match:
            if not self._admin_authorized():
                self._send(401, {"status": "error", "message": "invalid admin token"})
                return
            key = status_match.group(1)
            new_status = str(payload.get("status") or "").strip().lower()
            if new_status not in {"active", "disabled", "expired", "unused"}:
                self._send(400, {"status": "error", "message": "unsupported status"})
                return
            with STATE_LOCK:
                record = LICENSES.get(key)
                if record is None:
                    self._send(404, {"status": "error", "message": "license not found"})
                    return
                record["status"] = new_status
                item = dict(record)
            self._send(200, {"status": "ok", "item": item})
            return

        unbind_match = re.fullmatch(r"/api/admin/licenses/([^/]+)/unbind", path)
        if unbind_match:
            if not self._admin_authorized():
                self._send(401, {"status": "error", "message": "invalid admin token"})
                return
            key = unbind_match.group(1)
            with STATE_LOCK:
                record = LICENSES.get(key)
                if record is None:
                    self._send(404, {"status": "error", "message": "license not found"})
                    return
                record["device_id"] = ""
                record["device_name"] = ""
                record["bound_devices"] = 0
                item = dict(record)
            self._send(200, {"status": "ok", "item": item})
            return

        if path in {"/api/license/validate", "/api/license/activate"}:
            # Public paths: the real server authenticates by license key, not by
            # admin token, so no header check here.
            key = str(payload.get("license_key") or "").strip()
            device_id = str(payload.get("device_id") or "").strip()
            if not key:
                self._send(400, {"status": "error", "message": "license_key is required"})
                return
            with STATE_LOCK:
                record = LICENSES.get(key)
                if record is None:
                    if path == "/api/license/activate":
                        # Unknown key on activate: accept it so the dev flow can
                        # bind any string, but mark where it came from.
                        record = make_license(
                            key, plan_name="开发临时版", status="active", days_left=90,
                            device_id=device_id,
                        )
                        LICENSES[key] = record
                    else:
                        self._send(404, {"status": "error", "message": "license not found"})
                        return
                if path == "/api/license/activate":
                    record["status"] = "active"
                    record["device_id"] = device_id
                    record["device_name"] = str(payload.get("device_name") or "开发设备")
                    record["bound_devices"] = 1
                    if not record.get("expire_at"):
                        record["expire_at"] = (
                            datetime.now(SHANGHAI) + timedelta(days=90)
                        ).isoformat(timespec="seconds")
                    record["activated_at"] = now_iso()
                item = dict(record)
            self._send(200, {"status": "ok", "license": item})
            return

        self._send(404, {"status": "error", "message": f"no stub for POST {path}"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--port",
        type=int,
        default=15000,
        help="Must match LICENSE_SERVER_BASE_URL (deploy/.env.example uses 15000).",
    )
    args = parser.parse_args()

    seed_licenses()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    token = os.getenv("LICENSE_ADMIN_TOKEN", "").strip()
    print(f"dev license stub on http://{args.host}:{args.port}")
    print(f"  seeded licenses : {len(LICENSES)}")
    print(f"  admin token     : {'set' if token else 'NOT SET -- admin paths will 401'}")
    print("  Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
