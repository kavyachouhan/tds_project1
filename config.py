from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Settings
    APP_SECRET: str
    
    # GitHub Settings
    GITHUB_TOKEN: str
    GITHUB_USERNAME: str
    
    # LLM Settings
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-pro"
    
    # Evaluation Settings
    MAX_RETRIES: int = 5
    INITIAL_RETRY_DELAY: float = 1.0
    MAX_RETRY_DELAY: float = 60.0
    EVALUATION_TIMEOUT: int = 540  # 9 minutes (leave 1 minute buffer from 10min deadline)
    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()