from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.price_data import PriceDataModel, UserSessionModel, QueryAnalyticsModel
from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime, timedelta

class SessionService:
    def __init__(self):
        self.db = None
        self.collection = None

    async def _get_db(self):
        """Get database connection from dependency injection context"""
        # This will be set by the route handler
        if self.db is None:
            raise RuntimeError("Database not initialized. Use dependency injection.")
        return self.db
    
    def set_db(self, db: AsyncIOMotorDatabase):
        """Set database instance from dependency injection"""
        self.db = db
        self.collection = db.user_sessions

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by session_id"""
        try:
            if not session_id:
                return None
            db = await self._get_db()
            session_doc = await self.collection.find_one({"session_id": session_id})
            return session_doc
        except Exception as e:
            print(f"❌ Error getting session: {e}")
            return None

    async def create_session(self, session_model: UserSessionModel) -> bool:
        """Create a new session"""
        try:
            db = await self._get_db()
            session_dict = session_model.dict()
            session_dict['created_at'] = datetime.now()
            result = await self.collection.insert_one(session_dict)
            print(f"✅ Session created: {session_model.session_id}")
            return result.inserted_id is not None
        except Exception as e:
            print(f"❌ Error creating session: {e}")
            return False

    async def update_session(self, session_id: str, update_data: Dict[str, Any]) -> bool:
        """Update session with proper MongoDB operators"""
        try:
            if not session_id:
                return False
            
            db = await self._get_db()
            
            # Build update query properly
            update_query = {}
            
            # Handle $push operations
            if "$push" in update_data:
                update_query["$push"] = update_data["$push"]
                
            # Handle $inc operations  
            if "$inc" in update_data:
                update_query["$inc"] = update_data["$inc"]
            
            # Handle regular field updates
            regular_fields = {k: v for k, v in update_data.items() if not k.startswith('$')}
            if regular_fields:
                update_query["$set"] = regular_fields
            
            # Always update last_activity
            if "$set" not in update_query:
                update_query["$set"] = {}
            update_query["$set"]["last_activity"] = datetime.now()

            result = await self.collection.update_one(
                {"session_id": session_id}, 
                update_query,
                upsert=True
            )
            
            return result.modified_count > 0 or result.upserted_id is not None
            
        except Exception as e:
            print(f"❌ Error updating session: {e}")
            return False

class PriceDataService:
    def __init__(self):
        self.db = None
        self.collection = None

    def set_db(self, db: AsyncIOMotorDatabase):
        """Set database instance from dependency injection"""
        self.db = db
        self.collection = db.price_data

    async def get_cached_prices(self, commodity_code: str, district_code: str, 
                              date: str, max_age_hours: int = 2) -> Optional[pd.DataFrame]:
        """Get cached price data"""
        try:
            # 🔥 CRITICAL FIX: Use 'is None' instead of 'not self.collection'
            if self.collection is None:
                return None
                
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            cursor = self.collection.find({
                "commodity_code": commodity_code,
                "district_code": district_code, 
                "date": date,
                "scraped_at": {"$gte": cutoff_time}
            })
            documents = await cursor.to_list(length=None)
            if documents:
                df = pd.DataFrame(documents)
                print(f"📦 Retrieved {len(df)} cached price records")
                return df
            return None
        except Exception as e:
            print(f"❌ Error getting cached prices: {e}")
            return None

    async def cache_price_data(self, price_df: pd.DataFrame, commodity_code: str, 
                             district_code: str, date: str) -> int:
        """Cache price data"""
        try:
            # 🔥 CRITICAL FIX: Use 'is None' instead of 'not self.collection'
            if self.collection is None:
                return 0
                
            cached_count = 0
            current_time = datetime.now()
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
                    "scraped_at": current_time,
                    "quality_score": 1.0
                }
                await self.collection.insert_one(price_doc)
                cached_count += 1
            print(f"📦 Cached {cached_count} price records")
            return cached_count
        except Exception as e:
            print(f"❌ Error caching price data: {e}")
            return 0

class AnalyticsService:
    def __init__(self):
        self.db = None
        self.collection = None

    def set_db(self, db: AsyncIOMotorDatabase):
        """Set database instance from dependency injection"""
        self.db = db
        self.collection = db.query_analytics

    async def log_query(self, analytics_data: QueryAnalyticsModel) -> bool:
        """Log query analytics"""
        try:
            # 🔥 CRITICAL FIX: Use 'is None' instead of 'not self.collection'
            if self.collection is None:
                return False
                
            analytics_dict = analytics_data.dict()
            analytics_dict['timestamp'] = datetime.now()  # Ensure timestamp is set
            result = await self.collection.insert_one(analytics_dict)
            print(f"📊 Analytics logged for {analytics_data.commodity} in {analytics_data.district}")
            return result.inserted_id is not None
        except Exception as e:
            print(f"❌ Error logging analytics: {e}")
            return False

    async def get_popular_queries(self, days_back: int = 7) -> List[Dict[str, Any]]:
        """Get popular queries"""
        try:
            # 🔥 CRITICAL FIX: Use 'is None' instead of 'not self.collection'
            if self.collection is None:
                return []
                
            cutoff_date = datetime.now() - timedelta(days=days_back)
            pipeline = [
                {"$match": {"timestamp": {"$gte": cutoff_date}, "success": True}},
                {"$group": {
                    "_id": {"commodity": "$commodity", "district": "$district"},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]
            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=10)
            return results
        except Exception as e:
            print(f"❌ Error getting popular queries: {e}")
            return []

    async def get_query_stats(self, days_back: int = 30) -> Dict[str, Any]:
        """Get comprehensive query statistics"""
        try:
            if self.collection is None:
                return {"error": "Analytics service not available"}
                
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            # Total queries
            total_queries = await self.collection.count_documents({
                "timestamp": {"$gte": cutoff_date}
            })
            
            # Successful queries
            successful_queries = await self.collection.count_documents({
                "timestamp": {"$gte": cutoff_date},
                "success": True
            })
            
            # Most popular commodities
            commodity_pipeline = [
                {"$match": {"timestamp": {"$gte": cutoff_date}, "success": True}},
                {"$group": {"_id": "$commodity", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            top_commodities = await self.collection.aggregate(commodity_pipeline).to_list(5)
            
            # Most popular districts
            district_pipeline = [
                {"$match": {"timestamp": {"$gte": cutoff_date}, "success": True}},
                {"$group": {"_id": "$district", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            top_districts = await self.collection.aggregate(district_pipeline).to_list(5)
            
            return {
                "period_days": days_back,
                "total_queries": total_queries,
                "successful_queries": successful_queries,
                "success_rate": round((successful_queries / total_queries * 100) if total_queries > 0 else 0, 2),
                "top_commodities": top_commodities,
                "top_districts": top_districts
            }
        except Exception as e:
            print(f"❌ Error getting query stats: {e}")
            return {"error": str(e)}
