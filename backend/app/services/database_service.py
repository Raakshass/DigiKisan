"""
Firestore Database Service — Replaces MongoDB
==============================================
Uses Firebase Admin SDK (Firestore) for:
- Chat session storage
- Price data caching
- Query analytics
"""
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
import os

# ---------------------------------------------------------------------------
# Initialize Firebase Admin SDK (once)
# ---------------------------------------------------------------------------
_firebase_app = None
_firestore_client = None


def _init_firebase():
    """Initialize Firebase Admin SDK with service account."""
    global _firebase_app, _firestore_client
    if _firebase_app is not None:
        return _firestore_client

    try:
        # Look for service account in multiple locations
        sa_paths = [
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
            str(Path(__file__).parent.parent.parent / "firebase-sa.json"),
            "/etc/secrets/firebase-sa.json",  # Render secrets
        ]

        cred = None
        for path in sa_paths:
            if path and Path(path).exists():
                cred = credentials.Certificate(path)
                print(f"✅ Firebase SA loaded from: {path}")
                break

        if cred is None:
            # Try default credentials (Cloud Run, etc.)
            cred = credentials.ApplicationDefault()
            print("✅ Firebase using application default credentials")

        _firebase_app = firebase_admin.initialize_app(cred)
        _firestore_client = firestore.client()
        print("✅ Firestore initialized")
        return _firestore_client

    except Exception as e:
        print(f"⚠️ Firestore init failed: {e}")
        return None


def get_firestore():
    """Get Firestore client (lazy init)."""
    global _firestore_client
    if _firestore_client is None:
        _init_firebase()
    return _firestore_client


# ---------------------------------------------------------------------------
# Session Service (replaces MongoDB sessions)
# ---------------------------------------------------------------------------
class SessionService:
    def __init__(self):
        self._collection_name = "sessions"

    @property
    def _col(self):
        db = get_firestore()
        return db.collection(self._collection_name) if db else None

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        try:
            if not session_id or not self._col:
                return None
            doc = self._col.document(session_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            print(f"❌ Error getting session: {e}")
            return None

    async def create_session(self, session_model) -> bool:
        try:
            if not self._col:
                return False
            data = session_model.dict() if hasattr(session_model, 'dict') else dict(session_model)
            data['created_at'] = datetime.now().isoformat()
            sid = data.get('session_id', str(datetime.now().timestamp()))
            self._col.document(sid).set(data)
            print(f"✅ Session created: {sid}")
            return True
        except Exception as e:
            print(f"❌ Error creating session: {e}")
            return False

    async def update_session(self, session_id: str, update_data: Dict[str, Any]) -> bool:
        try:
            if not session_id or not self._col:
                return False

            doc_ref = self._col.document(session_id)

            # Flatten MongoDB-style operators into Firestore-compatible updates
            flat_update = {'last_activity': datetime.now().isoformat()}

            # Handle $set
            if '$set' in update_data:
                flat_update.update(update_data['$set'])

            # Handle $push (append to array)
            if '$push' in update_data:
                doc = doc_ref.get()
                existing = doc.to_dict() if doc.exists else {}
                for field, value in update_data['$push'].items():
                    arr = existing.get(field, [])
                    arr.append(value)
                    flat_update[field] = arr

            # Handle $inc (increment)
            if '$inc' in update_data:
                doc = doc_ref.get()
                existing = doc.to_dict() if doc.exists else {}
                for field, value in update_data['$inc'].items():
                    flat_update[field] = existing.get(field, 0) + value

            # Regular fields
            regular = {k: v for k, v in update_data.items() if not k.startswith('$')}
            flat_update.update(regular)

            doc_ref.set(flat_update, merge=True)
            return True

        except Exception as e:
            print(f"❌ Error updating session: {e}")
            return False


# ---------------------------------------------------------------------------
# Price Data Service (replaces MongoDB price_data)
# ---------------------------------------------------------------------------
class PriceDataService:
    def __init__(self):
        self._collection_name = "price_data"

    @property
    def _col(self):
        db = get_firestore()
        return db.collection(self._collection_name) if db else None

    async def get_cached_prices(self, commodity_code: str, district_code: str,
                                date: str, max_age_hours: int = 2):
        try:
            if not self._col:
                return None

            cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
            docs = (
                self._col
                .where("commodity_code", "==", commodity_code)
                .where("district_code", "==", district_code)
                .where("date", "==", date)
                .where("scraped_at", ">=", cutoff)
                .stream()
            )
            records = [doc.to_dict() for doc in docs]
            if records:
                import pandas as pd
                print(f"📦 Retrieved {len(records)} cached price records")
                return pd.DataFrame(records)
            return None
        except Exception as e:
            print(f"❌ Error getting cached prices: {e}")
            return None

    async def cache_price_data(self, price_df, commodity_code: str,
                               district_code: str, date: str) -> int:
        try:
            if not self._col:
                return 0

            cached_count = 0
            now = datetime.now().isoformat()
            for _, row in price_df.iterrows():
                price_doc = {
                    "commodity_code": commodity_code,
                    "commodity_name": row.get('Commodity', 'Unknown'),
                    "district_code": district_code,
                    "district_name": row.get('District', 'Unknown'),
                    "market_name": row.get('Market', 'Unknown'),
                    "date": date,
                    "modal_price": row.get('Modal', 0.0),
                    "min_price": row.get('Min', 0.0),
                    "max_price": row.get('Max', 0.0),
                    "data_source": "agmarknet",
                    "scraped_at": now,
                    "quality_score": 1.0,
                }
                self._col.add(price_doc)
                cached_count += 1
            print(f"📦 Cached {cached_count} price records")
            return cached_count
        except Exception as e:
            print(f"❌ Error caching price data: {e}")
            return 0


# ---------------------------------------------------------------------------
# Analytics Service (replaces MongoDB query_analytics)
# ---------------------------------------------------------------------------
class AnalyticsService:
    def __init__(self):
        self._collection_name = "query_analytics"

    @property
    def _col(self):
        db = get_firestore()
        return db.collection(self._collection_name) if db else None

    async def log_query(self, analytics_data) -> bool:
        try:
            if not self._col:
                return False
            data = analytics_data.dict() if hasattr(analytics_data, 'dict') else dict(analytics_data)
            data['timestamp'] = datetime.now().isoformat()
            self._col.add(data)
            print(f"📊 Analytics logged for {data.get('commodity', '?')} in {data.get('district', '?')}")
            return True
        except Exception as e:
            print(f"❌ Error logging analytics: {e}")
            return False

    async def get_popular_queries(self, days_back: int = 7) -> List[Dict[str, Any]]:
        try:
            if not self._col:
                return []
            cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
            docs = (
                self._col
                .where("timestamp", ">=", cutoff)
                .where("success", "==", True)
                .order_by("timestamp")
                .limit(100)
                .stream()
            )
            # Aggregate in Python (Firestore doesn't have $group)
            counts = {}
            for doc in docs:
                d = doc.to_dict()
                key = f"{d.get('commodity', '?')}|{d.get('district', '?')}"
                counts[key] = counts.get(key, 0) + 1

            results = [
                {"_id": {"commodity": k.split("|")[0], "district": k.split("|")[1]}, "count": v}
                for k, v in sorted(counts.items(), key=lambda x: -x[1])[:10]
            ]
            return results
        except Exception as e:
            print(f"❌ Error getting popular queries: {e}")
            return []

    async def get_query_stats(self, days_back: int = 30) -> Dict[str, Any]:
        try:
            if not self._col:
                return {"error": "Analytics not available"}
            # Simple stats
            return {
                "period_days": days_back,
                "status": "firestore_backed",
            }
        except Exception as e:
            return {"error": str(e)}
