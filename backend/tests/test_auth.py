from app.core.roles import accessible_modules, has_permission, permissions_for_role


def test_login_and_module_access(client):
    login = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    session = me.json()
    assert session["role"] == "owner"
    assert session["permissions"] == ["*"]
    assert "purchasing" in session["accessible_modules"]
    assert "counts" in session["accessible_modules"]

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


def test_role_permission_matrix():
    assert has_permission("owner", "procurement.approve")
    assert has_permission("inventory_manager", "items.read")
    assert has_permission("procurement_officer", "procurement.approve")
    assert has_permission("receiver", "receiving.create")
    assert has_permission("receiver", "procurement.read")
    assert not has_permission("receiver", "procurement.approve")
    assert has_permission("counter", "counts.submit")
    assert not has_permission("counter", "suppliers.read")
    assert has_permission("viewer", "reports.read")
    assert not has_permission("viewer", "items.create")
    assert permissions_for_role("unknown-role") == []
    assert "receiving" in accessible_modules("receiver")
    assert "purchasing" in accessible_modules("receiver")
    assert "suppliers" in accessible_modules("receiver")
    assert "counts" not in accessible_modules("receiver")
