def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_stock_ledger_payload(client):
    response = client.get("/api/v1/stock/ledger?limit=50", headers=auth_headers(client))
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"filters", "summary", "rows"}
    assert set(payload["summary"]) == {"movement_count", "net_quantity", "net_value", "document_count"}
    assert isinstance(payload["rows"], list)
    if payload["rows"]:
        row = payload["rows"][0]
        assert "document_number" in row
        assert "running_quantity" in row
        assert "line_value" in row


def test_stock_document_detail(client):
    headers = auth_headers(client)
    ledger = client.get("/api/v1/stock/ledger?limit=1", headers=headers).json()
    if not ledger["rows"]:
        return
    document_id = ledger["rows"][0]["document_id"]
    response = client.get(f"/api/v1/stock/documents/{document_id}", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["id"] == document_id
    assert isinstance(payload["lines"], list)
    assert set(payload["summary"]) == {"line_count", "net_quantity", "net_value"}


def test_missing_stock_document(client):
    response = client.get("/api/v1/stock/documents/not-a-real-id", headers=auth_headers(client))
    assert response.status_code == 404
