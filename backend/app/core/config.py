from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Existing settings
    gemini_api_key: str
    # Add this line inside your Settings class
    jwt_secret_key: str = "your-super-secret-jwt-key-change-in-production"
    
    # MongoDB settings
    mongodb_uri: str
    mongodb_dbname: str = "digikisan"
    
    # Allow any extra fields from .env (optional)
    mongodb_db: str = "digikisan"  # If you have this in .env
    env: str = "dev"  # If you have this in .env
    
    class Config:
        env_file = ".env"
        extra = "allow"  # This allows extra fields

settings = Settings()
