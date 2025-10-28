from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from datetime import datetime

class DatabaseService:
    client: AsyncIOMotorClient = None
    database = None

# Global database service instance
db_service = DatabaseService()

async def connect_to_mongo():
    """Create database connection"""
    try:
        print("🔗 Connecting to MongoDB Atlas...")
        db_service.client = AsyncIOMotorClient(settings.mongodb_uri)
        db_service.database = db_service.client[settings.mongodb_dbname]
        
        # Test connection with ping
        await db_service.client.admin.command('ping')
        print(f"✅ MongoDB connected successfully!")
        print(f"   📊 Database: {settings.mongodb_dbname}")
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        raise e

async def close_mongo_connection():
    """Close database connection"""
    if db_service.client:
        db_service.client.close()
        print("🔌 MongoDB connection closed")

def get_database():
    """Get database instance for use in routes"""
    return db_service.database

# FastAPI dependency
async def get_db():
    """FastAPI dependency to get database instance"""
    db = get_database()
    if db is None:
        raise Exception("Database not connected")
    return db
