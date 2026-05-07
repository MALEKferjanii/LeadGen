from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")
    # Database
    database_url: str = "postgresql://leadgen:leadgen_secret@localhost:5432/leadgen360"

    # PostgreSQL direct (for docker-compose)
    postgres_user: str = "leadgen"
    postgres_password: str = "leadgen_secret"
    postgres_db: str = "leadgen360"

    # LinkedIn accounts (jusqu'à 3 comptes pour rotation)
    linkedin_email_1: str = ""
    linkedin_password_1: str = ""
    linkedin_email_2: str = ""
    linkedin_password_2: str = ""
    linkedin_email_3: str = ""
    linkedin_password_3: str = ""

    # Cookies persistés pour éviter les re-authentifications
    cookies_dir: str = "./cookies"

    # API
    api_secret_key: str = "changeme_secret_key"

    # LLM — Groq (primaire) + Ollama (fallback local)
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"

    # Enrichissement email
    hunter_api_key: str = ""

    # Rate limits LinkedIn (conservateur pour éviter les bans)
    linkedin_requests_per_hour: int = 80
    linkedin_requests_per_day: int = 250

    # n8n
    n8n_webhook_url: str = "http://n8n:5678/webhook"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Config déplacée vers model_config (voir au-dessus)


@lru_cache
def get_settings() -> Settings:
    return Settings()
