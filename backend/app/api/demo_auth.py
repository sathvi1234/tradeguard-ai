"""Hackathon demo login. No production auth. No secrets returned."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class DemoLoginRequest(BaseModel):
    email: Optional[str] = None
    continue_as_demo: bool = False
    password: Optional[str] = Field(default=None, exclude=True)


@router.post("/demo")
async def demo_login(body: DemoLoginRequest) -> dict:
    """Issue a demo session descriptor. Password is never stored, logged, or returned."""
    expected = settings.demo_user_email.strip().lower()
    email = (body.email or "").strip().lower()
    if not body.continue_as_demo and email != expected:
        raise HTTPException(status_code=401, detail="Use Continue as Demo User or the configured demo email")
    return {
        "ok": True,
        "user": {
            "name": "Demo User",
            "email": settings.demo_user_email,
            "role": "demo",
            "paper_trading": True,
            "dry_run": True,
            "live_trading": False,
        },
        "session": "demo",
        "message": "Demo session. Paper trading ON. DRY_RUN ON. Live trading BLOCKED.",
    }
