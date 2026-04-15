"""NDJSON debug sink for Cursor debug mode (session 4dff2c)."""

import json
import sys
import time

LOG_PATH = "/Users/lukascypra/GitHub/Fakturovatko v2/.cursor/debug-4dff2c.log"
SESSION_ID = "4dff2c"


def agent_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict,
    *,
    run_id: str = "repro",
) -> None:
    try:
        line = {
            "sessionId": SESSION_ID,
            "timestamp": int(time.time() * 1000),
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
        }
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass
    try:
        # Remote deploy (Coolify): workspace path neexistuje — stejný řádek na stderr pro logy kontejneru
        print(json.dumps(line, ensure_ascii=False), file=sys.stderr, flush=True)
    except Exception:
        pass
