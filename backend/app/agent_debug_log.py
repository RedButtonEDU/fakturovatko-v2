"""NDJSON debug ingest (Cursor debug mode). Do not log secrets."""

from __future__ import annotations

import json
import time
from pathlib import Path

# Repo root: backend/app/agent_debug_log.py → parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = _REPO_ROOT / ".cursor" / "debug-4dff2c.log"
SESSION_ID = "4dff2c"


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
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


def email_domain(addr: str) -> str:
    parts = (addr or "").strip().lower().split("@", 1)
    return parts[1] if len(parts) == 2 else ""
