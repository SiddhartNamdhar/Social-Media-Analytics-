import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve project root dynamically
PROJECT_ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    TELEGRAM_API_ID: str
    TELEGRAM_API_HASH: str
    TELEGRAM_PHONE: str = ""
    TELEGRAM_SESSION_NAME: str = "social_media_intelligence"
    
    DATA_DIRECTORY: str = str(PROJECT_ROOT / "data")
    LOG_LEVEL: str = "INFO"
    
    YOUTUBE_API_KEY: str = ""
    YOUTUBE_DEFAULT_REGION_CODE: str = "IN"
    YOUTUBE_DEFAULT_LANGUAGE: str = "en"
    YOUTUBE_MAX_RESULTS: int = 50

    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / '.env'), env_file_encoding='utf-8', extra='ignore')

settings = Settings()
