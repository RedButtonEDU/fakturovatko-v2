"""NDJSON debug ingest (Cursor debug mode). Do not log secrets.

V Docker/Coolify není workspace ``.cursor/`` — výchozí cesta je ``/tmp`` (vždy zapisovatelné).
Volitelně: ``FAKTUROVATKO_DEBUG_LOG=/data/debug-4dff2c.log`` při mountu svazku.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

SESSION_ID = "4dff2c"


def _log_path() -> Path:
    raw = (os.environ.get("FAKTUROVATKO_DEBUG_LOG") or "").strip()
    if raw:
        return Path(raw)
    # Coolify / Linux container: /tmp is writable without extra volume
    return Path("/tmp/debug-4dff2c.log")


def log_event(
    location: str,
    message: str,
    data: dict,
    *,
    hypothesis_id: str,
    run_id: str = "pre-fix",
) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": SESSION_ID,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


def email_domain(addr: str) -> str:
    parts = (addr or "").strip().lower().split("@", 1)
    return parts[1] if len(parts) == 2 else ""
