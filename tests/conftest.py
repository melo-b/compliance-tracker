import os

# Settings are read when the app is first imported, so provide test values up front.
# Tests override get_db with the test database below, so DATABASE_URL is never contacted.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production-0123456789")
os.environ.setdefault("DATABASE_URL", "sqlite:///./unused-test.db")

import itertools
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.database import get_db
from app.main import app
from app.models.product import Product
from app.models.standard import ProductCompliance, Standard, WorkflowStatus
from app.models.user import User, UserRole
from tests.helpers import TEST_PASSWORD, bearer

# 1. The test database.
# By default an in-memory SQLite database: fast, and nothing to install. Set TEST_POSTGRES_URL
# (CI does) to run the whole suite against PostgreSQL instead, the production database, inside
# a temporary schema that is dropped afterwards. It is deliberately not read from DATABASE_URL,
# so a leftover production URL in your terminal can never be touched by the tests.
TEST_POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")
USING_POSTGRES = bool(TEST_POSTGRES_URL)

if USING_POSTGRES:
    _SCHEMA = f"pytest_{uuid.uuid4().hex[:12]}"
    _base_url = make_url(TEST_POSTGRES_URL)
    with create_engine(_base_url).begin() as _connection:
        _connection.execute(text(f'CREATE SCHEMA "{_SCHEMA}"'))
    engine = create_engine(_base_url.update_query_dict({"options": f"-csearch_path={_SCHEMA}"}))

    @pytest.fixture(scope="session", autouse=True)
    def _drop_test_schema():
        yield
        engine.dispose()
        with create_engine(_base_url).begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{_SCHEMA}" CASCADE'))

else:
    engine = create_engine(
        "sqlite:///:memory:",
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


# 3. Client Fixture
@pytest.fixture(scope="function")
def client(db_session):
    """Overrides the database dependency to use our SQLite test DB."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# 4. Users and tokens (real users, real signed JWTs: authentication is never mocked)
@pytest.fixture(scope="session")
def test_password_hash():
    """Hashing is deliberately slow, so hash the shared test password only once."""
    return hash_password(TEST_PASSWORD)


@pytest.fixture
def make_user(db_session, test_password_hash):
    """Factory: make_user(role, email=None, is_active=True) -> persisted User."""
    counter = itertools.count(1)

    def _make_user(role=UserRole.READ_ONLY, email=None, is_active=True, hashed_password=None):
        user = User(
            email=email or f"user{next(counter)}-{role.name.lower()}@example.com",
            hashed_password=hashed_password or test_password_hash,
            role=role,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make_user


@pytest.fixture
def admin_user(make_user):
    return make_user(UserRole.ADMIN)


@pytest.fixture
def admin_headers(admin_user):
    return bearer(admin_user)


@pytest.fixture
def engineer_headers(make_user):
    return bearer(make_user(UserRole.ENGINEER))


@pytest.fixture
def readonly_headers(make_user):
    return bearer(make_user(UserRole.READ_ONLY))


@pytest.fixture
def make_compliance(db_session):
    """Factory: make_compliance(workflow_status=..., expiration_date=...) -> persisted record."""
    counter = itertools.count(1)

    def _make(workflow_status=WorkflowStatus.PENDING, **fields):
        n = next(counter)
        product = Product(name=f"Product {n}", model_number=f"MODEL-{n}")
        standard = Standard(standard_number=f"STD-{n}", title=f"Standard {n}", issuing_body="CSA")
        db_session.add_all([product, standard])
        db_session.flush()
        record = ProductCompliance(
            product_id=product.id,
            standard_id=standard.id,
            workflow_status=workflow_status,
            **fields,
        )
        db_session.add(record)
        db_session.commit()
        db_session.refresh(record)
        return record

    return _make
