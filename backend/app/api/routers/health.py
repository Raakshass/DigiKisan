"""
KisanMitra AI API — Health & Utility Router
=========================================
- /health       — API health check
- /info         — list available endpoints
- /classify     — text classification
- /test-firestore — database connectivity test
- /check-data   — data store statistics
"""
from typing import Dict, Any

from fastapi import APIRouter, Depends, Body

from app.services.database_service import get_firestore
from app.api.deps import get_text_clf

router = APIRouter(tags=["Utility"])


@router.get("/health")
async def health():
    return {"status": "ok", "message": "KisanMitra AI Backend API is running"}


@router.post("/classify")
async def classify_text(
    payload: Dict[str, Any] = Body(...),
    clf: Any = Depends(get_text_clf),
):
    """Classify text as price_enquiry or non_price_enquiry."""
    text = payload.get("text", "")
    if not text.strip():
        return {"ok": False, "error": "Text cannot be empty"}
    result = clf.predict(text)
    return {"ok": True, "result": result}


@router.get("/test-firestore")
async def test_firestore():
    try:
        db = get_firestore()
        if db:
            # Test by reading a collection
            return {"ok": True, "message": "Firestore connected!"}
        return {"ok": False, "error": "Firestore not initialized"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Keep old endpoint for backward compat
@router.get("/test-mongodb")
async def test_mongodb():
    return await test_firestore()


@router.get("/check-data")
async def check_data():
    try:
        db = get_firestore()
        if not db:
            return {"ok": False, "error": "Firestore not connected"}
        return {
            "ok": True,
            "backend": "firestore",
            "status": "connected",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/info")
async def info():
    return {
        "api": "KisanMitra AI",
        "version": "2.0.0",
        "architecture": "Modular routers (chat, disease, utility)",
        "endpoints": {
            "health": "/health",
            "classify": "/classify",
            "chat": ["/chat/start-session", "/chat/message", "/chat/send", "/chat/slots"],
            "disease": ["/disease/predict", "/disease/chat", "/disease/chat/history", "/disease/chat/clear"],
            "utility": ["/test-firestore", "/check-data", "/info"],
        },
        "features": [
            "Production-grade async price scraper (no Selenium)",
            "OpenRouter LLM integration (multi-model fallback)",
            "Firebase Auth integration",
            "Session-based slot filling chat",
            "Crop disease detection with ResNet50",
            "Multilingual voice (Sarvam AI)",
            "Firestore session & analytics storage",
            "RAG knowledge base with ChromaDB",
        ],
    }
