from jose import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
import uuid
from app.models.user import UserCreate, UserInDB, UserResponse, TokenData
from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = getattr(settings, 'jwt_secret_key', "your-secret-key-change-this")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class AuthService:
    def __init__(self):
        self.db = None
        self.users_collection = None

    def set_db(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.users_collection = db.users

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    async def get_user_by_username(self, username: str) -> Optional[UserInDB]:
        try:
            user_doc = await self.users_collection.find_one({"username": username})
            if user_doc:
                return UserInDB(**user_doc)
        except Exception as e:
            print(f"Error getting user: {e}")
        return None

    async def create_user(self, user: UserCreate) -> Optional[UserInDB]:
        try:
            existing_user = await self.get_user_by_username(user.username)
            if existing_user:
                return None

            user_id = str(uuid.uuid4())
            hashed_password = self.get_password_hash(user.password)
            
            user_doc = {
                "user_id": user_id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "phone": user.phone,
                "location": user.location,
                "hashed_password": hashed_password,
                "created_at": datetime.now(),
                "last_login": None,
                "total_queries": 0,
                "is_active": True
            }
            
            result = await self.users_collection.insert_one(user_doc)
            if result.inserted_id:
                return UserInDB(**user_doc)
                
        except Exception as e:
            print(f"Error creating user: {e}")
        return None

    async def authenticate_user(self, username: str, password: str) -> Optional[UserInDB]:
        user = await self.get_user_by_username(username)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        
        await self.users_collection.update_one(
            {"username": username},
            {"$set": {"last_login": datetime.now()}}
        )
        
        return user

    # ✅ ADDED: Missing method to update user query count
    async def update_user_queries(self, username: str) -> bool:
        """Update user's total query count"""
        try:
            result = await self.users_collection.update_one(
                {"username": username},
                {
                    "$inc": {"total_queries": 1},
                    "$set": {"last_login": datetime.utcnow()}
                }
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Update user queries error: {e}")
            return False
