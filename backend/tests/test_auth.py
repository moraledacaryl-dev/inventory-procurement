def test_login_and_module_access(client):
    login = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    items = client.get("/api/v1/items", headers=headers)
    assert items.status_code == 200
    assert isinstance(items.json(), list)
