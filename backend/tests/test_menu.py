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

def test_generic_pos_rule_setup(client):
    h=auth_headers(client)
    modifier=client.post("/api/v1/fnb/pos-rules/modifiers",json={
        "name":"Sinkers","group":{"id":"sinkers","label":"Sinkers / Add-ons","mode":"multi","options":[{"label":"Pearl","price_delta":20}]}
    },headers=h)
    assert modifier.status_code==201,modifier.text
    pricing=client.post("/api/v1/fnb/pos-rules/pricing",json={
        "name":"Combo pricing","qualifier_tag":"combo-qualifier","target_tag":"combo-target"
    },headers=h)
    assert pricing.status_code==201,pricing.text
    p={"name":"Flexible Item","category":"Test","pricing_tags":["combo-target"],"modifier_template_ids":[modifier.json()["id"]],"variants":[{"name":"Regular","price":"50","conditional_prices":[{"rule_id":pricing.json()["id"],"price":45}]}]}
    r=client.post("/api/v1/fnb/menu",json=p,headers=h)
    assert r.status_code==201,r.text
    body=r.json()
    assert body["pricing_tags"]==["combo-target"]
    assert body["modifier_template_ids"]==[modifier.json()["id"]]
    assert body["variants"][0]["conditional_prices"][0]["price"]==45


def test_generic_pos_rule_validation_and_references(client):
    h=auth_headers(client)
    bad_modifier=client.post("/api/v1/fnb/pos-rules/modifiers",json={
        "name":"Bad Sinkers","group":{"id":"sinkers","label":"Sinkers","mode":"multi","options":[
            {"id":"pearl","label":"Pearl","price_delta":20},
            {"id":"pearl","label":"Pearl 2","price_delta":20}
        ]}
    },headers=h)
    assert bad_modifier.status_code==422

    negative_modifier=client.post("/api/v1/fnb/pos-rules/modifiers",json={
        "name":"Negative","group":{"id":"negative","label":"Negative","mode":"multi","options":[{"label":"Bad","price_delta":-1}]}
    },headers=h)
    assert negative_modifier.status_code==422

    missing_refs={"name":"Broken Rules","category":"Test","pricing_tags":["combo-target"],"modifier_template_ids":["missing-template"],"variants":[{"name":"Regular","price":"50","conditional_prices":[{"rule_id":"missing-rule","price":45}]}]}
    r=client.post("/api/v1/fnb/menu",json=missing_refs,headers=h)
    assert r.status_code==422


def test_pos_rule_priority_is_published(client):
    h=auth_headers(client)
    first=client.post("/api/v1/fnb/pos-rules/pricing",json={"name":"Later","qualifier_tag":"q","target_tag":"t","priority":200},headers=h)
    second=client.post("/api/v1/fnb/pos-rules/pricing",json={"name":"Earlier","qualifier_tag":"q","target_tag":"t","priority":10},headers=h)
    assert first.status_code==201 and second.status_code==201
    rules=client.get("/api/v1/fnb/pos-rules",headers=h).json()
    assert rules["conflict_policy"]=="lowest_price_then_priority_then_rule_id"
    assert next(x for x in rules["pricing_rules"] if x["id"]==second.json()["id"])["priority"]==10
