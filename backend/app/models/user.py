from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None
    location: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    full_name: str
    phone: Optional[str] = None
    location: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    total_queries: int = 0
    is_active: bool = True

class UserInDB(BaseModel):
    user_id: str
    username: str
    email: str
    full_name: str
    phone: Optional[str] = None
    location: Optional[str] = None
    hashed_password: str
    created_at: datetime
    last_login: Optional[datetime] = None
    total_queries: int = 0
    is_active: bool = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user_info: UserResponse

class TokenData(BaseModel):
    username: Optional[str] = None
