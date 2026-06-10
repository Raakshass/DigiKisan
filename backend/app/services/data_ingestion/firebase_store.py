"""
KisanMitra AI — Firebase Storage Layer
=====================================
Handles all Firebase interactions for the data ingestion pipeline:
- Cloud Storage: Upload/download knowledge base documents (.md files)
- Firestore: Log ingestion metadata (state, district, source, timestamp)

Architecture:
    Scrapers → IngestedDocument → FirebaseStore.upload() → Cloud Storage + Firestore
    RAG Re-indexer → FirebaseStore.download_state() → local temp → ChromaDB

Graceful degradation:
    If Firebase is not configured (no service account), falls back to local disk.
    The app never crashes — it just uses the existing static knowledge_base/ files.
"""
import os
import json
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from pathlib import Path

from app.core.config import settings

# Firebase Admin SDK — optional import
_firebase_initialized = False
_firestore_client = None
_storage_bucket = None

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, storage
    _FIREBASE_SDK_AVAILABLE = True
except ImportError:
    _FIREBASE_SDK_AVAILABLE = False
    print("⚠️ firebase-admin not installed. Run: pip install firebase-admin")


def _init_firebase():
    """Initialize Firebase Admin SDK (once). Thread-safe via GIL."""
    global _firebase_initialized, _firestore_client, _storage_bucket

    if _firebase_initialized:
        return

    if not _FIREBASE_SDK_AVAILABLE:
        print("⚠️ Firebase SDK not available — using local fallback")
        _firebase_initialized = True
        return

    if not settings.firebase_enabled:
        print("⚠️ Firebase not configured (FIREBASE_SERVICE_ACCOUNT or FIREBASE_STORAGE_BUCKET missing)")
        print("   Using local fallback: knowledge_base/")
        _firebase_initialized = True
        return

    try:
        # Resolve service account path relative to backend dir
        # Resolve relative to backend/ root
        # __file__ = backend/app/services/data_ingestion/firebase_store.py
        # dirname x4 = backend/
        sa_path = settings.firebase_service_account
        if not os.path.isabs(sa_path):
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            sa_path = os.path.join(backend_dir, sa_path)

        if not os.path.exists(sa_path):
            print(f"⚠️ Firebase service account not found: {sa_path}")
            _firebase_initialized = True
            return

        cred = credentials.Certificate(sa_path)
        firebase_admin.initialize_app(cred, {
            "storageBucket": settings.firebase_storage_bucket,
        })

        _firestore_client = firestore.client()
        _storage_bucket = storage.bucket()

        print(f"✅ Firebase initialized (bucket: {settings.firebase_storage_bucket})")
        _firebase_initialized = True

    except Exception as e:
        print(f"⚠️ Firebase init failed: {e}")
        _firebase_initialized = True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class FirebaseStore:
    """
    Dual-mode storage: Firebase Cloud Storage + Firestore when configured,
    local disk fallback when not.
    """

    # Cloud Storage paths
    _STORAGE_PREFIX = "knowledge_base"
    # Firestore collection
    _FIRESTORE_COLLECTION = "ingestion_logs"
    _FIRESTORE_DOCS_COLLECTION = "knowledge_documents"

    def __init__(self):
        _init_firebase()
        # __file__ = backend/app/services/data_ingestion/firebase_store.py → dirname x4 = backend/
        self._backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

    @property
    def is_firebase_active(self) -> bool:
        """Check if Firebase is actually connected (not just configured)."""
        return _storage_bucket is not None and _firestore_client is not None

    # -------------------------------------------------------------------
    # Upload
    # -------------------------------------------------------------------
    async def upload_document(
        self,
        content: str,
        state: str,
        district: Optional[str],
        source_name: str,
        category: str,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Upload a parsed document (.md content) to storage + log metadata.

        Args:
            content: Markdown text content
            state: State code (e.g., "UP")
            district: District name or None for state-level docs
            source_name: Data source identifier (e.g., "crida", "imd", "open_meteo")
            category: Document category (e.g., "contingency", "weather_advisory")
            filename: Target filename (e.g., "lucknow_contingency.md")
            metadata: Extra metadata dict

        Returns:
            {"ok": True, "path": str, "storage": "firebase"|"local"}
        """
        # Build storage path: knowledge_base/{category}/{state}/{filename}
        rel_path = f"{category}/{state}/{filename}"

        doc_metadata = {
            "state": state,
            "district": district or "",
            "source": source_name,
            "category": category,
            "filename": filename,
            "path": rel_path,
            "size_bytes": len(content.encode("utf-8")),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        if self.is_firebase_active:
            return await self._upload_firebase(content, rel_path, doc_metadata)
        else:
            return self._upload_local(content, rel_path, doc_metadata)

    async def _upload_firebase(
        self, content: str, rel_path: str, doc_metadata: Dict
    ) -> Dict[str, Any]:
        """Upload to Firebase Cloud Storage + log to Firestore."""
        try:
            # 1. Upload content to Cloud Storage
            blob_path = f"{self._STORAGE_PREFIX}/{rel_path}"
            blob = _storage_bucket.blob(blob_path)
            blob.upload_from_string(
                content,
                content_type="text/markdown",
                timeout=30,
            )
            print(f"  ☁️  Uploaded: gs://{settings.firebase_storage_bucket}/{blob_path}")

            # 2. Log metadata to Firestore
            doc_ref = _firestore_client.collection(self._FIRESTORE_DOCS_COLLECTION).document(
                rel_path.replace("/", "_")
            )
            doc_ref.set(doc_metadata)

            return {"ok": True, "path": blob_path, "storage": "firebase"}

        except Exception as e:
            print(f"  ❌ Firebase upload failed for {rel_path}: {e}")
            # Fallback to local
            return self._upload_local(content, rel_path, doc_metadata)

    def _upload_local(
        self, content: str, rel_path: str, doc_metadata: Dict
    ) -> Dict[str, Any]:
        """Fallback: write to local knowledge_base/ directory."""
        try:
            kb_dir = os.path.join(self._backend_dir, settings.ingestion_local_fallback)
            full_path = os.path.join(kb_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"  💾 Saved locally: {full_path}")

            # Log to local JSON
            self._log_local_metadata(doc_metadata)

            return {"ok": True, "path": full_path, "storage": "local"}

        except Exception as e:
            print(f"  ❌ Local save failed for {rel_path}: {e}")
            return {"ok": False, "error": str(e), "storage": "failed"}

    def _log_local_metadata(self, doc_metadata: Dict):
        """Append metadata to local _ingestion_log.json as fallback."""
        kb_dir = os.path.join(self._backend_dir, settings.ingestion_local_fallback)
        log_path = os.path.join(kb_dir, "_ingestion_log.json")

        logs = []
        if os.path.exists(log_path):
            try:
                with open(log_path, "r") as f:
                    logs = json.load(f)
            except (json.JSONDecodeError, IOError):
                logs = []

        logs.append(doc_metadata)

        with open(log_path, "w") as f:
            json.dump(logs, f, indent=2, default=str)

    # -------------------------------------------------------------------
    # Download (for RAG re-indexer)
    # -------------------------------------------------------------------
    def download_all_documents(
        self, target_dir: str, states: Optional[List[str]] = None
    ) -> int:
        """
        Download all knowledge base documents to a local directory
        for ChromaDB indexing.

        Args:
            target_dir: Local directory to download to
            states: Optional list of state codes to filter (None = all)

        Returns:
            Number of documents downloaded
        """
        if self.is_firebase_active:
            return self._download_from_firebase(target_dir, states)
        else:
            return self._copy_from_local(target_dir, states)

    def _download_from_firebase(
        self, target_dir: str, states: Optional[List[str]]
    ) -> int:
        """Download from Cloud Storage to local dir."""
        count = 0
        try:
            prefix = f"{self._STORAGE_PREFIX}/"
            blobs = _storage_bucket.list_blobs(prefix=prefix)

            for blob in blobs:
                # Filter by state if specified
                if states:
                    blob_state = self._extract_state_from_path(blob.name)
                    if blob_state and blob_state not in states:
                        continue

                # Build local path
                rel_path = blob.name[len(prefix):]
                local_path = os.path.join(target_dir, rel_path)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                blob.download_to_filename(local_path)
                count += 1

            print(f"📥 Downloaded {count} documents from Firebase")

        except Exception as e:
            print(f"❌ Firebase download failed: {e}")
            # Fallback to local copy
            count = self._copy_from_local(target_dir, states)

        return count

    def _copy_from_local(
        self, target_dir: str, states: Optional[List[str]]
    ) -> int:
        """Copy from local knowledge_base/ to target dir."""
        import shutil
        kb_dir = os.path.join(self._backend_dir, settings.ingestion_local_fallback)

        if not os.path.exists(kb_dir):
            return 0

        count = 0
        for root, _, files in os.walk(kb_dir):
            for f in files:
                if not f.endswith(".md"):
                    continue

                src = os.path.join(root, f)
                rel = os.path.relpath(src, kb_dir)

                # Filter by state
                if states:
                    state_in_path = self._extract_state_from_path(rel)
                    if state_in_path and state_in_path not in states:
                        continue

                dst = os.path.join(target_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                count += 1

        return count

    @staticmethod
    def _extract_state_from_path(path: str) -> Optional[str]:
        """Extract state code from path like 'contingency/UP/lucknow.md'."""
        parts = Path(path).parts
        # State code is typically the second directory in the path
        for p in parts:
            if p.upper() in ("UP", "MP", "MH", "PB", "KA"):
                return p.upper()
        return None

    # -------------------------------------------------------------------
    # Ingestion Logging
    # -------------------------------------------------------------------
    async def log_ingestion_run(
        self,
        source_name: str,
        states_processed: List[str],
        documents_count: int,
        errors: List[str],
        duration_seconds: float,
    ) -> None:
        """Log a completed ingestion run."""
        log_entry = {
            "source": source_name,
            "states": states_processed,
            "documents_count": documents_count,
            "errors": errors,
            "error_count": len(errors),
            "duration_seconds": round(duration_seconds, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "firebase_active": self.is_firebase_active,
        }

        if self.is_firebase_active:
            try:
                _firestore_client.collection(self._FIRESTORE_COLLECTION).add(log_entry)
            except Exception as e:
                print(f"⚠️ Firestore log failed: {e}")
                self._log_local_metadata(log_entry)
        else:
            self._log_local_metadata(log_entry)

        status = "✅" if not errors else "⚠️"
        print(
            f"{status} Ingestion run logged: {source_name} | "
            f"{documents_count} docs | {len(errors)} errors | "
            f"{duration_seconds:.1f}s"
        )

    # -------------------------------------------------------------------
    # Query metadata
    # -------------------------------------------------------------------
    def get_last_ingestion(self, source_name: str) -> Optional[Dict]:
        """Get the most recent ingestion log for a source."""
        if self.is_firebase_active:
            try:
                query = (
                    _firestore_client.collection(self._FIRESTORE_COLLECTION)
                    .where("source", "==", source_name)
                    .order_by("timestamp", direction=firestore.Query.DESCENDING)
                    .limit(1)
                )
                docs = list(query.stream())
                if docs:
                    return docs[0].to_dict()
            except Exception as e:
                print(f"⚠️ Firestore query failed: {e}")

        # Local fallback
        kb_dir = os.path.join(self._backend_dir, settings.ingestion_local_fallback)
        log_path = os.path.join(kb_dir, "_ingestion_log.json")
        if os.path.exists(log_path):
            try:
                with open(log_path, "r") as f:
                    logs = json.load(f)
                for log in reversed(logs):
                    if log.get("source") == source_name:
                        return log
            except Exception:
                pass

        return None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_store: Optional[FirebaseStore] = None


def get_firebase_store() -> FirebaseStore:
    """Get the FirebaseStore singleton."""
    global _store
    if _store is None:
        _store = FirebaseStore()
    return _store
