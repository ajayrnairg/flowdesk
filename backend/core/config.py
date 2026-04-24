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
    # Allow extra fields to prevent crashes when new variables are added to .env
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Notifications & Digest
    NOTIFICATION_SECRET: str
    RESEND_API_KEY: str
    VAPID_PRIVATE_KEY: str
    VAPID_PUBLIC_KEY: str
    VAPID_CLAIM_EMAIL: str
    
    # 1 AM UTC = 6:30 AM IST. Using 1 as a safe floor hour.
    DIGEST_HOUR_UTC: int = 1
    DIGEST_WINDOW_MINUTES: int = 15

    # Knowledge Base
    JINA_TIMEOUT_SECONDS: int = 15
    GITHUB_TOKEN: str = "" # Optional: empty string means unauthenticated
    GEMINI_API_KEY: str # Ensure this is present

    # Vector / Search / Redis (for rate limiting or caching)
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""

# Instantiate settings to be imported and used across the app
settings = Settings()