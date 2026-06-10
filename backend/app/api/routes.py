"""
KisanMitra AI API — Route Aggregator
==================================
This file aggregates all modular routers into a single APIRouter
for backward compatibility with main.py's `app.include_router(router, prefix="/api")`.

Architecture:
    main.py → routes.py (aggregator) → routers/chat.py
                                      → routers/disease.py
                                      → routers/auth.py
                                      → routers/health.py
"""
from fastapi import APIRouter

from app.api.routers.chat import router as chat_router
from app.api.routers.disease import router as disease_router
from app.api.routers.auth import router as auth_router
from app.api.routers.health import router as health_router
from app.api.routers.voice import router as voice_router

# Main aggregator router — included by main.py with prefix="/api"
router = APIRouter()

# Include all sub-routers
router.include_router(chat_router)
router.include_router(disease_router)
router.include_router(auth_router)
router.include_router(health_router)
router.include_router(voice_router)
