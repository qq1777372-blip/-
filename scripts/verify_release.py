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


def main() -> int:
    base_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    expected_version = sys.argv[2] if len(sys.argv) > 2 else ""
    ready = read_json(f"{base_url}/health/ready")
    if ready.get("status") != "ok":
        raise RuntimeError(f"readiness failed: {ready}")
    actual_version = str(ready.get("checks", {}).get("frontend", {}).get("version", ""))
    if expected_version and actual_version != expected_version:
        raise RuntimeError(f"expected frontend {expected_version}, got {actual_version}")
    print(json.dumps(ready, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, urllib.error.URLError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
