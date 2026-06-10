"""
Firebase Auth verification for backend routes.
Verifies Firebase ID tokens sent from the Flutter app.
"""
from firebase_admin import auth as firebase_auth
from typing import Optional, Dict, Any


async def verify_firebase_token(id_token: str) -> Optional[Dict[str, Any]]:
    """Verify a Firebase ID token and return user info."""
    try:
        decoded = firebase_auth.verify_id_token(id_token)
        return {
            "uid": decoded["uid"],
            "email": decoded.get("email", ""),
            "name": decoded.get("name", ""),
        }
    except Exception as e:
        print(f"⚠️ Firebase token verification failed: {e}")
        return None


def get_uid_from_token(id_token: str) -> Optional[str]:
    """Quick helper to extract UID from token."""
    try:
        decoded = firebase_auth.verify_id_token(id_token)
        return decoded["uid"]
    except Exception:
        return None
