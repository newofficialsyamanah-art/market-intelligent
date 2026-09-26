import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

    DATABASE_URL = os.getenv("DATABASE_URL", "")
    if DATABASE_URL and "sslmode=" not in DATABASE_URL:
        DATABASE_URL += "&sslmode=require" if "?" in DATABASE_URL else "?sslmode=require"
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "market_intelligence")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    SQLALCHEMY_DATABASE_URI = DATABASE_URL or (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    SCHEDULER_TIMEZONE = os.getenv("SCHEDULER_TIMEZONE", "UTC")
    SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "duckduckgo")
    DUCKDUCKGO_VERIFY_SSL = os.getenv("DUCKDUCKGO_VERIFY_SSL", "true").lower() == "true"
    BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY", "")
    GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")

    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "static", "uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", 20)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv", "pdf"}


class TestConfig(Config):
    """Konfigurasi terisolasi khusus untuk Unit Testing & Benchmarking."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
    DB_NAME = os.getenv("TEST_DB_NAME", "market_intelligence_test")
    SQLALCHEMY_DATABASE_URI = TEST_DATABASE_URL or (
        f"mysql+pymysql://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )

