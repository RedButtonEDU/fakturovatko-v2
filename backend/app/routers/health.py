from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Production: only ``status``. With ``DEBUG=true``: resolved Gmail From for local smoke checks."""
    if get_settings().debug:
        s = get_settings()
        return {
            "status": "ok",
            "gmail_from_email": s.gmail_from_email,
            "gmail_from_name": s.gmail_from_name,
        }
    return {"status": "ok"}
