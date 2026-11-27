from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # priority: 1. Real OS/Docker env vars -> 2. .env file -> 3. Defaults below
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore" # Without this line, pydantic-settings throws a strict error in your .env contains GEMINI_API_KEY(or any extra variable) that isn't declared as a field on Settings.
    )

    # Redis & RQ settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    queue_name: str = "support_tickets"
    result_ttl_seconds: int = 3600

    # LLM Settings
    primary_model: str = "google_genai:gemini-3.8-flash"
    backup_model: str = "google_genai:gemini-3.8-flash-lite"
    llm_timeout: int = 15
    llm_max_retries: int = 1

# Create one shared settings object that every other file imports
settings = Settings()
# Here is the exact lookup order BaseSettings follows at startup:
# 1. Checks the OS environment first(case-insensitive): It looks for REDIS_HOST in the container's OS. Because docker-compose.yml inject REDIS_HOST=redis, BaseSettings grabs "redis" and ignores "localhost".
# 2. Checks .env second: If REDIS_HOST wasn't in the OS, it checks your .env file.
# 3. Uses the default last: If neither the OS nor .env has REDIS_HOST(like when you run locally on mac), it falls to "localhost".