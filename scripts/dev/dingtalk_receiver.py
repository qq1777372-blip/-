"""Local stand-in for the 钉钉 robot webhook, for local debugging.

`DINGTALK_ROBOT_WEBHOOK` is unset locally, so every push raises 503
("未配置 DINGTALK_ROBOT_WEBHOOK") and the feature cannot be exercised at all.
Pointing that variable at this server makes pushes succeed and, more usefully,
shows exactly what markdown the backend built.

    python scripts/dev/dingtalk_receiver.py
    -> POST http://127.0.0.1:8610/robot/send   what the backend calls
    -> GET  http://127.0.0.1:8610/            rendered log of everything received

It answers the way 钉钉 does ({"errcode": 0, "errmsg": "ok"}) so the backend's
own success/failure handling is what gets tested, not this stub's.
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

RECEIVED: list[dict[str, object]] = []
MAX_KEPT = 200


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return  # the console prints a readable summary instead

    def _json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {"_unparsed": raw.decode("utf-8", "replace")}

        query = parse_qs(parsed.query)
        entry = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "path": parsed.path,
            # The backend appends these only when DINGTALK_ROBOT_SECRET is set,
            # so their presence tells you whether signing is being exercised.
            "signed": "sign" in query and "timestamp" in query,
            "msgtype": payload.get("msgtype") if isinstance(payload, dict) else None,
            "payload": payload,
        }
        RECEIVED.append(entry)
        del RECEIVED[:-MAX_KEPT]

        title = ""
        if isinstance(payload, dict):
            markdown = payload.get("markdown")
            if isinstance(markdown, dict):
                title = str(markdown.get("title") or "")
        signed = "signed" if entry["signed"] else "unsigned"
        print(f"[{entry['at']}] {signed} {entry['msgtype']} {title}")

        self._json(200, {"errcode": 0, "errmsg": "ok"})

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path == "/messages":
            self._json(200, {"count": len(RECEIVED), "items": RECEIVED})
            return

        rows = []
        for entry in reversed(RECEIVED):
            payload = entry["payload"]
            markdown = payload.get("markdown") if isinstance(payload, dict) else None
            title = str(markdown.get("title") or "") if isinstance(markdown, dict) else ""
            text = str(markdown.get("text") or "") if isinstance(markdown, dict) else json.dumps(
                payload, ensure_ascii=False, indent=2
            )
            rows.append(
                "<article>"
                f"<h2>{html.escape(title) or '(no title)'}</h2>"
                f"<small>{entry['at']} · {entry['msgtype']} · "
                f"{'signed' if entry['signed'] else 'unsigned'}</small>"
                f"<pre>{html.escape(text)}</pre>"
                "</article>"
            )
        body = (
            "<!doctype html><meta charset='utf-8'>"
            "<title>钉钉推送接收器（本地）</title>"
            "<style>body{font:14px/1.6 system-ui;margin:24px;max-width:760px}"
            "article{border:1px solid #e5e7eb;border-radius:10px;padding:12px 16px;margin:12px 0}"
            "h1{font-size:18px}h2{font-size:15px;margin:0 0 4px}"
            "small{color:#6b7280}pre{white-space:pre-wrap;background:#f9fafb;padding:10px;"
            "border-radius:8px;margin:8px 0 0}</style>"
            f"<h1>钉钉推送接收器 · 已收到 {len(RECEIVED)} 条</h1>"
            "<p>后端把推送发到这里而不是真实钉钉。发布一条链接即可看到内容。</p>"
            + ("".join(rows) or "<p>还没有收到推送。</p>")
        )
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8610)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"dingtalk receiver on http://{args.host}:{args.port}/")
    print(f"  set DINGTALK_ROBOT_WEBHOOK=http://{args.host}:{args.port}/robot/send")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
