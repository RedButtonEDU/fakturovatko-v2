"""Protected internal endpoints (Coolify scheduled task)."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.services.workflow import process_paid_orders

router = APIRouter(prefix="/internal", tags=["internal"])


def verify_cron(x_cron_token: Optional[str] = Header(None, alias="X-Cron-Token")) -> None:
    s = get_settings()
    if not x_cron_token or x_cron_token != s.cron_secret:
        raise HTTPException(401, "Invalid cron token")


@router.post("/jobs/poll-payments")
async def poll_payments(
    db: Session = Depends(get_db),
    _auth: None = Depends(verify_cron),
):
    result = await process_paid_orders(db)
    return result
