PAYLOAD = {
    "model_number": "RELAY-100",
    "name": "High Voltage Relay",
    "description": "Standard compliance relay",
}


def test_create_product_unauthenticated(client):
    """Anonymous users are blocked from creating products."""
    response = client.post("/api/v1/products/", json=PAYLOAD)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_list_products_requires_login(client):
    assert client.get("/api/v1/products/").status_code == 401


def test_readonly_user_cannot_create_product(client, readonly_headers):
    response = client.post("/api/v1/products/", json=PAYLOAD, headers=readonly_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_engineer_can_create_product(client, engineer_headers):
    response = client.post("/api/v1/products/", json=PAYLOAD, headers=engineer_headers)
    data = response.json()

    assert response.status_code == 201
    assert data["model_number"] == "RELAY-100"
    assert "id" in data


def test_duplicate_model_number_is_rejected(client, engineer_headers):
    client.post("/api/v1/products/", json=PAYLOAD, headers=engineer_headers)
    response = client.post("/api/v1/products/", json=PAYLOAD, headers=engineer_headers)

    assert response.status_code == 400


def test_every_role_can_read_products(client, engineer_headers, readonly_headers, admin_headers):
    client.post("/api/v1/products/", json=PAYLOAD, headers=engineer_headers)

    for headers in (readonly_headers, engineer_headers, admin_headers):
        response = client.get("/api/v1/products/", headers=headers)
        assert response.status_code == 200
        assert [p["model_number"] for p in response.json()] == ["RELAY-100"]


def test_get_product_by_id_and_missing_product(client, engineer_headers, readonly_headers):
    created = client.post("/api/v1/products/", json=PAYLOAD, headers=engineer_headers).json()

    found = client.get(f"/api/v1/products/{created['id']}", headers=readonly_headers)
    assert found.status_code == 200
    assert client.get("/api/v1/products/999", headers=readonly_headers).status_code == 404


def test_engineer_can_update_but_readonly_cannot(client, engineer_headers, readonly_headers):
    created = client.post("/api/v1/products/", json=PAYLOAD, headers=engineer_headers).json()
    url = f"/api/v1/products/{created['id']}"

    assert client.patch(url, json={"name": "X"}, headers=readonly_headers).status_code == 403
    updated = client.patch(url, json={"name": "Renamed Relay"}, headers=engineer_headers)
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed Relay"


def test_only_admin_can_delete_product(client, engineer_headers, admin_headers):
    created = client.post("/api/v1/products/", json=PAYLOAD, headers=engineer_headers).json()
    url = f"/api/v1/products/{created['id']}"

    assert client.delete(url, headers=engineer_headers).status_code == 403
    assert client.delete(url, headers=admin_headers).status_code == 204
    assert client.get(url, headers=admin_headers).status_code == 404
