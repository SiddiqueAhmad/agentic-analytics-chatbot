from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_api_key: str  # Will look for GOOGLE_API_KEY
    redis_url: str = "redis://localhost:6379"  # Default value if missing

    class Config:
        env_file = ".env"


# Create a global settings object
settings = Settings()
