def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_ready(client):
    assert client.get("/api/v1/ready").status_code == 200
