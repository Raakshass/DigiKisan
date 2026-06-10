"""
KisanMitra AI — Base Data Source
==============================
Abstract base class for all data ingestion sources.
Every scraper/fetcher (CRIDA, IMD, Open-Meteo, state portals) inherits from this.

Contract:
    1. fetch() → downloads/scrapes raw data for given states
    2. process() → converts raw data into IngestedDocument objects
    3. ingest() → orchestrates fetch → process → upload to FirebaseStore

All sources MUST:
    - Be 100% free (no paid APIs)
    - Handle errors gracefully (log and continue, never crash)
    - Tag every document with state, district, category metadata
    - Support incremental updates (skip already-ingested docs)
"""
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from app.services.data_ingestion.firebase_store import get_firebase_store, FirebaseStore


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------
@dataclass
class IngestedDocument:
    """
    A single document produced by a data source, ready for storage.

    This is the universal output format. Every scraper produces these.
    The FirebaseStore handles where they get saved.
    """
    # Content
    content: str                    # Markdown text
    filename: str                   # e.g. "lucknow_contingency.md"

    # Location tagging
    state: str                      # State code: "UP", "MP", etc.
    district: Optional[str] = None  # District name or None for state-level

    # Classification
    category: str = ""              # "contingency", "weather_advisory", "crop_stats"
    source: str = ""                # "crida", "open_meteo", "state_portal"

    # Extra metadata (scrape URL, PDF page count, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate required fields."""
        if not self.content or not self.content.strip():
            raise ValueError(f"IngestedDocument '{self.filename}' has empty content")
        if not self.state:
            raise ValueError(f"IngestedDocument '{self.filename}' missing state code")
        if not self.filename:
            raise ValueError("IngestedDocument missing filename")


@dataclass
class IngestionResult:
    """Summary of an ingestion run for a single source."""
    source_name: str
    states_processed: List[str]
    documents_ingested: int = 0
    documents_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    started_at: str = ""
    completed_at: str = ""

    @property
    def success(self) -> bool:
        return self.documents_ingested > 0 and len(self.errors) == 0

    @property
    def summary(self) -> str:
        status = "✅" if self.success else ("⚠️" if self.documents_ingested > 0 else "❌")
        return (
            f"{status} {self.source_name}: "
            f"{self.documents_ingested} ingested, "
            f"{self.documents_skipped} skipped, "
            f"{len(self.errors)} errors, "
            f"{self.duration_seconds:.1f}s"
        )


# ---------------------------------------------------------------------------
# Abstract Base Class
# ---------------------------------------------------------------------------
class DataSource(ABC):
    """
    Base class for all data ingestion sources.

    Subclasses implement:
        - name: Human-readable source identifier
        - category: Document category for RAG filtering
        - fetch_documents(): The actual scraping/API logic

    The base class handles:
        - Error handling and retry
        - Upload to FirebaseStore
        - Ingestion logging
        - Skip logic (don't re-fetch recently ingested docs)
    """

    # Subclasses MUST override these
    name: str = "unknown"
    category: str = "general"

    # How many days between re-fetches (30 = monthly)
    refresh_interval_days: int = 30

    # Max documents per state per run (safety limit)
    max_docs_per_state: int = 50

    # HTTP request settings
    request_timeout: int = 30
    request_delay: float = 1.0  # Seconds between requests (be polite to gov servers)

    def __init__(self):
        self._store: FirebaseStore = get_firebase_store()

    # -------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------
    async def ingest(self, states: List[str]) -> IngestionResult:
        """
        Run a full ingestion cycle for the given states.

        This is the ONLY method callers should use. It handles:
        1. Check if source needs refresh
        2. Fetch documents for each state
        3. Upload to Firebase/local
        4. Log results

        Args:
            states: List of state codes to ingest (e.g., ["UP", "MP"])

        Returns:
            IngestionResult with counts and errors
        """
        result = IngestionResult(
            source_name=self.name,
            states_processed=states,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        start_time = time.time()
        print(f"\n{'='*60}")
        print(f"🔄 Starting ingestion: {self.name}")
        print(f"   States: {', '.join(states)}")
        print(f"{'='*60}")

        # Check if we need to refresh
        if self._should_skip():
            print(f"⏭️  {self.name} was recently ingested — skipping")
            result.documents_skipped = -1  # Signal: skipped entirely
            result.duration_seconds = time.time() - start_time
            result.completed_at = datetime.now(timezone.utc).isoformat()
            return result

        # Fetch and upload for each state
        for state in states:
            try:
                print(f"\n📍 Processing state: {state}")
                documents = await self.fetch_documents(state)

                if not documents:
                    print(f"   ℹ️ No documents found for {state}")
                    continue

                # Cap at safety limit
                if len(documents) > self.max_docs_per_state:
                    print(f"   ⚠️ Capping {len(documents)} docs to {self.max_docs_per_state}")
                    documents = documents[:self.max_docs_per_state]

                # Upload each document
                for doc in documents:
                    try:
                        upload_result = await self._store.upload_document(
                            content=doc.content,
                            state=doc.state,
                            district=doc.district,
                            source_name=self.name,
                            category=doc.category or self.category,
                            filename=doc.filename,
                            metadata=doc.metadata,
                        )
                        if upload_result.get("ok"):
                            result.documents_ingested += 1
                        else:
                            result.errors.append(
                                f"{doc.filename}: {upload_result.get('error', 'unknown')}"
                            )
                    except Exception as e:
                        error_msg = f"{doc.filename}: {str(e)}"
                        result.errors.append(error_msg)
                        print(f"   ❌ Upload failed: {error_msg}")

            except Exception as e:
                error_msg = f"State {state}: {str(e)}"
                result.errors.append(error_msg)
                print(f"   ❌ State processing failed: {error_msg}")
                traceback.print_exc()

        # Log the run
        result.duration_seconds = round(time.time() - start_time, 2)
        result.completed_at = datetime.now(timezone.utc).isoformat()

        await self._store.log_ingestion_run(
            source_name=self.name,
            states_processed=states,
            documents_count=result.documents_ingested,
            errors=result.errors,
            duration_seconds=result.duration_seconds,
        )

        print(f"\n{result.summary}")
        return result

    # -------------------------------------------------------------------
    # Abstract method — subclasses implement this
    # -------------------------------------------------------------------
    @abstractmethod
    async def fetch_documents(self, state: str) -> List[IngestedDocument]:
        """
        Fetch and parse documents for a single state.

        Args:
            state: State code (e.g., "UP")

        Returns:
            List of IngestedDocument objects, ready for upload.
            Return empty list if no data available.

        MUST:
            - Handle network errors gracefully
            - Respect request_delay between HTTP calls
            - Tag every document with correct state/district
            - Never raise — return empty list on failure
        """
        ...

    # -------------------------------------------------------------------
    # Skip logic
    # -------------------------------------------------------------------
    def _should_skip(self) -> bool:
        """Check if this source was recently ingested (within refresh_interval_days)."""
        last_run = self._store.get_last_ingestion(self.name)
        if not last_run:
            return False

        try:
            last_ts = datetime.fromisoformat(last_run["timestamp"])
            # Make timezone-aware if not already
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - last_ts).days
            return age_days < self.refresh_interval_days
        except (KeyError, ValueError):
            return False

    # -------------------------------------------------------------------
    # Utility for subclasses
    # -------------------------------------------------------------------
    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Convert a district/state name to a safe filename."""
        return (
            name.lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace("(", "")
            .replace(")", "")
            .replace("/", "_")
            .replace(".", "")
            .strip("_")
            + ".md"
        )

    @staticmethod
    def build_document_header(
        title: str,
        state: str,
        district: Optional[str] = None,
        source_url: Optional[str] = None,
        last_updated: Optional[str] = None,
    ) -> str:
        """Build a standard markdown header for ingested documents."""
        lines = [
            f"# {title}",
            "",
            f"**State:** {state}",
        ]
        if district:
            lines.append(f"**District:** {district}")
        if source_url:
            lines.append(f"**Source:** {source_url}")
        lines.append(
            f"**Ingested:** {last_updated or datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)
