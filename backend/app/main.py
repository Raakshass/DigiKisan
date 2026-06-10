"""
KisanMitra AI Backend — Application Entry Point
=============================================
FastAPI application with proper middleware, lifecycle management, and structured logging.
"""
import json
import time
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .api.routes import router
from .core.config import settings
from .core.db import connect_to_mongo, close_mongo_connection


# ---------------------------------------------------------------------------
# Application lifecycle (replaces deprecated @app.on_event)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    print("🚀 Starting KisanMitra AI Backend v1.0.0...")

    # Validate critical config
    if not settings.openrouter_api_key:
        print("[WARN] OPENROUTER_API_KEY not set -- chatbot will return fallback responses")
        print("   Get a free key at: https://openrouter.ai/keys")
    
    # Connect to Firestore (non-fatal if unavailable)
    try:
        await connect_to_mongo()
        print("✅ Firestore connected")
    except Exception as e:
        print(f"⚠️  Firestore unavailable: {e}")
        print("   Session storage and analytics will be disabled. Chat still works.")

    # Initialize RAG knowledge base in background thread (non-blocking)
    def _init_rag():
        try:
            from .services.rag_pipeline import get_knowledge_base
            kb = get_knowledge_base()
            if kb.is_available:
                print("✅ RAG knowledge base ready")
            else:
                print("⚠️ RAG knowledge base unavailable (will use Gemini-only mode)")
        except Exception as e:
            print(f"⚠️ RAG init error (non-fatal): {e}")

    rag_thread = threading.Thread(target=_init_rag, daemon=True)
    # Disabled for Render 512MB Free Tier — let it lazy-load on first request
    # rag_thread.start()

    # Start monthly data ingestion scheduler
    try:
        from .services.data_ingestion.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        print(f"⚠️ Ingestion scheduler init failed (non-fatal): {e}")

    print("✅ All services initialized successfully!")
    yield
    print("🔌 Shutting down KisanMitra AI Backend...")

    # Stop scheduler
    try:
        from .services.data_ingestion.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass

    await close_mongo_connection()
    print("✅ Shutdown complete")


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="KisanMitra AI Backend API",
    description=(
        "🌱 **KisanMitra AI Backend API**\n\n"
        "Production-grade agricultural assistance platform providing:\n"
        "- 💬 RAG-augmented AI chatbot with agricultural knowledge base\n"
        "- 🔍 Real-time market price data (async, no Selenium)\n"
        "- 🌿 Crop disease detection with ResNet50 + AI consultation\n"
        "- 📊 Session analytics and price caching (Firestore)\n"
        "- 🎙️ Voice STT/TTS via Sarvam AI\n"
        "- 🔐 Firebase Authentication\n\n"
        "Built with FastAPI, LangChain, ChromaDB, Firestore, and OpenRouter (DeepSeek)."
    ),
    version="1.0.0",
    lifespan=lifespan,
    contact={"name": "KisanMitra AI Support", "email": "support@kisanmitra.ai"},
    license_info={"name": "MIT License", "url": "https://opensource.org/licenses/MIT"},
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ---------------------------------------------------------------------------
# CORS — use config-driven origins, NOT wildcard "*"
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request logging middleware (debug-mode only, for /chat/ and /disease/ endpoints)
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log request/response for debugging. Only active in development mode."""
    should_log = settings.debug and any(
        seg in str(request.url) for seg in ("/chat/", "/disease/")
    )

    if not should_log:
        return await call_next(request)

    start_time = time.time()
    req_body = await request.body()

    print(f"\n{'=' * 60}")
    print(f"🔍 REQUEST: {request.method} {request.url}")
    print(f"🕐 Time: {time.strftime('%H:%M:%S')}")

    try:
        if req_body:
            print(f"📤 BODY: {json.loads(req_body.decode())}")
    except json.JSONDecodeError:
        print(f"📤 BODY (raw): {req_body[:200]}")

    response = await call_next(request)

    # Read response body for logging, then reconstruct the response
    resp_body = b""
    async for chunk in response.body_iterator:
        resp_body += chunk

    process_time = time.time() - start_time
    print(f"📥 STATUS: {response.status_code} | ⏱️ {process_time:.3f}s")
    print(f"{'=' * 60}\n")

    return Response(
        content=resp_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a clean JSON error."""
    print(f"❌ Unhandled exception on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


# ---------------------------------------------------------------------------
# Root health check
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "KisanMitra AI Backend API is running!",
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/docs",
        "environment": settings.environment,
    }


# ---------------------------------------------------------------------------
# Include API routes
# ---------------------------------------------------------------------------
app.include_router(router, prefix="/api")
