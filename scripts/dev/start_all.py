"""Start the whole stack locally, with the server-only pieces stubbed.

Four things the production host provides are missing on a dev box, and each one
fails in a way that looks like a broken page rather than missing config:

  * the SYCM collector (a separate program on a machine with 生意参谋 logged in)
    -- without it 同步数据 queues a task nobody claims
  * the DingTalk robot webhook -- without it pushing a link 503s
  * the license server (reached in production over an SSH tunnel to the legacy
    Aliyun box) -- without it every 卡密 page 502s
  * four side sqlite files under /srv/fastapiproject -- absent locally, so the
    routes that read them 500

This sets the env vars that redirect all of them at local paths/ports, then
launches: license stub, DingTalk receiver, backend, fake collector, and both
frontend dev servers.

Run:
  python scripts/dev/start_all.py              # everything
  python scripts/dev/start_all.py --no-frontend
  python scripts/dev/start_all.py --only backend,collector

Ctrl+C stops every child process.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEV_DIR = PROJECT_ROOT / "scripts" / "dev"

sys.path.insert(0, str(DEV_DIR))

import init_side_dbs  # noqa: E402  (needs DEV_DIR on the path first)

# Holds the three side sqlite files. init_side_dbs owns both the layout and the
# rule-catalog schema, so importing it is what keeps the paths this launcher
# exports and the files it creates from drifting apart.
SIDE_DB_ROOT = PROJECT_ROOT / "_dev_side_dbs"

# Dev-only shared secrets. These are not credentials for anything real -- they
# only have to agree between the backend and the stubs in this same process
# tree, which is exactly why they can be hardcoded here.
DEV_SYCM_UPLOAD_TOKEN = "dev-sycm-upload-token"
DEV_INTERNAL_SYNC_TOKEN = "dev-internal-sync-token"
DEV_LICENSE_ADMIN_TOKEN = "dev-license-admin-token"

LICENSE_STUB_PORT = 15000
DINGTALK_PORT = 15100


def venv_python() -> str:
    """The venv interpreter, so children import the project's deps.

    sys.executable is not enough: this script may be launched by a bare python
    while FastAPI/httpx only exist inside .venv.
    """
    candidate = PROJECT_ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python"
    )
    return str(candidate) if candidate.exists() else sys.executable


def build_env() -> dict[str, str]:
    """Every var that redirects a server-only dependency at something local."""
    # Creates the files too, not just the paths. The rule catalog is the reason
    # this has to run before the backend: it only reads and updates, so a missing
    # file makes it answer 503 rather than bootstrap itself.
    init_side_dbs.init(SIDE_DB_ROOT)

    env = dict(os.environ)
    env.update({
        # --- the main database. Without this the backend falls back to
        # DEFAULT_SQLITE_PATH (shop_records.db) and creates it empty, so every
        # login fails with 401 even though seed_dev_data.py filled dev.db.
        "DATABASE_URL": f"sqlite:///{PROJECT_ROOT / 'dev.db'}",

        # --- tokens shared with the stubs below
        "SYCM_UPLOAD_TOKEN": DEV_SYCM_UPLOAD_TOKEN,
        "DINGTALK_PROFIT_SYNC_TOKEN": DEV_INTERNAL_SYNC_TOKEN,
        "LICENSE_ADMIN_TOKEN": DEV_LICENSE_ADMIN_TOKEN,

        # --- redirect the two outbound integrations at local processes
        "DINGTALK_ROBOT_WEBHOOK": f"http://127.0.0.1:{DINGTALK_PORT}/robot/send",
        # Left empty on purpose: with no secret the backend skips HMAC signing,
        # which is one less moving part. The receiver accepts both.
        "DINGTALK_ROBOT_SECRET": "",
        "LICENSE_SERVER_BASE_URL": f"http://127.0.0.1:{LICENSE_STUB_PORT}",

        # --- links in DingTalk pushes. build_saved_link_detail_url appends
        # /ui/..., which the PC console serves on 5173 -- 5174 is the mobile App
        # under /app/ and would 404.
        "PUBLIC_APP_BASE_URL": "http://127.0.0.1:5173",

        "REDIS_ENABLED": "false",
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
    })

    # The four side sqlite paths, from the initializer so a path can never drift
    # from the schema it creates. Their defaults point at /srv/fastapiproject/...
    # and every route reading one fails: two raise "unable to open database
    # file", and the rule catalog answers 503 on a missing file.
    env.update({key: str(value) for key, value in init_side_dbs.env_for(SIDE_DB_ROOT).items()})
    return env


def describe(env: dict[str, str]) -> None:
    print("dev environment")
    for key in (
        "DATABASE_URL",
        "SYCM_DATA_DB_PATH",
        "RULE_CATALOG_DB_PATH",
        "PRODUCT_PARSE_CACHE_DB_PATH",
        "PUBLISH_FAILURE_REPORT_DB_PATH",
        "DINGTALK_ROBOT_WEBHOOK",
        "LICENSE_SERVER_BASE_URL",
        "PUBLIC_APP_BASE_URL",
    ):
        print(f"  {key:32} {env[key]}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-frontend", action="store_true", help="Skip both vite dev servers.")
    parser.add_argument(
        "--only",
        default="",
        help="Comma-separated subset of: license,dingtalk,backend,collector,app,pc",
    )
    args = parser.parse_args()

    python = venv_python()
    env = build_env()
    describe(env)

    specs: list[tuple[str, list[str], Path]] = [
        ("license", [python, str(DEV_DIR / "license_server_stub.py"), "--port", str(LICENSE_STUB_PORT)], PROJECT_ROOT),
        ("dingtalk", [python, str(DEV_DIR / "dingtalk_receiver.py"), "--port", str(DINGTALK_PORT)], PROJECT_ROOT),
        ("backend", [python, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"], PROJECT_ROOT),
        # --watch keeps polling, so a 同步数据 click is picked up seconds later
        # instead of needing a manual run.
        ("collector", [python, str(DEV_DIR / "fake_collector.py"), "--watch"], PROJECT_ROOT),
        # npm run dev inherits the cwd vite.config.ts, which controls the port.
        # Pass --host explicitly so vite binds to 127.0.0.1 and not ::1 (IPv6
        # only); localhost resolves to ::1 on Windows and the app just 404s.
        ("app", ["npm", "run", "dev", "--", "--host", "127.0.0.1"], PROJECT_ROOT / "app-frontend"),
        ("pc",  ["npm", "run", "dev", "--", "--host", "127.0.0.1"], PROJECT_ROOT / "frontend"),
    ]

    wanted = {name.strip() for name in args.only.split(",") if name.strip()}
    if wanted:
        specs = [spec for spec in specs if spec[0] in wanted]
    elif args.no_frontend:
        specs = [spec for spec in specs if spec[0] not in {"app", "pc"}]

    children: list[tuple[str, subprocess.Popen[bytes]]] = []
    # npm on Windows is a .cmd shim, which only runs through the shell.
    use_shell = os.name == "nt"

    try:
        for name, command, cwd in specs:
            if name in {"app", "pc"} and not (cwd / "node_modules").exists():
                print(f"  skip {name}: {cwd / 'node_modules'} missing (run npm install)")
                continue
            print(f"  start {name}")
            process = subprocess.Popen(
                subprocess.list2cmdline(command) if use_shell and command[0] == "npm" else command,
                cwd=str(cwd),
                env=env,
                shell=use_shell and command[0] == "npm",
            )
            children.append((name, process))
            # The collector and the frontends both need the backend listening;
            # give uvicorn a moment rather than racing it.
            if name == "backend":
                time.sleep(3)
            else:
                time.sleep(0.4)

        print()
        print("running. endpoints:")
        print("  backend          http://127.0.0.1:8000")
        print("  mobile app       http://127.0.0.1:5174/app/")
        print("  PC console       http://127.0.0.1:5173/ui/")
        print(f"  dingtalk pushes  http://127.0.0.1:{DINGTALK_PORT}/  (what the robot would have sent)")
        print(f"  license stub     http://127.0.0.1:{LICENSE_STUB_PORT}/api/health")
        print()
        print("  admin / dev12345   (use 127.0.0.1, not localhost)")
        print("  Ctrl+C stops everything")
        print()

        while True:
            for name, process in children:
                code = process.poll()
                if code is not None:
                    print(f"\n[{name}] exited with code {code}")
                    return code or 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopping")
        return 0
    finally:
        for name, process in reversed(children):
            if process.poll() is not None:
                continue
            try:
                if os.name == "nt":
                    process.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
                else:
                    process.terminate()
            except (OSError, ValueError, AttributeError):
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
