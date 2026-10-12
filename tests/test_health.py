from sqlalchemy.exc import OperationalError

from app.db.database import get_db
from app.main import app


def test_liveness_does_not_need_the_database(client):
    def broken_db():
        raise AssertionError("liveness must not open a database session")
        yield

    app.dependency_overrides[get_db] = broken_db
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_ok_when_database_reachable(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_readiness_returns_503_when_database_is_down(client):
    class DownSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    def down_db():
        yield DownSession()

    app.dependency_overrides[get_db] = down_db
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
