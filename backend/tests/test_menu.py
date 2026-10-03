def auth_headers(client):
    r=client.post("/api/v1/auth/login",json={"email":"owner@example.com","password":"password123"});assert r.status_code==200
    return {"Authorization":f"Bearer {r.json()['access_token']}"}
def test_menu_crud_and_auto_codes(client):
    h=auth_headers(client);p={"name":"Test Latte","category":"Iced Coffee","variants":[{"name":"16 oz","price":"120"},{"name":"22 oz","price":"150","with_drink_price":"140"}]}
    r=client.post("/api/v1/fnb/menu",json=p,headers=h);assert r.status_code==201,r.text;b=r.json();assert len(b["variants"])==2;assert all(v["sku"] and v["barcode"] for v in b["variants"])
    assert client.get("/api/v1/fnb/menu?include_inactive=true",headers=h).status_code==200
def test_with_drink_price_guard(client):
    h=auth_headers(client);p={"name":"Bad Cookie","category":"Pastries","variants":[{"name":"Regular","price":"50","with_drink_price":"60"}]}
    assert client.post("/api/v1/fnb/menu",json=p,headers=h).status_code==422
