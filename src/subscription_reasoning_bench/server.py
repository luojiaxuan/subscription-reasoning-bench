from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .adapters import ClaudeAdapter, CodexAdapter
from .reporting import load_records, summarize
from .research_reporting import summarize_research


def capabilities() -> dict[str, object]:
    return {
        "codex": {
            "models": sorted(CodexAdapter.models),
            "efforts": ["high", "xhigh", "max", "ultra"],
            "speeds": ["standard", "fast"],
            "subscription_auth": "ChatGPT login",
        },
        "claude": {
            "models": sorted(ClaudeAdapter.models),
            "efforts": ["high", "xhigh", "max"],
            "speeds": ["standard"],
            "subscription_auth": "claude.ai login",
            "note": "ultracode is orchestration at xhigh, not an ultra model effort",
        },
    }


def find_ui_dir() -> Path:
    candidates = [Path(__file__).parent / "ui", Path(__file__).parents[2] / "ui"]
    for candidate in candidates:
        if (candidate / "index.html").exists():
            return candidate
    raise FileNotFoundError("UI assets are missing")


def collect_records(results_dir: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    if not results_dir.exists():
        return records
    for path in sorted(results_dir.rglob("*.jsonl")):
        if "traces" in path.parts:
            continue
        try:
            records.extend(load_records(path))
        except (json.JSONDecodeError, KeyError):
            continue
    return records


def short_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        record
        for record in records
        if not str(record.get("record_type", "")).startswith("research")
    ]


def make_handler(results_dir: Path, ui_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/summary":
                self.send_json(summarize(short_records(collect_records(results_dir))))
                return
            if parsed.path == "/api/research-summary":
                self.send_json(summarize_research(collect_records(results_dir)))
                return
            if parsed.path == "/api/capabilities":
                self.send_json(capabilities())
                return
            if parsed.path.startswith("/api/"):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            relative = "index.html" if parsed.path in {"", "/"} else parsed.path.lstrip("/")
            target = (ui_dir / relative).resolve()
            if ui_dir.resolve() not in target.parents and target != ui_dir.resolve():
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not target.is_file():
                target = ui_dir / "index.html"
            payload = target.read_bytes()
            content_type, _ = mimetypes.guess_type(target.name)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def send_json(self, value: object) -> None:
            payload = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def serve(results_dir: Path, host: str, port: int) -> None:
    ui_dir = find_ui_dir()
    server = ThreadingHTTPServer((host, port), make_handler(results_dir.resolve(), ui_dir.resolve()))
    print(f"SRB UI: http://{host}:{port}")
    print(f"Results: {results_dir.resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
