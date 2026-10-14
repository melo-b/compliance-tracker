from app.models.user import UserRole


def test_admin_can_list_users(client, admin_headers, make_user):
    make_user(UserRole.READ_ONLY, email="viewer@example.com")

    response = client.get("/api/v1/users/", headers=admin_headers)

    assert response.status_code == 200
    emails = [u["email"] for u in response.json()]
    assert "viewer@example.com" in emails
    assert all("hashed_password" not in u for u in response.json())


def test_me_returns_the_callers_own_profile_and_role(client, make_user):
    from tests.helpers import bearer

    engineer = make_user(UserRole.ENGINEER, email="eng@example.com")

    body = client.get("/api/v1/users/me", headers=bearer(engineer)).json()

    assert body["email"] == "eng@example.com"
    assert body["role"] == "engineer"


def test_admin_can_promote_a_user(client, admin_headers, make_user):
    target = make_user(UserRole.READ_ONLY)

    response = client.patch(
        f"/api/v1/users/{target.id}", json={"role": "engineer"}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["role"] == "engineer"


def test_admin_can_deactivate_a_user(client, admin_headers, make_user):
    target = make_user(UserRole.ENGINEER)

    response = client.patch(
        f"/api/v1/users/{target.id}", json={"is_active": False}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_admin_cannot_change_their_own_role_or_status(client, admin_headers, admin_user):
    for body in ({"role": "read_only"}, {"is_active": False}):
        response = client.patch(f"/api/v1/users/{admin_user.id}", json=body, headers=admin_headers)
        assert response.status_code == 400


def test_updating_a_missing_user_is_404(client, admin_headers):
    response = client.patch("/api/v1/users/9999", json={"role": "admin"}, headers=admin_headers)
    assert response.status_code == 404


def test_invalid_role_value_is_rejected(client, admin_headers, make_user):
    target = make_user()
    response = client.patch(
        f"/api/v1/users/{target.id}", json={"role": "SUPERUSER"}, headers=admin_headers
    )
    assert response.status_code == 422


def test_explicit_null_cannot_unset_a_role(client, admin_headers, make_user):
    target = make_user(UserRole.ENGINEER)

    response = client.patch(
        f"/api/v1/users/{target.id}", json={"role": None}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["role"] == "engineer"


def test_non_admins_cannot_manage_users(client, engineer_headers, readonly_headers, make_user):
    target = make_user()
    for headers in (engineer_headers, readonly_headers):
        assert client.get("/api/v1/users/", headers=headers).status_code == 403
        response = client.patch(
            f"/api/v1/users/{target.id}", json={"role": "admin"}, headers=headers
        )
        assert response.status_code == 403
