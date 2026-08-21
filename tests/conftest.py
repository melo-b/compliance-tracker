import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import get_db
from app.db.base import Base
from app.api.dependencies import get_current_user
from app.models.user import User

# 1. Setup in-memory SQLite database for fast, isolated testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 2. Database Fixture
@pytest.fixture(scope="function")
def db_session():
    """Creates a fresh database for each test and destroys it afterward."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

# 3. Standard Client Fixture (Unauthenticated)
@pytest.fixture(scope="function")
def client(db_session):
    """Overrides the database dependency to use our SQLite test DB."""
    def override_get_db():
        yield db_session
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
        
# 4. Authorized Client Fixture (Authenticated)
@pytest.fixture(scope="function")
def authorized_client(client):
    """Bypasses the JWT token check by mocking the current user."""
    def override_get_current_user():
        return User(id=1, email="test_engineer@example.com", is_active=True)
        
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)