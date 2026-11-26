"""Transaction, transit, lot and blind-count outcome certification."""
import pytest
from conftest import begin
from training.control_lessons import LESSONS


def perform(client,lesson,v):
    id=lesson.id
    def request(method,path,payload=None,status=200):
        response=client.request(method,"/api/v1"+path,**({"json":payload} if payload is not None else {}))
        assert response.status_code==status,response.text
        return response.json() if response.status_code!=204 else None
    if id in {"reserve-event-stock","reservation-shortage"}:
        return request("POST","/reservations",{"item_id":v["chicken"],"location_id":v["store"],"quantity":v["quantity"] if id=="reserve-event-stock" else v["reservation_overage"],"reference_type":"event","reference_id":v["reference"]},201 if id=="reserve-event-stock" else 409)
    if id in {"create-controlled-transfer","correct-transfer-destination"}:
        body={"source_location_id":v["store"],"destination_location_id":v["kitchen"],"notes":v["reference"],"lines":[{"item_id":v["chicken"],"quantity":v["quantity"]}]}
        if id=="correct-transfer-destination":request("POST","/transfer-orders",{**body,"destination_location_id":v["store"]},422)
        return request("POST","/transfer-orders",body,201)
    if id in {"dispatch-controlled-transfer","transfer-stock-became-unavailable","transfer-transit-scope-required"}:
        return request("POST","/transfer-orders/training-transfer/dispatch",status=403 if id=="transfer-transit-scope-required" else 409 if id=="transfer-stock-became-unavailable" else 200)
    if id in {"receive-controlled-transfer","transfer-receipt-variance"}:
        return request("POST","/transfer-orders/training-transfer/receive",{"lines":[{"item_id":v["chicken"],"received_quantity":v["quantity"] if id=="receive-controlled-transfer" else v["transfer_accepted"],"variance_reason":"damaged in transit" if id=="transfer-receipt-variance" else None}]})
    if id=="cancel-draft-transfer":return request("POST","/transfer-orders/training-transfer/cancel")
    if id in {"count-multiple-units","start-full-count","save-incomplete-count"}:
        count_id=v["count"]
        if id=="start-full-count":
            count=request("POST","/counts",{"location_id":v["store"],"notes":v["reference"],"blind_count":True,"approval_threshold":1},201)
            count_id=count["id"]
        lines=[{"item_id":v["chicken"],"counted_quantity":v["quantity"]}]
        if id!="save-incomplete-count":lines.append({"item_id":v["amenities"],"counted_quantity":v["secondary_count"]})
        if id=="start-full-count":lines.append({"item_id":v["alfredo"],"counted_quantity":0})
        saved=request("PUT",f"/counts/{count_id}/entries",{"lines":lines})
        assert all(line["snapshot_quantity"] is None and line["live_quantity"] is None for line in saved["lines"])
        if id!="save-incomplete-count":return request("POST",f"/counts/{count_id}/submit")
        return saved
    if id=="request-count-recheck":return request("POST","/counts/training-count/recount",{"item_ids":[v["chicken"]],"reason":"verify scale and units"})
    if id=="stale-count-snapshot":return request("POST","/counts/training-count/submit",status=409)
    if id=="cancel-unused-count":return request("POST","/counts/training-count/cancel-guided")
    if id=="approved-opening-correction":return request("POST","/inventory-controls/adjustments",{"location_id":v["store"],"reason_code":"correction","reference":v["reference"],"lines":[{"item_id":v["chicken"],"quantity_delta":-v["quantity"]}]},201)
    if id=="create-traceable-lot":return request("POST","/lots",{"item_id":v["chicken"],"lot_number":v["lot_number"],"manufactured_date":"2026-11-01","expiry_date":"2026-12-15","supplier_id":v["supplier"]},201)
    if id=="expired-lot-writeoff":return request("POST","/inventory-controls/waste",{"item_id":v["chicken"],"location_id":v["store"],"lot_id":v["lot_id"],"quantity":v["quantity"],"reason_code":"expired"},201)
    return request("POST","/lot-transactions",{"lot_id":v["lot_id"],"location_id":v["store"],"quantity":v["lot_overissue"] if id=="lot-quantity-shortage" else v["quantity"],"unit_cost":200,"transaction_type":v["lot_action"],"reason":v["lot_reason"]},409 if id=="lot-quantity-shortage" else 201)


@pytest.mark.parametrize("lesson",LESSONS,ids=lambda lesson:lesson.id)
def test_real_control_outcomes_in_all_modes(learner,lesson):
    from training.scenarios import values
    for mode in ("guided","assisted","independent"):
        if mode=="guided":begin(learner,lesson.id,lesson.roles[0])
        else:
            response=learner.post("/api/v1/training/start",json={"lesson_id":lesson.id,"mode":mode})
            assert response.status_code==200,response.text
            learner.headers["X-Training-Attempt"]=response.json()["attempt_id"]
        assert not learner.post("/api/v1/training/check",json={"answer":lesson.answer}).json()["passed"]
        perform(learner,lesson,values(lesson,mode))
        result=learner.post("/api/v1/training/check",json={"answer":lesson.answer}).json()
        assert result["passed"],result
        if lesson.module=="G":assert "physical_quantity" not in result["evidence"]
        me=learner.get("/api/v1/training/me").json()
        assert me["attempt"]["checkpoint"]==len(lesson.steps)


def test_created_count_restores_its_real_route_and_partial_saved_checkpoint(learner):
    begin(learner,"start-full-count","counter")
    created=learner.post("/api/v1/counts",json={"location_id":"training-store","notes":"TRAIN-START-FULL-COUNT-GUIDED","blind_count":True,"approval_threshold":1}).json()
    me=learner.get("/api/v1/training/me").json()
    assert me["lesson"]["route"]==f"/counts/{created['id']}"
    assert me["attempt"]["checkpoint"]==5
    saved=learner.put(f"/api/v1/counts/{created['id']}/entries",json={"lines":[{"item_id":"training-chicken","counted_quantity":21}]})
    assert saved.status_code==200,saved.text
    me=learner.get("/api/v1/training/me").json()
    assert me["attempt"]["checkpoint"]==6
    assert all(line["snapshot_quantity"] is None for line in saved.json()["lines"])


def test_box_quantity_is_not_accepted_as_individual_kits(learner):
    begin(learner,"count-multiple-units","counter")
    assert learner.put("/api/v1/counts/training-count/entries",json={"lines":[{"item_id":"training-chicken","counted_quantity":21},{"item_id":"training-amenities","counted_quantity":2}]}).status_code==200
    assert learner.post("/api/v1/counts/training-count/submit").status_code==200
    result=learner.post("/api/v1/training/check",json={"answer":"2.5"}).json()
    assert not result["passed"]
    assert "individual kits" in result["message"]


@pytest.mark.parametrize("role",["inventory_manager","owner"])
def test_full_count_uses_assigned_review_limit_in_every_approver_role(learner,role):
    from training.curriculum import BY_ID
    from training.scenarios import values
    lesson=BY_ID["start-full-count"]
    for mode in ("guided","assisted","independent"):
        if mode=="guided":begin(learner,lesson.id,role)
        else:
            response=learner.post("/api/v1/training/start",json={"lesson_id":lesson.id,"mode":mode})
            assert response.status_code==200,response.text
            learner.headers["X-Training-Attempt"]=response.json()["attempt_id"]
        assert perform(learner,lesson,values(lesson,mode))["status"]=="pending_approval"
        assert learner.post("/api/v1/training/check",json={"answer":"no"}).json()["passed"]
