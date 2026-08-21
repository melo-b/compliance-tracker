import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:password@localhost:5433/compliance_db")

# 1. Create the Engine (The core interface to PostgreSQL)
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 2. Create the Session Factory (Spawns isolated sessions for API requests)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Dependency Injection (Hands a safe session to FastAPI routes)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()