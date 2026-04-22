# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Pro URL Shortener"
    DATABASE_URL: str
    
    # Your excellent Pydantic V2 implementation
    model_config = SettingsConfigDict(env_file=".env",extra="ignore")

# Instantiate it (Capital S for class, lowercase s for object)
settings = Settings()