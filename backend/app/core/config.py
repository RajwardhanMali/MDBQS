# app/core/config.py
from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    POSTGRES_DSN: str = os.getenv("POSTGRES_DSN")
    MONGO_URI: str =  os.getenv("MONGO_URI")
    MONGO_DB: str = os.getenv("MONGO_DB", "mdbs")
    NEO4J_URI: str = os.getenv("NEO4J_URI")
    NEO4J_USER: str = os.getenv("NEO4J_USER")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD")
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    APP_ENV: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# usage: settings = Settings()
