from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """`gmail_from_*` = resolved runtime values (env or code defaults) used for MIME From when sending."""
    s = get_settings()
    return {
        "status": "ok",
        "gmail_from_email": s.gmail_from_email,
        "gmail_from_name": s.gmail_from_name,
    }
