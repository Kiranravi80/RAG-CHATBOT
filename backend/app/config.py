from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str

    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    APP_DEBUG: bool = True


settings = Settings()
