from app.core.config import settings
from app.core.database import Base, SessionLocal, engine, get_db


BASE_DIR = settings.base_dir
DATABASE_URL = settings.database_url

__all__ = ["BASE_DIR", "DATABASE_URL", "Base", "SessionLocal", "engine", "get_db"]
