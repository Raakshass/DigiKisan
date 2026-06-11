import os
from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables / .env file.
    All secrets MUST be provided via environment — no hardcoded defaults for production.
    """

    # --- OpenRouter AI (LLM Provider) ---
    # Get free API key at: https://openrouter.ai/keys (no credit card required)
    # Default model (100% free): google/gemma-4-31b-it:free
    # Alternatives: meta-llama/llama-3.3-70b-instruct:free, qwen/qwen3-coder:free
    openrouter_api_key: str = ""
    openrouter_api_key_2: str = ""  # Second key for round-robin rate-limit avoidance
    openrouter_model: str = "google/gemma-4-31b-it:free"

    # --- HF Inference API (Primary LLM Provider) ---
    # Token with "Make calls to Inference Providers" permission
    hf_inference_token: str = ""

    # --- JWT Authentication ---
    # SECURITY: Generate via: python -c "import secrets; print(secrets.token_urlsafe(64))"
    jwt_secret_key: str = "INSECURE-DEV-ONLY-CHANGE-IN-PRODUCTION"

    # --- MongoDB ---
    # Local: mongodb://localhost:27017 | Atlas: mongodb+srv://user:pass@cluster.mongodb.net
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_dbname: str = "kisanmitra"

    # --- Sarvam AI (Voice/Translation) ---
    sarvam_api_key: Optional[str] = None

    # --- data.gov.in (Market Prices — fastest source) ---
    data_gov_api_key: Optional[str] = None

    # --- Redis (Caching) ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # --- CORS ---
    cors_origins: str = "http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # --- Model Paths (relative to backend/ directory) ---
    text_classifier_dir: str = "models/text_classifier"
    image_classifier_checkpoint: str = "models/image_classifier/best_model.pth"
    image_classifier_classes: str = "models/image_classifier/class_names.json"

    # --- Data Files (relative to backend/ directory) ---
    commodity_mappings_csv: str = "commodity_mappings.csv"
    district_mappings_csv: str = "up_districts.csv"

    # --- Firebase Admin SDK (RAG Data Pipeline) ---
    # Path to Firebase service account JSON (download from Firebase Console → Project Settings → Service Accounts)
    # Free tier (Spark): 5 GB Storage, 1 GB Firestore, 50K reads/day
    firebase_service_account: Optional[str] = None
    firebase_storage_bucket: str = ""  # e.g. "kisanmitra-app.appspot.com"

    # --- Data Ingestion (Monthly RAG Refresh) ---
    # Target states for contingency document scraping
    ingestion_target_states: str = "UP,MP,MH,PB,KA"
    # Cron: day of month to run ingestion (1 = 1st of each month)
    ingestion_day_of_month: int = 1
    # Local fallback directory when Firebase is unavailable
    ingestion_local_fallback: str = "knowledge_base"

    @property
    def target_states_list(self) -> list:
        """Parse comma-separated target states."""
        return [s.strip() for s in self.ingestion_target_states.split(",") if s.strip()]

    @property
    def firebase_enabled(self) -> bool:
        """Check if Firebase is configured."""
        return bool(self.firebase_service_account and self.firebase_storage_bucket)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"  # Allow extra fields from .env without crashing


# Resolve .env path relative to the backend directory
# __file__ = backend/app/core/config.py → dirname x3 = backend/
_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_env_path = os.path.join(_backend_dir, ".env")

# Only load settings if .env exists or env vars are set
try:
    settings = Settings(_env_file=_env_path if os.path.exists(_env_path) else None)
except Exception as e:
    print(f"⚠️  Configuration error: {e}")
    print(f"   Make sure you have a .env file at: {_env_path}")
    print(f"   Or set environment variables. See backend/.env.example for reference.")
    raise
