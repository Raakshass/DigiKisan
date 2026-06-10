"""
KisanMitra AI — Data Ingestion Scheduler
==========================================
Monthly cron job that runs all data source scrapers and refreshes
the RAG knowledge base.

Architecture:
    APScheduler cron (1st of month, 00:00 UTC)
        → CRIDAScraper.ingest(states)      # Contingency PDFs
        → OpenMeteoFetcher.ingest(states)   # Weather data
        → Re-index ChromaDB                 # RAG refresh

Can also be triggered manually via:
    POST /api/admin/trigger-ingestion

Usage:
    from app.services.data_ingestion.scheduler import start_scheduler
    start_scheduler()  # Call once at app startup
"""
import asyncio
import time
import traceback
from datetime import datetime, timezone
from typing import List, Optional

from app.core.config import settings
from app.services.data_ingestion.base_source import IngestionResult
from app.services.data_ingestion.firebase_store import get_firebase_store


# ---------------------------------------------------------------------------
# Source registry — add new sources here
# ---------------------------------------------------------------------------
def _get_sources():
    """
    Lazily import and instantiate all data sources.
    This avoids circular imports and heavy init at module load.
    """
    sources = []

    try:
        from app.services.data_ingestion.crida_scraper import CRIDAScraper
        sources.append(CRIDAScraper())
    except ImportError as e:
        print(f"⚠️ CRIDA scraper unavailable: {e}")

    try:
        from app.services.data_ingestion.open_meteo_fetcher import OpenMeteoFetcher
        sources.append(OpenMeteoFetcher())
    except ImportError as e:
        print(f"⚠️ Open-Meteo fetcher unavailable: {e}")

    return sources


# ---------------------------------------------------------------------------
# Main ingestion pipeline
# ---------------------------------------------------------------------------
async def run_ingestion(
    states: Optional[List[str]] = None,
    force: bool = False,
) -> List[IngestionResult]:
    """
    Run the full data ingestion pipeline.

    Args:
        states: List of state codes to process. Defaults to config.
        force: If True, bypass the refresh_interval_days skip logic.

    Returns:
        List of IngestionResult from each source.
    """
    target_states = states or settings.target_states_list
    sources = _get_sources()

    if not sources:
        print("❌ No data sources available — check imports")
        return []

    print(f"\n{'='*70}")
    print(f"🚀 KisanMitra AI — Data Ingestion Pipeline")
    print(f"   Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"   States: {', '.join(target_states)}")
    print(f"   Sources: {', '.join(s.name for s in sources)}")
    print(f"   Force: {force}")
    print(f"{'='*70}")

    start = time.time()
    results = []

    for source in sources:
        try:
            # Override skip logic if forced
            if force:
                source.refresh_interval_days = 0

            result = await source.ingest(target_states)
            results.append(result)

        except Exception as e:
            print(f"❌ Source '{source.name}' crashed: {e}")
            traceback.print_exc()
            results.append(IngestionResult(
                source_name=source.name,
                states_processed=target_states,
                errors=[f"Fatal: {str(e)}"],
                duration_seconds=0,
            ))

    # Print summary
    total_time = time.time() - start
    total_docs = sum(r.documents_ingested for r in results)
    total_errors = sum(len(r.errors) for r in results)

    print(f"\n{'='*70}")
    print(f"📊 Ingestion Complete")
    print(f"   Total documents: {total_docs}")
    print(f"   Total errors: {total_errors}")
    print(f"   Total time: {total_time:.1f}s")
    print(f"   Results:")
    for r in results:
        print(f"     {r.summary}")
    print(f"{'='*70}\n")

    return results


# ---------------------------------------------------------------------------
# APScheduler integration
# ---------------------------------------------------------------------------
_scheduler = None


def start_scheduler():
    """
    Start the monthly ingestion scheduler.
    Runs on the configured day of month at 00:00 UTC.

    Call this once during FastAPI lifespan startup.
    """
    global _scheduler

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        print("⚠️ APScheduler not installed — monthly ingestion disabled")
        print("   Run: pip install apscheduler")
        return

    if _scheduler is not None:
        print("⚠️ Scheduler already running")
        return

    _scheduler = AsyncIOScheduler()

    # Monthly cron: run on configured day at 00:00 UTC
    day = settings.ingestion_day_of_month
    _scheduler.add_job(
        _scheduled_ingestion,
        CronTrigger(day=day, hour=0, minute=0),
        id="monthly_ingestion",
        name=f"Monthly data ingestion (day {day})",
        replace_existing=True,
    )

    # Also run Open-Meteo weekly (weather changes fast)
    _scheduler.add_job(
        _scheduled_weather_update,
        CronTrigger(day_of_week="mon", hour=6, minute=0),
        id="weekly_weather",
        name="Weekly weather advisory update",
        replace_existing=True,
    )

    _scheduler.start()
    print(f"⏰ Scheduler started:")
    print(f"   Monthly ingestion: day {day} at 00:00 UTC")
    print(f"   Weekly weather: Monday 06:00 UTC")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        print("⏰ Scheduler stopped")


async def _scheduled_ingestion():
    """Scheduled monthly ingestion — runs all sources."""
    print("⏰ Scheduled monthly ingestion triggered")
    await run_ingestion()


async def _scheduled_weather_update():
    """Scheduled weekly weather update — Open-Meteo only."""
    print("⏰ Scheduled weekly weather update triggered")
    try:
        from app.services.data_ingestion.open_meteo_fetcher import OpenMeteoFetcher
        fetcher = OpenMeteoFetcher()
        fetcher.refresh_interval_days = 0  # Force refresh
        await fetcher.ingest(settings.target_states_list)
    except Exception as e:
        print(f"❌ Weekly weather update failed: {e}")
