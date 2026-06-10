"""KisanMitra AI — Full Import Chain Verification"""
import sys
sys.path.insert(0, ".")
errors = []

# 1. Core framework
try:
    import fastapi, uvicorn, pydantic
    print(f"[OK] FastAPI {fastapi.__version__}, Uvicorn {uvicorn.__version__}, Pydantic {pydantic.__version__}")
except ImportError as e:
    errors.append(f"Core: {e}")
    print(f"[FAIL] Core: {e}")

# 2. Database (Firestore via firebase-admin)
try:
    import firebase_admin
    from firebase_admin import firestore
    print(f"[OK] firebase-admin {firebase_admin.__version__}")
except ImportError as e:
    errors.append(f"DB: {e}")
    print(f"[FAIL] DB: {e}")

# 3. LangChain + RAG
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_core.documents import Document
    print("[OK] LangChain + Chroma + HuggingFaceEmbeddings (standalone packages)")
except ImportError as e:
    errors.append(f"LangChain: {e}")
    print(f"[FAIL] LangChain: {e}")

# 4. Firebase
try:
    import firebase_admin
    print(f"[OK] firebase-admin {firebase_admin.__version__}")
except ImportError as e:
    errors.append(f"Firebase: {e}")
    print(f"[FAIL] Firebase: {e}")

# 5. Data ingestion deps
try:
    import fitz, pdfplumber, apscheduler, httpx, bs4
    print("[OK] PyMuPDF, pdfplumber, APScheduler, httpx, bs4")
except ImportError as e:
    errors.append(f"Ingestion deps: {e}")
    print(f"[FAIL] Ingestion deps: {e}")

# 6. App imports — the critical chain
print()
print("--- App Import Chain ---")

try:
    from app.core.config import settings
    print(f"[OK] config.py (Firebase enabled: {settings.firebase_enabled})")
except Exception as e:
    errors.append(f"config: {e}")
    print(f"[FAIL] config: {e}")

try:
    from app.services.rag_pipeline import KnowledgeBaseManager
    kb = KnowledgeBaseManager()
    has_loc = hasattr(kb, "search_with_location")
    print(f"[OK] rag_pipeline.py (search_with_location: {has_loc})")
except Exception as e:
    errors.append(f"rag_pipeline: {e}")
    print(f"[FAIL] rag_pipeline: {e}")

try:
    from app.services.chat_orchestrator import ChatOrchestrator
    print("[OK] chat_orchestrator.py")
except Exception as e:
    errors.append(f"chat_orchestrator: {e}")
    print(f"[FAIL] chat_orchestrator: {e}")

try:
    from app.services.data_ingestion.scheduler import run_ingestion
    from app.services.data_ingestion.open_meteo_fetcher import OpenMeteoFetcher
    from app.services.data_ingestion.crida_scraper import CRIDAScraper
    from app.services.data_ingestion.firebase_store import get_firebase_store
    print("[OK] Data ingestion pipeline (all 4 modules)")
except Exception as e:
    errors.append(f"ingestion: {e}")
    print(f"[FAIL] ingestion: {e}")

# 7. Try importing the main app
try:
    from app.main import app
    print("[OK] app.main (FastAPI app created)")
except Exception as e:
    errors.append(f"app.main: {e}")
    print(f"[FAIL] app.main: {e}")

print()
if errors:
    print(f"RESULT: {len(errors)} FAILURES")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("RESULT: ALL IMPORTS PASSED - ZERO ERRORS")
