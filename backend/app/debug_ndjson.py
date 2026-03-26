"""Session debug NDJSON logger (Cursor debug mode). Do not log secrets or PII."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

def _log_path() -> Path:
    """Repo .cursor locally; in Docker image (/app/app/...) use /app/.cursor."""
    here = Path(__file__).resolve()
    for i in range(2, min(8, len(here.parents))):
        ancestor = here.parents[i]
        if (ancestor / "frontend").is_dir() and (ancestor / "backend").is_dir():
            return ancestor / ".cursor" / "debug-42613d.log"
    return Path("/app/.cursor") / "debug-42613d.log"


_SESSION_ID = "42613d"


def log(
    *,
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict[str, Any] | None = None,
    run_id: str = "run1",
) -> None:
    payload: dict[str, Any] = {
        "sessionId": _SESSION_ID,
        "timestamp": int(time.time() * 1000),
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "runId": run_id,
    }
    try:
        lp = _log_path()
        lp.parent.mkdir(parents=True, exist_ok=True)
        with lp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
