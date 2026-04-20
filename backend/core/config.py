from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Core app settings
    PROJECT_NAME: str = "FlowDesk"
    
    # Database
    # Expected format: postgresql+asyncpg://user:password@host/dbname
    DATABASE_URL: str 
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Pydantic v2 config for loading from .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Notifications & Digest
    NOTIFICATION_SECRET: str
    RESEND_API_KEY: str
    VAPID_PRIVATE_KEY: str
    VAPID_PUBLIC_KEY: str
    VAPID_CLAIM_EMAIL: str
    
    # 1 AM UTC = 6:30 AM IST. Using 1 as a safe floor hour.
    DIGEST_HOUR_UTC: int = 1
    DIGEST_WINDOW_MINUTES: int = 15

# Instantiate settings to be imported and used across the app
settings = Settings()