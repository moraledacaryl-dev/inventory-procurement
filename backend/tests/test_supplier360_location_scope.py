"""Supplier 360 financial values and quotes are SQL-scoped to assigned locations."""
from decimal import Decimal

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.pass6 import OperationalAccessScope
from app.models.procurement import PurchaseOrder, PurchaseRequisition
from app.models.user import User


def login(client, email="owner@example.com"):
    r=client.post("/api/v1/auth/login",json={"email":email,"password":"password123"})
    assert r.status_code==200,r.text
    return {"Authorization":f"Bearer {r.json()['access_token']}"}


def create(client,path,header,data):
    r=client.post(path,headers=header,json=data)
    assert r.status_code==201,(path,r.text)
    return r.json()


def seed(client):
    owner=login(client)
    cat=create(client,"/api/v1/categories",owner,{"name":"Supplier 360 isolation"})
    unit=create(client,"/api/v1/units",owner,{"code":"SAZ","name":"Supplier isolation unit"})
    a,b=[create(client,"/api/v1/locations",owner,{"code":code,"name":code})["id"]
         for code in ("SUP360-A","SUP360-B")]
    item=create(client,"/api/v1/items",owner,{
        "sku":"SUP360-ING","name":"Supplier 360 stock","category_id":cat["id"],
        "base_unit_id":unit["id"],"standard_cost":"20",
    })["id"]
    supplier=create(client,"/api/v1/suppliers",owner,{
        "code":"SUP360-S","name":"Scoped Supplier for Finance"
    })
    with SessionLocal() as db:
        for email in ("supplier-scoped@example.com","supplier-global@example.com"):
            db.add(User(email=email,full_name=email,role="procurement_officer",
                        password_hash=hash_password("password123")))
        db.commit()
        scoped_id=db.query(User).filter(User.email=="supplier-scoped@example.com").one().id
    scope=create(client,"/api/v1/access-scopes",owner,{
        "user_id":scoped_id,"location_id":a,"approval_limit":"0",
    })["id"]
    reqs=[
        create(client,"/api/v1/requisitions",owner,{
            "department":"Cafe","location_id":location,
            "justification":"Buy food",
            "lines":[{"item_id":item,"quantity":"4","estimated_unit_cost":"25"}],
        }) for location in (a,b)
    ]
    # Legacy unassigned requisitions do not grant visibility via their line notes.
    legacy=create(client,"/api/v1/requisitions",owner,{
        "department":"Cafe","lines":[{
            "item_id":item,"quantity":"4","notes":f"location:{a}",
        }],
    })
    with SessionLocal() as db:
        for req in [*reqs,legacy]:
            db.get(PurchaseRequisition,req["id"]).status="approved"
        db.commit()
    quotes=[
        create(client,"/api/v1/quotations",owner,{
            "requisition_id":req["id"],"supplier_id":supplier["id"],
            "lines":[{"item_id":item,"quantity":"4","unit_price":"25"}],
        }) for req in [*reqs,legacy]
    ]
    pos=[
        create(client,"/api/v1/purchase-orders",owner,{
            "supplier_id":supplier["id"],"delivery_location_id":location,
            "lines":[{"item_id":item,"ordered_quantity":"4","unit_price":"25"}],
        }) for location in (a,b)
    ]
    with SessionLocal() as db:
        for po in pos:
            db.get(PurchaseOrder,po["id"]).status="approved"
        db.commit()
    for idx,po in enumerate(pos):
        response=client.post(f"/api/v1/receiving/purchase-orders/{po['id']}",
                             headers=owner,json={
            "delivery_reference":f"SUP360-DR-{idx}",
            "lines":[{"purchase_order_line_id":po["lines"][0]["id"],
                      "received_quantity":"2","accepted_quantity":"2",
                      "rejected_quantity":"0"}],
        })
        assert response.status_code==201,response.text
    return owner,login(client,"supplier-scoped@example.com"),login(
        client,"supplier-global@example.com"),a,b,item,supplier,reqs,legacy,quotes,pos,scope


def test_supplier_financial_totals_and_unawarded_quotations_are_location_scoped(client):
    owner,scoped,global_user,a,b,item,supplier,reqs,legacy,quotes,pos,scope=seed(client)
    path=f"/api/v1/suppliers/{supplier['id']}/detail"
    limited=client.get(path,headers=scoped)
    assert limited.status_code==200,limited.text
    limited=limited.json()
    assert {p["id"] for p in limited["purchase_orders"]}=={pos[0]["id"]}
    assert {r["purchase_order_id"] for r in limited["receipts"]}=={pos[0]["id"]}
    assert {q["id"] for q in limited["quotations"]}=={quotes[0]["id"]}
    assert limited["metrics"]["purchase_orders"]==1
    assert limited["metrics"]["quotations"]==1
    assert Decimal(limited["metrics"]["ordered_value"])==Decimal("100")
    assert Decimal(limited["metrics"]["accepted_value"])==Decimal("50")
    assert len(limited["returns"])==0
    # The shared supplier master remains visible; transactional values do not.
    assert limited["supplier"]["id"]==supplier["id"]

    for header in (owner,global_user):
        result=client.get(path,headers=header)
        assert result.status_code==200,result.text
        payload=result.json()
        assert {p["id"] for p in payload["purchase_orders"]}=={x["id"] for x in pos}
        assert {r["purchase_order_id"] for r in payload["receipts"]}=={x["id"] for x in pos}
        assert {q["id"] for q in payload["quotations"]}=={x["id"] for x in quotes}
        assert payload["metrics"]["purchase_orders"]==2
        assert payload["metrics"]["quotations"]==3
        assert Decimal(payload["metrics"]["ordered_value"])==Decimal("200")
        assert Decimal(payload["metrics"]["accepted_value"])==Decimal("100")

    with SessionLocal() as db:
        db.get(OperationalAccessScope,scope).is_active=False
        db.commit()
    revoked=client.get(path,headers=scoped)
    assert revoked.status_code==200,revoked.text
    data=revoked.json()
    assert data["purchase_orders"]==[]
    assert data["receipts"]==[]
    assert data["returns"]==[]
    assert data["quotations"]==[]
    assert data["metrics"]["purchase_orders"]==0
    assert data["metrics"]["quotations"]==0
    assert Decimal(data["metrics"]["ordered_value"])==0
    assert Decimal(data["metrics"]["received_value"])==0
    assert Decimal(data["metrics"]["accepted_value"])==0
