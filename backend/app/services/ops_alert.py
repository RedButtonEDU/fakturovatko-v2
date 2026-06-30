"""Operational alerts to configured ops e-mail."""

import logging

from app.config import get_settings
from app.services import email as email_svc

logger = logging.getLogger(__name__)


def notify_ops(subject: str, body: str) -> None:
    s = get_settings()
    to = (s.allfred_quick_setup_error_email or "").strip()
    if not to:
        logger.error("ops alert skipped (allfred_quick_setup_error_email empty): %s", subject)
        return
    if not s.gmail_refresh_token:
        logger.error("ops alert skipped (GMAIL_REFRESH_TOKEN missing): %s — %s", subject, body[:500])
        return
    try:
        email_svc.send_email(to, subject, body)
        logger.info("ops alert sent to %s: %s", to, subject)
    except Exception as e:
        logger.exception("ops alert failed (%s): %s", subject, e)
