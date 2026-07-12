def auth_headers(client):
    response = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert response.status_code == 200
    payload = response.json()
    return {"Authorization": f"Bearer {payload['access_token']}"}, payload["user"]["id"]


def service_headers(source):
    token = "test-staff-integration-token" if source == "staff" else "test-command-center-integration-token"
    return {"X-Integration-Token": token}


def request_payload(user_id, source="staff", external_id="REQ-001"):
    return {"source_system":source,"external_request_id":external_id,"requester_user_id":user_id,"department":"Cafe","request_type":"stock_request","title":"Restock coffee beans","description":"Request two bags from storage.","priority":"high","related_entity_type":"item","related_entity_id":"coffee-beans"}


def test_receive_operational_request_is_idempotent(client):
    auth,user_id=auth_headers(client);headers=service_headers("staff")
    first=client.post("/api/v1/integrations/operations/requests",headers=headers,json=request_payload(user_id));assert first.status_code==201;assert first.json()["workflow_status"]=="submitted"
    duplicate=client.post("/api/v1/integrations/operations/requests",headers=headers,json=request_payload(user_id));assert duplicate.status_code==201;assert duplicate.json()["id"]==first.json()["id"]
    workspace=client.get("/api/v1/integrations/operations/workspace",headers=auth);assert workspace.status_code==200;assert workspace.json()["summary"]["submitted"]>=1;assert any(row["id"]==first.json()["id"] for row in workspace.json()["requests"])


def test_accept_and_complete_operational_request(client):
    auth,user_id=auth_headers(client)
    created=client.post("/api/v1/integrations/operations/requests",headers=service_headers("command-center"),json=request_payload(user_id,"command-center","REQ-002"));assert created.status_code==201
    accepted=client.post(f"/api/v1/integrations/operations/requests/{created.json()['id']}/decision",headers=auth,json={"decision":"accepted","assigned_to_user_id":user_id,"notes":"Approved for release"});assert accepted.status_code==200;assert accepted.json()["workflow_status"]=="accepted"
    completed=client.post(f"/api/v1/integrations/operations/requests/{created.json()['id']}/decision",headers=auth,json={"decision":"completed","notes":"Released from storage"});assert completed.status_code==200;assert completed.json()["workflow_status"]=="completed"
    repeated=client.post(f"/api/v1/integrations/operations/requests/{created.json()['id']}/decision",headers=auth,json={"decision":"completed"});assert repeated.status_code==409


def test_request_requires_supported_source_identity_and_token(client):
    _auth,user_id=auth_headers(client)
    invalid_source=client.post("/api/v1/integrations/operations/requests",headers={"X-Integration-Token":"bad"},json=request_payload(user_id,"payroll","REQ-003"));assert invalid_source.status_code==422
    unauthorized=client.post("/api/v1/integrations/operations/requests",json=request_payload(user_id,"staff","REQ-004"));assert unauthorized.status_code==401
    bad_identity=client.post("/api/v1/integrations/operations/requests",headers=service_headers("staff"),json=request_payload("missing-user","staff","REQ-005"));assert bad_identity.status_code==422


def test_accept_requires_assignee(client):
    auth,user_id=auth_headers(client)
    created=client.post("/api/v1/integrations/operations/requests",headers=service_headers("staff"),json=request_payload(user_id,"staff","REQ-006"))
    response=client.post(f"/api/v1/integrations/operations/requests/{created.json()['id']}/decision",headers=auth,json={"decision":"accepted"});assert response.status_code==422
