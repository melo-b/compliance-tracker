from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

SQLALCHEMY_DATABASE_URL = get_settings().database_url

# 1. Create the Engine (The core interface to PostgreSQL)
# pool_pre_ping tests a connection before use and pool_recycle retires old ones, so connections
# killed when a serverless database (Neon) scales to zero are replaced instead of raising errors.
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

# 2. Create the Session Factory (Spawns isolated sessions for API requests)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# 3. Dependency Injection (Hands a safe session to FastAPI routes)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
