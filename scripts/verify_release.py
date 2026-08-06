from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request


def read_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return json.load(response)


def check_version(ready: dict, check: str, expected: str) -> None:
    """Fail unless the named build check reports exactly the expected version.

    The App ships separately from the PC frontend, so each version is passed in
    on its own and an omitted argument means "do not care about this one".
    """
    if not expected:
        return
    actual = str(ready.get("checks", {}).get(check, {}).get("version", ""))
    if actual != expected:
        raise RuntimeError(f"expected {check} {expected}, got {actual or '<missing>'}")


def main() -> int:
    base_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    expected_version = sys.argv[2] if len(sys.argv) > 2 else ""
    expected_app_version = sys.argv[3] if len(sys.argv) > 3 else ""
    ready = read_json(f"{base_url}/health/ready")
    if ready.get("status") != "ok":
        raise RuntimeError(f"readiness failed: {ready}")
    check_version(ready, "frontend", expected_version)
    check_version(ready, "app", expected_app_version)
    print(json.dumps(ready, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, urllib.error.URLError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
