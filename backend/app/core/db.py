"""
Database connection module — Firestore (replaces MongoDB).
"""
from app.services.database_service import get_firestore


async def connect_to_mongo():
    """Initialize Firestore (kept name for backward compat)."""
    db = get_firestore()
    if db:
        print("✅ Firestore connected")
    else:
        print("⚠️ Firestore not available")


async def close_mongo_connection():
    """No-op for Firestore (connection managed by SDK)."""
    print("🔌 Firestore connection closed")


def get_database():
    """Get Firestore client."""
    return get_firestore()


async def get_db():
    """FastAPI dependency — returns Firestore client."""
    db = get_firestore()
    if db is None:
        raise Exception("Firestore not connected")
    return db
