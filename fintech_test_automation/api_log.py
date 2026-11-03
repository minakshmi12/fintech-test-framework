"""API request/response logging: kept per test, flushed to reports/api_logs/*.jsonl, and attached to failures."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

MAX_BODY = 2_000
LOG_DIR = Path("reports/api_logs")


def _truncate(value: Any) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= MAX_BODY else text[:MAX_BODY] + f"... [{len(text) - MAX_BODY} more chars]"


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: ("Bearer ****" if k.lower() == "authorization" else v) for k, v in headers.items()}


class ApiLogger:
    """Records every API call of a test (method, URL, status, bodies) to a JSONL log, redacting credentials."""

    def __init__(self, test_id: str):
        self.test_id = test_id
        self.entries: list[dict[str, Any]] = []

    def record(self, *, method: str, url: str, headers: dict[str, str], request_body: Any,
               status: int, response_body: str, started: float) -> None:
        """Add one API call to the log."""
        self.entries.append({
            "test": self.test_id,
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "method": method, "url": url, "status": status,
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
            "request_headers": redact_headers(headers),
            "request_body": _truncate(request_body) if request_body is not None else None,
            "response_body": _truncate(response_body),
        })

    def as_text(self) -> str:
        """Human-readable log, used in failure reports."""
        if not self.entries:
            return "(no API calls were made)"
        blocks = []
        for e in self.entries:
            blocks.append(
                f"{e['method']} {e['url']}  ->  {e['status']}  ({e['duration_ms']} ms)\n"
                f"  request : {e['request_body']}\n  response: {e['response_body']}")
        return "\n\n".join(blocks)

    def flush(self) -> None:
        """Append the recorded calls to the worker's JSONL log file."""
        if not self.entries:
            return
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        worker = os.getenv("PYTEST_XDIST_WORKER", "main")
        with open(LOG_DIR / f"api-{worker}.jsonl", "a", encoding="utf-8") as fh:
            for e in self.entries:
                fh.write(json.dumps(e) + "\n")
