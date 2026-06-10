"""
KisanMitra AI API — Authentication Router (Firebase)
===================================================
Auth is now handled client-side by Firebase Auth SDK.
This router provides a token verification endpoint for the backend.
"""
from fastapi import APIRouter, Header, HTTPException
from typing import Optional
from app.services.auth_service import verify_firebase_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/verify")
async def verify_token(authorization: Optional[str] = Header(None)):
    """Verify a Firebase ID token from the Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split("Bearer ")[1]
    user = await verify_firebase_token(token)

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {"ok": True, "user": user}


@router.get("/status")
async def auth_status():
    """Auth system status."""
    return {
        "ok": True,
        "provider": "firebase",
        "methods": ["email_password"],
        "note": "Auth is handled client-side by Firebase Auth SDK. Use /auth/verify to validate tokens.",
    }
