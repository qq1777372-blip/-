"""Collect this machine's runtime metrics and POST them to the main site.

`collect_server_status` can only read the box it runs on -- /proc, systemctl and
disk_usage are all local -- so a second server has to report in. This script is
what runs there, on a timer, pushing to /dashboard/server-status/push.

Standard library only, deliberately: the secondary box has no virtualenv for this
project. The metric collection itself is imported from
`app/services/server_status.py` rather than reimplemented, so the two machines
cannot drift apart. That module is stdlib-only as long as no engine is passed,
which is exactly how it is called here.

Deploy: copy this file plus `app/services/server_status.py` to the target box,
keeping either the repo layout or both files in one directory.

    python3 report_server_status.py \
        --base-url https://xiaoxu666.asia \
        --node-id aliyun \
        --label 阿里云旧机 \
        --token "$SERVER_STATUS_PUSH_TOKEN"

The token must match SERVER_STATUS_PUSH_TOKEN on the main site. Prefer passing it
as --token-env so it does not show up in `ps`. Exit code is non-zero on failure so
cron/systemd surfaces the problem.

Suggested systemd timer on the reporting box (every 2 minutes):

    # /etc/systemd/system/server-status-report.service
    [Service]
    Type=oneshot
    Environment=SERVER_STATUS_PUSH_TOKEN=...
    ExecStart=/usr/bin/python3 /opt/ops/report_server_status.py \
        --base-url https://xiaoxu666.asia --node-id aliyun --token-env SERVER_STATUS_PUSH_TOKEN
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent


def _load_collector():
    """Import collect_server_status from the repo, or from beside this script.

    Two layouts have to work: run from a checkout (scripts/ops/... with the repo
    root two levels up), and run from a flat directory on the reporting box where
    server_status.py was copied next to this file.
    """
    candidates = [SCRIPT_DIR.parents[1], SCRIPT_DIR]
    for root in candidates:
        if (root / "app" / "services" / "server_status.py").is_file():
            sys.path.insert(0, str(root))
            from app.services.server_status import collect_server_status

            return collect_server_status

    if (SCRIPT_DIR / "server_status.py").is_file():
        sys.path.insert(0, str(SCRIPT_DIR))
        from server_status import collect_server_status  # type: ignore[no-redef]

        return collect_server_status

    raise SystemExit(
        "cannot find the collector. Copy app/services/server_status.py next to "
        f"this script ({SCRIPT_DIR}) or run from a full checkout.",
    )


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"cannot serialise {type(value).__name__}")


def _parse_roots(values: list[str]) -> tuple[tuple[str, Path], ...]:
    """Parse `label=/path` pairs, tolerating a bare path (label = its name)."""
    roots: list[tuple[str, Path]] = []
    for entry in values:
        label, separator, raw_path = entry.partition("=")
        if not separator:
            label, raw_path = Path(entry).name or entry, entry
        path = Path(raw_path.strip()).expanduser()
        roots.append((label.strip() or path.name, path))
    return tuple(roots)


def _parse_services(values: list[str]) -> tuple[tuple[str, str], ...]:
    """Parse `unit=显示名` pairs, tolerating a bare unit name."""
    services: list[tuple[str, str]] = []
    for entry in values:
        unit, separator, label = entry.partition("=")
        unit = unit.strip()
        if not unit:
            continue
        services.append((unit, (label.strip() if separator else "") or unit))
    return tuple(services)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True, help="Main site root, e.g. https://xiaoxu666.asia")
    parser.add_argument("--node-id", required=True, help="Stable id for this machine ([A-Za-z0-9._-])")
    parser.add_argument("--label", default=None, help="Display name shown in the console")
    parser.add_argument("--token", default=None, help="Push token (prefer --token-env)")
    parser.add_argument(
        "--token-env",
        default="SERVER_STATUS_PUSH_TOKEN",
        help="Environment variable holding the token (default: SERVER_STATUS_PUSH_TOKEN)",
    )
    parser.add_argument(
        "--disk-path",
        default="/",
        help="Filesystem to measure for the disk figures (default: /)",
    )
    parser.add_argument(
        "--database-root",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="Directory to scan for SQLite files; repeatable. Omit if the box has none.",
    )
    parser.add_argument(
        "--service",
        action="append",
        default=[],
        metavar="UNIT=显示名",
        help="systemd unit to report; repeatable.",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    parser.add_argument(
        "--interval",
        type=float,
        default=0.0,
        help=(
            "Seconds between reports. 0 (default) sends once and exits, which is "
            "what a systemd timer or cron wants; a positive value stays running."
        ),
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the payload instead of sending it")
    return parser


def push_once(args: argparse.Namespace, token: str, collect_server_status: Any) -> int:
    # engine=None: this box has no application database, and the collector
    # reports that as "not-configured" rather than treating it as a failure.
    metrics = collect_server_status(
        engine=None,
        base_dir=Path(args.disk_path),
        database_roots=_parse_roots(args.database_root),
        services=_parse_services(args.service),
    )

    payload = {"node_id": args.node_id, "metrics": metrics}
    if args.label:
        payload["label"] = args.label

    if args.dry_run:
        print(json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2))
        return 0

    body = json.dumps(payload, default=_json_default, ensure_ascii=False).encode("utf-8")
    url = f"{args.base_url.rstrip('/')}/dashboard/server-status/push"
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-Server-Status-Token": token},
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            print(f"ok {response.status} {response.read().decode('utf-8', 'replace')[:200]}")
    except urllib.error.HTTPError as exc:
        # The response body carries the reason (bad token, id collision), which
        # is the whole diagnostic when this runs unattended.
        detail = exc.read().decode("utf-8", "replace")[:300]
        print(f"push failed: HTTP {exc.code} {detail}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        print(f"push failed: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    token = args.token or os.getenv(args.token_env, "").strip()
    if not token and not args.dry_run:
        print(f"no token: pass --token or set {args.token_env}", file=sys.stderr)
        return 2

    collect_server_status = _load_collector()

    if args.interval <= 0:
        return push_once(args, token, collect_server_status)

    # Long-running mode: a failed report must not end the loop, or one restart of
    # the main site would silently stop this node from ever reporting again.
    while True:
        try:
            push_once(args, token, collect_server_status)
        except Exception as exc:  # noqa: BLE001 - the loop outliving any single error is the point
            print(f"report failed: {exc}", file=sys.stderr)
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
