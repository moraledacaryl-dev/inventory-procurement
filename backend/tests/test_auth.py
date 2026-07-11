def test_login_and_module_access(client):
    login = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    items = client.get("/api/v1/items", headers=headers)
    assert items.status_code == 200
    assert isinstance(items.json(), list)


def test_browser_session_cookie_and_logout(client):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
        headers={"X-Requested-With": "HiddenOasisInventory"},
    )
    assert login.status_code == 200
    assert "inventory_session=" in login.headers["set-cookie"]
    assert "HttpOnly" in login.headers["set-cookie"]
    assert client.get("/api/v1/auth/me").status_code == 200

    blocked = client.post("/api/v1/auth/logout")
    assert blocked.status_code == 403

    logout = client.post("/api/v1/auth/logout", headers={"X-Requested-With": "HiddenOasisInventory"})
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
