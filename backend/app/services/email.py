"""Gmail send via OAuth2 refresh token (RB Universe pattern)."""

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import get_settings
from app.debug_ndjson import agent_log

logger = logging.getLogger(__name__)

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.send"
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _credentials(refresh_token: str) -> Credentials:
    s = get_settings()
    return Credentials(
        token=None,
        refresh_token=refresh_token.strip(),
        token_uri=TOKEN_URI,
        client_id=s.google_client_id,
        client_secret=s.google_client_secret,
        scopes=[GMAIL_SCOPE],
    )


def send_email(
    to: str,
    subject: str,
    body_text: str,
    *,
    body_html: Optional[str] = None,
    attachment_bytes: Optional[bytes] = None,
    attachment_name: Optional[str] = None,
    attachment_content_type: str = "application/pdf",
) -> None:
    s = get_settings()
    # region agent log
    agent_log(
        "H1",
        "email.py:send_email:entry",
        "resolved_settings_and_env_flags",
        {
            "gmail_from_email": s.gmail_from_email,
            "gmail_from_name": s.gmail_from_name,
            "env_GMAIL_FROM_EMAIL_defined": "GMAIL_FROM_EMAIL" in os.environ,
            "env_GMAIL_FROM_NAME_defined": "GMAIL_FROM_NAME" in os.environ,
        },
    )
    # endregion
    if not s.gmail_refresh_token:
        raise RuntimeError("GMAIL_REFRESH_TOKEN is not set")
    if not s.google_client_id or not s.google_client_secret:
        raise RuntimeError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required")

    creds = _credentials(s.gmail_refresh_token)
    creds.refresh(Request())
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    # region agent log
    oauth_mailbox: Optional[str] = None
    get_profile_error: Optional[str] = None
    try:
        prof = service.users().getProfile(userId="me").execute()
        oauth_mailbox = (prof.get("emailAddress") or "").strip() or None
    except Exception as e:
        get_profile_error = f"{type(e).__name__}:{str(e)[:160]}"
    if not oauth_mailbox and creds.token:
        try:
            req = urllib.request.Request(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {creds.token}"},
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                ui = json.loads(r.read().decode())
                oauth_mailbox = (ui.get("email") or "").strip() or None
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as e:
            if not get_profile_error:
                get_profile_error = f"userinfo:{type(e).__name__}"
    _want = (s.gmail_from_email or "").strip().lower()
    _got = (oauth_mailbox or "").strip().lower()
    agent_log(
        "H6",
        "email.py:send_email:oauth_identity",
        "mailbox_behind_userId_me_vs_mime_from",
        {
            "oauth_mailbox_email": oauth_mailbox,
            "get_profile_or_userinfo_error": get_profile_error,
            "gmail_from_email_setting": s.gmail_from_email,
            "oauth_mailbox_matches_mime_from_email": (_got == _want) if oauth_mailbox else None,
        },
    )
    # endregion
    if oauth_mailbox and _got != _want:
        logger.warning(
            "Gmail OAuth mailbox %s differs from GMAIL_FROM_EMAIL %s; many clients show the OAuth "
            "account as sender. Fix: obtain GMAIL_REFRESH_TOKEN via OAuth as %s, or add “Send mail as” "
            "for that address on the OAuth account in Google Workspace / Gmail.",
            oauth_mailbox,
            s.gmail_from_email,
            s.gmail_from_email,
        )

    # MIME From = GMAIL_FROM_* (viz config). OAuth účet u GMAIL_REFRESH_TOKEN může v klientovi
    # přebít zobrazení, pokud adresa v From není v Gmailu „Odesílat jako“ pro daný účet.
    from_hdr = formataddr((s.gmail_from_name, s.gmail_from_email))
    logger.info("Gmail send: MIME From header %s", from_hdr)

    if attachment_bytes and attachment_name:
        message = MIMEMultipart()
        message["to"] = to
        message["subject"] = subject
        message["from"] = from_hdr
        if body_html:
            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(body_text, "plain", "utf-8"))
            alt.attach(MIMEText(body_html, "html", "utf-8"))
            message.attach(alt)
        else:
            message.attach(MIMEText(body_text, "plain", "utf-8"))
        part = MIMEApplication(attachment_bytes, _subtype=attachment_content_type.split("/")[-1])
        part.add_header("Content-Disposition", "attachment", filename=attachment_name)
        message.attach(part)
    elif body_html:
        message = MIMEMultipart("alternative")
        message["to"] = to
        message["subject"] = subject
        message["from"] = from_hdr
        message.attach(MIMEText(body_text, "plain", "utf-8"))
        message.attach(MIMEText(body_html, "html", "utf-8"))
    else:
        message = MIMEText(body_text, "plain", "utf-8")
        message["to"] = to
        message["subject"] = subject
        message["from"] = from_hdr

    # region agent log
    _from_combined = f"{from_hdr} {(message.get('From') or message.get('from') or '')}"
    agent_log(
        "H2",
        "email.py:send_email:before_send",
        "mime_from_built",
        {
            "from_hdr": from_hdr,
            "message_get_From": message.get("From") or message.get("from"),
            "contains_hello_at": "hello@" in _from_combined.lower(),
        },
    )
    # endregion

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    # region agent log
    send_result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    agent_log(
        "H3",
        "email.py:send_email:after_gmail_api",
        "gmail_messages_send_response",
        {
            "message_id": send_result.get("id"),
            "thread_id": send_result.get("threadId"),
            "label_ids": send_result.get("labelIds"),
        },
    )
    # endregion
    logger.info("Email sent to %s", to)
