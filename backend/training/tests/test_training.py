import json
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from conftest import begin

LESSON_IDS = [
    "available-stock", "find-your-work", "catalogue-units", "opening-stock", "issue-kitchen", "transfer-stock", "blind-count", "count-zero", "approve-count", "record-waste", "supplier-profile", "request-purchase", "purchase-approval", "order-supplies", "supplier-return", "expiry-rotation", "recipe-cost", "batch-production", "menu-mapping", "sale-consumption", "staff-meal", "housekeeping-supplies", "asset-maintenance", "accounting-proof", "connected-work", "management-review", "admin-controls", "full-delivery", "partial-delivery", "damaged-delivery", "expired-delivery", "fully-rejected", "quantity-discrepancy", "wrong-item", "later-delivery", "check-order", "resume-delivery",
]


@pytest.mark.parametrize("lesson",LESSON_IDS)
def test_every_lesson_fixture_and_actor_session_are_compatible(learner,lesson):
    from training.curriculum import BY_ID
    role=BY_ID[lesson].roles[0]
    result=begin(learner,lesson,role)
    session=learner.get("/api/v1/auth/me")
    assert session.status_code==200,session.text
    assert session.json()["role"]==role
    assert result["lesson"]["curriculum_version"]


def check(client, lesson):
    from training.curriculum import BY_ID
    return client.post("/api/v1/training/check", json={"answer": BY_ID[lesson].answer}).json()


@pytest.mark.parametrize("lesson", ["full-delivery", "partial-delivery", "damaged-delivery", "expired-delivery", "fully-rejected", "quantity-discrepancy", "wrong-item", "later-delivery", "check-order", "resume-delivery"])
def test_receiving_outcomes(learner, lesson):
    result = begin(learner, lesson, "receiver")
    task = result["lesson"]
    assert check(learner, lesson)["passed"] is False
    response = learner.post("/api/v1/receiving/purchase-orders/training-po", json={"delivery_reference": task["reference"], "idempotency_key": "delivery-retry", "lines": [{"purchase_order_line_id": "training-po-line", "received_quantity": task["quantity"], "accepted_quantity": task["quantity"] - task["rejected"], "rejected_quantity": task["rejected"], "discrepancy_reason": "inspection failure" if task["rejected"] else None}]})
    assert response.status_code == 201, response.text
    assert check(learner, lesson)["passed"] is True
    # Replaying the same receipt cannot add stock again.
    duplicate = learner.post("/api/v1/receiving/purchase-orders/training-po", json={"delivery_reference": task["reference"], "idempotency_key": "delivery-retry", "lines": [{"purchase_order_line_id": "training-po-line", "received_quantity": task["quantity"], "accepted_quantity": task["quantity"] - task["rejected"], "rejected_quantity": task["rejected"], "discrepancy_reason": "inspection failure" if task["rejected"] else None}]})
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == response.json()["id"]


@pytest.mark.parametrize("lesson,quantity", [("blind-count", 21), ("count-zero", 0)])
def test_counter_blind_quantity_saved_and_independent_approval_required(learner, lesson, quantity):
    begin(learner, lesson, "counter")
    before = learner.get("/api/v1/counts/training-count/detail").json()
    assert before["lines"][0]["snapshot_quantity"] is None
    assert before["lines"][0]["live_quantity"] is None
    attempted=check(learner,lesson)
    assert attempted["evidence"]["physical_quantity"] is None
    assert learner.post("/api/v1/counts/training-count/submit").status_code == 422
    saved = learner.put("/api/v1/counts/training-count/entries", json={"lines": [{"item_id": "training-chicken", "counted_quantity": quantity} ]})
    assert saved.status_code == 200
    assert learner.get("/api/v1/counts/training-count/detail").json()["lines"][0]["counted_quantity"] == f"{quantity}.0000"
    posted = learner.post("/api/v1/counts/training-count/submit")
    assert posted.status_code == 200
    assert posted.json()["status"] == "pending_approval"
    assert posted.json()["lines"][0]["snapshot_quantity"] is None
    assert learner.post("/api/v1/counts/training-count/approve-guided").status_code == 403
    assert check(learner, lesson)["passed"] is True


def test_count_approval_posts_real_adjustment(learner):
    begin(learner, "approve-count", "inventory_manager")
    response = learner.post("/api/v1/counts/training-count/approve-guided")
    assert response.status_code == 200, response.text
    assert response.json()["created_by_user_id"] != response.json()["approved_by_user_id"]
    assert response.json()["posted_document_id"]
    assert check(learner, "approve-count")["passed"]


def test_saved_business_state_restores_missing_guide_acknowledgement(learner):
    begin(learner,"blind-count","counter")
    assert learner.put("/api/v1/counts/training-count/entries",json={"lines":[{"item_id":"training-chicken","counted_quantity":21}]}).status_code==200
    # No guide checkpoint was sent, as when the browser closes after Save.
    me=learner.get("/api/v1/training/me")
    assert me.status_code==200,me.text
    assert me.json()["attempt"]["checkpoint"]==2
    assert learner.post("/api/v1/counts/training-count/submit").status_code==200
    assert learner.get("/api/v1/training/me").json()["attempt"]["checkpoint"]==4


@pytest.mark.parametrize("lesson,endpoint,body", [
    ("issue-kitchen", "/stock/issues", {"location_id": "training-store", "lines": [{"item_id": "training-chicken", "quantity": 5}]}),
    ("opening-stock", "/stock/receipts", {"location_id": "training-store", "lines": [{"item_id": "training-chicken", "quantity": 5, "unit_cost": 200}]}),
    ("transfer-stock", "/stock/transfers", {"source_location_id": "training-store", "destination_location_id": "training-kitchen", "lines": [{"item_id": "training-chicken", "quantity": 5}]}),
    ("record-waste", "/inventory-controls/waste", {"item_id":"training-chicken", "location_id":"training-store", "quantity":2, "reason_code":"spoilage"}),
    ("order-supplies", "/purchase-orders", {"supplier_id":"training-supplier", "delivery_location_id":"training-store", "lines":[{"item_id":"training-chicken", "ordered_quantity":10, "unit_price":200}]}),
    ("request-purchase", "/procurement/planning/requisitions", {"department":"Kitchen", "location_id":"training-store", "justification":"busy weekend", "lines":[{"item_id":"training-chicken", "quantity":8,"estimated_unit_cost":200}]}),
    ("staff-meal", "/staff-meals", {"meal_name":"Training staff lunch", "servings":4, "location_id":"training-store", "lines":[{"item_id":"training-chicken", "quantity":2}]}),
    ("supplier-return", "/receiving/purchase-orders/training-po/returns", {"reason":"quality failure", "lines":[{"purchase_order_line_id":"training-po-line","quantity":2}]}),
])
def test_real_transaction_validation(learner, lesson, endpoint, body):
    begin(learner, lesson)
    assert check(learner, lesson)["passed"] is False
    response = learner.post("/api/v1" + endpoint, json=body)
    assert response.status_code in {200,201}, response.text
    assert check(learner, lesson)["passed"] is True


def test_production_actual_material_and_yield(learner):
    begin(learner,"batch-production","inventory_manager")
    assert learner.post("/api/v1/production-batches/training-batch/start").status_code == 200
    posted = learner.post("/api/v1/production-batches/training-batch/execute", json={"actual_output_quantity":10,"output_waste_quantity":0,"materials":[{"item_id":"training-chicken","actual_quantity":3}]})
    assert posted.status_code == 200, posted.text
    assert check(learner,"batch-production")["passed"]


def test_purchase_independent_approval_and_no_stock_addition(learner):
    begin(learner,"purchase-approval","procurement_officer")
    response = learner.post("/api/v1/purchase-orders/training-po/approve")
    assert response.status_code == 200, response.text
    assert check(learner,"purchase-approval")["passed"]


def test_knowledge_alone_never_passes_and_guide_checkpoint_is_not_evidence(learner):
    begin(learner,"partial-delivery","receiver")
    assert learner.post("/api/v1/training/checkpoint",json={"step":8}).status_code == 200
    assert not check(learner,"partial-delivery")["passed"]
    assert learner.post("/api/v1/training/checkpoint",json={"step":100}).status_code == 422


def test_opening_quantity_without_correct_valuation_does_not_pass(learner):
    begin(learner,"opening-stock","inventory_manager")
    response=learner.post("/api/v1/stock/receipts",json={"location_id":"training-store","lines":[{"item_id":"training-chicken","quantity":5,"unit_cost":0}]})
    assert response.status_code==201
    result=check(learner,"opening-stock")
    assert not result["passed"]
    assert "PHP 200 per kg" in result["message"]


def test_reading_requires_observation_and_actual_record_request(learner):
    begin(learner,"available-stock","viewer")
    payload={"answer":"available","observation":"20"}
    assert not learner.post("/api/v1/training/check",json=payload).json()["passed"]
    assert learner.get("/api/v1/availability").status_code == 200
    assert learner.post("/api/v1/training/check",json=payload).json()["passed"]


def test_reset_preserves_history_and_rejects_stale_tab(learner):
    first=begin(learner,"issue-kitchen","inventory_manager")
    second=learner.post("/api/v1/training/start",json={"lesson_id":"issue-kitchen"}).json()
    stale=learner.post("/api/v1/stock/issues",json={"location_id":"training-store","lines":[{"item_id":"training-chicken","quantity":5}]})
    assert stale.status_code == 409
    me=learner.get("/api/v1/training/me").json()
    assert len(me["history"]) == 2
    assert any(row["id"]==first["attempt_id"] and row["status"]=="reset" for row in me["history"])
    assert me["attempt"]["id"]==second["attempt_id"]


def test_role_and_location_restrictions(learner):
    begin(learner,"partial-delivery","receiver")
    session=learner.get("/api/v1/auth/me")
    assert session.status_code==200,session.text
    assert "receiving" in session.json()["accessible_modules"]
    assert learner.post("/api/v1/training/start",json={"lesson_id":"order-supplies"}).status_code==403
    assert learner.post("/api/v1/purchase-orders",json={"supplier_id":"training-supplier","delivery_location_id":"training-store","lines":[{"item_id":"training-chicken","ordered_quantity":1,"unit_price":200}]}).status_code==403
    assert learner.get("/api/v1/stock/balances?location_id=training-restricted").status_code==403


@pytest.mark.parametrize("path", ["/integrations/accounting/events/fictional/requeue", "/integrations/staff/employees", "/integration-events/process", "/master-data/publish", "/auth/login"])
def test_external_delivery_and_service_endpoints_disabled(learner,path):
    begin(learner,"accounting-proof")
    assert learner.post("/api/v1"+path,json={}).status_code==403


def test_isolated_concurrent_users(app):
    def run(quantity):
        client=TestClient(app);client.headers["X-Requested-With"]="HiddenOasisInventory"
        begin(client,"issue-kitchen","inventory_manager")
        response=client.post("/api/v1/stock/issues",json={"location_id":"training-store","lines":[{"item_id":"training-chicken","quantity":quantity}]})
        assert response.status_code==201,response.text
        return client.get("/api/v1/stock/balances?location_id=training-store&item_id=training-chicken").json()[0]["quantity"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        quantities=list(pool.map(run,[3,5]))
    assert quantities==["21.0000","19.0000"]


def test_independent_assessment_locked_until_both_practice_levels(learner):
    begin(learner,"issue-kitchen","inventory_manager")
    assert learner.post("/api/v1/training/start",json={"lesson_id":"issue-kitchen","mode":"independent"}).status_code==409


def test_outdated_attempt_cannot_post_or_certify_under_a_new_curriculum(learner,app):
    result=begin(learner,"issue-kitchen","inventory_manager")
    with app.state.training_store.connect() as db:
        db.execute("UPDATE attempts SET curriculum_version='old' WHERE id=?",(result["attempt_id"],))
    assert learner.get("/api/v1/training/me").json()["attempt"] is None
    assert learner.post("/api/v1/stock/issues",json={"location_id":"training-store","lines":[{"item_id":"training-chicken","quantity":5}]}).status_code==409
    assert learner.post("/api/v1/training/check",json={"answer":"issue"}).status_code==409


def test_mastery_requires_different_independent_business_outcome_and_no_hints(learner):
    from training.curriculum import BY_ID
    begin(learner,"issue-kitchen","inventory_manager")
    for mode,quantity in [("guided",5),("assisted",4),("independent",3)]:
        if mode!="guided":
            result=learner.post("/api/v1/training/start",json={"lesson_id":"issue-kitchen","mode":mode})
            assert result.status_code==200,result.text
            learner.headers["X-Training-Attempt"]=result.json()["attempt_id"]
        response=learner.post("/api/v1/stock/issues",json={"location_id":"training-store","lines":[{"item_id":"training-chicken","quantity":quantity}]})
        assert response.status_code==201,response.text
        assert check(learner,"issue-kitchen")["passed"]
    repeat=learner.post("/api/v1/training/start",json={"lesson_id":"issue-kitchen","mode":"independent"})
    learner.headers["X-Training-Attempt"]=repeat.json()["attempt_id"]
    assert learner.post("/api/v1/training/hint").status_code==200
    learner.post("/api/v1/stock/issues",json={"location_id":"training-store","lines":[{"item_id":"training-chicken","quantity":3}]})
    assert not check(learner,"issue-kitchen")["passed"]


def test_manager_roster_not_exposed_to_self_selected_owner(learner):
    begin(learner,"accounting-proof","owner")
    assert learner.get("/api/v1/training/management").status_code==403
    assert learner.post("/api/v1/training/assign",json={"learner_id":"other","role":"owner"}).status_code==403


@pytest.mark.parametrize("active", [False, True])
def test_sign_out_separates_employees_and_preserves_trainer_history(learner,app,active):
    first=learner.post("/api/v1/training/enrol",json={"name":"First employee","role":"receiver"}).json()
    if active:
        assert learner.post("/api/v1/training/start",json={"lesson_id":"partial-delivery"}).status_code==200
    response=learner.post("/api/v1/auth/logout")
    assert response.status_code==204
    assert response.headers["x-inventory-environment"]=="isolated-training"
    assert learner.get("/api/v1/training/me").status_code==401
    second=learner.post("/api/v1/training/enrol",json={"name":"Second employee","role":"receiver"}).json()
    assert first["id"]!=second["id"]
    assert learner.get("/api/v1/training/me").json()["history"]==[]
    assert len(app.state.training_store.history(first["id"]))==int(active)


def test_authorized_trainer_can_review_and_reassign_without_losing_history(learner,app):
    begin(learner,"issue-kitchen","inventory_manager")
    me=learner.get("/api/v1/training/me").json()
    key=(app.state.training_store.root/"manager-key").read_text()
    headers={"X-Training-Manager-Key":key}
    roster=learner.get("/api/v1/training/management",headers=headers)
    assert roster.status_code==200
    assert any(row["id"]==me["learner"]["id"] for row in roster.json()["learners"])
    response=learner.post("/api/v1/training/assign",headers=headers,json={"learner_id":me["learner"]["id"],"role":"receiver"})
    assert response.status_code==200
    after=learner.get("/api/v1/training/me").json()
    assert after["learner"]["role"]=="receiver"
    assert after["attempt"] is None
    assert len(after["history"])==1 and after["history"][0]["status"]=="reset"


@pytest.mark.parametrize("key,value", [("DATABASE_URL","postgresql://production/database"),("APP_ENV","production"),("JWT_SECRET","production-secret"),("INTEGRATION_ENDPOINTS_JSON",'{"accounting":"http://127.0.0.1:8000"}'),("STAFF_INTEGRATION_TOKEN","production-token"),("NEXT_PUBLIC_API_URL","https://inventory.hiddenoasis.app/api/v1")])
def test_production_configuration_fails_before_database_creation(tmp_path,key,value):
    script="from pathlib import Path; from training.safety import configure; configure(Path("+repr(str(tmp_path/"inventory-training"))+"))"
    env={k:v for k,v in os.environ.items() if k not in {"DATABASE_URL","JWT_SECRET","APP_ENV","NEXT_PUBLIC_API_URL"} and "INTEGRATION" not in k}
    env[key]=value
    result=subprocess.run([sys.executable,"-c",script],env=env,capture_output=True,text=True)
    assert result.returncode!=0
    assert not (tmp_path/"inventory-training").exists()


def test_network_guard_denies_http_and_loopback_in_subprocess():
    script='''from training.safety import install_network_guard
install_network_guard()
import socket
for host in ["127.0.0.1","inventory.hiddenoasis.app","10.0.0.1"]:
    try: socket.create_connection((host,443),timeout=.1)
    except PermissionError: pass
    else: raise AssertionError(host)
print("outbound connections denied")
'''
    result=subprocess.run([sys.executable,"-c",script],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert "outbound connections denied" in result.stdout


def test_dedicated_launcher_initializes_os_loop_before_guard_and_serves_requests(tmp_path):
    import socket
    import time
    from urllib.request import urlopen
    with socket.socket() as listener:
        listener.bind(("127.0.0.1",0))
        port=listener.getsockname()[1]
    # Simulate Windows' loopback-based private socketpair initialization on
    # every OS. This fails if guard installation moves ahead of loop creation.
    script='''import asyncio, socket, sys
original=asyncio.events.new_event_loop
def initialize():
    with socket.socket() as probe:
        probe.settimeout(.1)
        probe.connect_ex(("127.0.0.1",9))
    return original()
asyncio.events.new_event_loop=initialize
from training.launch import main
main()
'''
    env={k:v for k,v in os.environ.items() if k not in {"DATABASE_URL","JWT_SECRET","BOOTSTRAP_OWNER_PASSWORD","INTERNAL_API_URL","NEXT_PUBLIC_API_URL"} and "INTEGRATION" not in k and not k.startswith(("PGHOST","PGDATABASE","PGUSER","PGPASSWORD"))}
    child=subprocess.Popen([sys.executable,"-c",script,"--data",str(tmp_path/"inventory-training"),"--port",str(port)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    try:
        for _ in range(100):
            if child.poll() is not None:
                pytest.fail(child.stderr.read())
            try:
                with urlopen(f"http://127.0.0.1:{port}/api/v1/training/catalogue",timeout=.2) as response:
                    assert json.load(response)["environment"]=="isolated-training"
                break
            except OSError:
                time.sleep(.1)
        else: pytest.fail("Dedicated launcher did not become ready")
    finally:
        child.terminate()
        child.wait(timeout=10)
