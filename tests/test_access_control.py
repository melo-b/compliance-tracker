"""Role x endpoint access matrix.

Every API route is listed with the roles that may call it. For each route the test checks that
anonymous callers get 401, roles outside the list get 403, and allowed roles are not blocked by
authorization (they may still get 404/422 because the test sends placeholder data).
"""
from types import SimpleNamespace

import pytest

from app.main import app
from app.models.user import UserRole

ANY = {UserRole.ADMIN, UserRole.ENGINEER, UserRole.READ_ONLY}
ENGINEER_UP = {UserRole.ADMIN, UserRole.ENGINEER}
ADMIN_ONLY = {UserRole.ADMIN}

MATRIX = [
    # products
    ("GET", "/api/v1/products/", ANY),
    ("GET", "/api/v1/products/1", ANY),
    ("POST", "/api/v1/products/", ENGINEER_UP),
    ("PATCH", "/api/v1/products/1", ENGINEER_UP),
    ("DELETE", "/api/v1/products/1", ADMIN_ONLY),
    # standards (managing the catalogue is admin-only)
    ("GET", "/api/v1/standards/", ANY),
    ("GET", "/api/v1/standards/1", ANY),
    ("POST", "/api/v1/standards/", ADMIN_ONLY),
    ("PATCH", "/api/v1/standards/1", ADMIN_ONLY),
    ("DELETE", "/api/v1/standards/1", ADMIN_ONLY),
    # compliance records
    ("GET", "/api/v1/standards/compliance/", ANY),
    ("GET", "/api/v1/standards/compliance/product/1", ANY),
    ("POST", "/api/v1/standards/compliance/", ENGINEER_UP),
    ("PATCH", "/api/v1/standards/compliance/1", ENGINEER_UP),
    ("DELETE", "/api/v1/standards/compliance/1", ADMIN_ONLY),
    ("POST", "/api/v1/standards/compliance/scan/", ADMIN_ONLY),
    # documents
    ("GET", "/api/v1/documents/product/1", ANY),
    ("POST", "/api/v1/documents/upload/", ENGINEER_UP),
    # users
    ("GET", "/api/v1/users/me", ANY),
    ("GET", "/api/v1/users/", ADMIN_ONLY),
    ("PATCH", "/api/v1/users/1", ADMIN_ONLY),
]

PUBLIC_PATHS = {"/", "/health", "/health/ready", "/api/v1/auth/register/", "/api/v1/auth/login/"}

HEADERS_BY_ROLE = {
    UserRole.ADMIN: "admin_headers",
    UserRole.ENGINEER: "engineer_headers",
    UserRole.READ_ONLY: "readonly_headers",
}


@pytest.fixture(autouse=True)
def no_real_task_queue(monkeypatch):
    """The scan endpoint would otherwise try to reach a Redis broker."""
    fake_task = SimpleNamespace(delay=lambda **kwargs: SimpleNamespace(id="test-task-id"))
    monkeypatch.setattr("app.api.routes_standard.scan_expiring_compliance_records", fake_task)


def send(client, method, path, headers=None):
    return client.request(method, path, json={}, headers=headers)


@pytest.mark.parametrize(("method", "path", "allowed"), MATRIX)
def test_anonymous_callers_are_rejected(client, method, path, allowed):
    assert send(client, method, path).status_code == 401


@pytest.mark.parametrize(("method", "path", "allowed"), MATRIX)
@pytest.mark.parametrize("role", list(UserRole))
def test_role_access(request, client, method, path, allowed, role):
    headers = request.getfixturevalue(HEADERS_BY_ROLE[role])
    status_code = send(client, method, path, headers).status_code

    if role in allowed:
        assert status_code not in (401, 403), f"{role.name} should be allowed on {method} {path}"
    else:
        assert status_code == 403, f"{role.name} should be forbidden on {method} {path}"


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def declared_operations() -> dict[tuple[str, str], bool]:
    """(METHOD, path with {params} replaced by 1) -> whether the operation requires login.

    Read from the OpenAPI schema, which is FastAPI's public description of the app. Every
    operation whose dependencies include the OAuth2 bearer scheme carries a `security` entry.
    """
    operations = {}
    for path, item in app.openapi()["paths"].items():
        concrete = "/".join("1" if part.startswith("{") else part for part in path.split("/"))
        for method, operation in item.items():
            if method in HTTP_METHODS:
                operations[(method.upper(), concrete)] = bool(operation.get("security"))
    return operations


def test_schema_discovery_actually_finds_the_routes():
    """Guards the guards: an empty route list would make the checks below pass vacuously."""
    assert len(declared_operations()) >= 20


def test_every_api_route_requires_login_unless_explicitly_public():
    """Secure by default: a new route that forgets authentication fails this test."""
    unprotected = sorted(
        f"{method} {path}"
        for (method, path), protected in declared_operations().items()
        if path not in PUBLIC_PATHS and not protected
    )
    assert unprotected == []


def test_the_public_routes_are_exactly_the_expected_ones():
    public = {path for (_, path), protected in declared_operations().items() if not protected}
    assert public == PUBLIC_PATHS


def test_the_matrix_lists_every_protected_route():
    """A new route must be added to MATRIX so its role rules are tested too."""
    protected = {key for key, is_protected in declared_operations().items() if is_protected}
    assert protected == {(method, path) for method, path, _ in MATRIX}
