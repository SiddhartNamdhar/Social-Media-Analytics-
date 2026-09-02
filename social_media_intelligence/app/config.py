import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    TELEGRAM_API_ID: str
    TELEGRAM_API_HASH: str
    TELEGRAM_PHONE: str = ""
    TELEGRAM_SESSION_NAME: str = "social_media_intelligence"
    
    DATA_DIRECTORY: str = "data"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
