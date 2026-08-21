def test_create_product_unauthorized(client):
    """Ensure anonymous users are blocked from creating products."""
    response = client.post(
        "/api/v1/products/",
        json={
            "model_number": "RELAY-100",
            "name": "High Voltage Relay",
            "description": "Standard compliance relay"
        }
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

def test_create_product_authorized(authorized_client):
    """Ensure logged-in users can successfully create a product."""
    payload = {
        "model_number": "RELAY-100",
        "name": "High Voltage Relay",
        "description": "Standard compliance relay"
    }
    
    response = authorized_client.post("/api/v1/products/", json=payload)
    data = response.json()
    
    assert response.status_code == 201
    assert data["model_number"] == "RELAY-100"
    assert "id" in data

def test_get_products(client, authorized_client):
    """Ensure the GET route works and returns the created data."""
    # 1. Create a product using the authorized client
    authorized_client.post(
        "/api/v1/products/",
        json={
            "model_number": "BREAKER-200",
            "name": "Circuit Breaker",
            "description": "20A Breaker"
        }
    )
    
    # 2. Fetch the product list using the standard public client
    response = client.get("/api/v1/products/")
    data = response.json()
    
    assert response.status_code == 200
    assert len(data) == 1
    assert data[0]["model_number"] == "BREAKER-200"