from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    DEBUG: bool
    
    DATABASE_URL: str
    
    OLLAMA_BASE_URL: str
    OLLAMA_MODEL: str
    OLLAMA_EMBEDDING_MODEL: str

    OSS_ENDPOINT: Optional[str] = None
    OSS_ACCESS_KEY: Optional[str] = None
    OSS_SECRET_KEY: Optional[str] = None
    OSS_BUCKET_NAME: Optional[str] = None
    OSS_DOMAIN: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
