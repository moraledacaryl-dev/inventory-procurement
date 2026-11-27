"""Circulation conserves property; financial and maintenance actions stay local."""
import pytest
from conftest import begin
from training.property_lessons import LESSONS


def perform(client,lesson,v):
    id=lesson.id
    if id in {"issue-clean-linen","send-used-linen-to-laundry","return-clean-linen"}:return client.post("/api/v1/property/movements",json={"item_id":v["linen"],"quantity":v["quantity"],"source_location_id":v["property_source"],"destination_location_id":v["property_destination"],"source_condition_id":v["property_from_condition"],"destination_condition_id":v["property_to_condition"],"movement_reason_id":v["property_reason"],"reference":v["reference"]})
    if id=="configure-room-par":return client.post("/api/v1/hotel/par-profiles",json={"code":"TRAIN-ROOM-PAR","name":"Training standard room","profile_type":"room_type","location_id":v["kitchen"],"lines":[{"item_id":v["linen"],"par_quantity":v["quantity"]}]})
    if id=="register-fixed-asset":return client.post("/api/v1/assets",json={"asset_tag":"TRAIN-FAN-02","item_id":v["asset_item"],"asset_class_id":v["asset_class"],"depreciation_method_id":v["asset_method"],"location_id":v["store"],"acquisition_date":"2026-11-01","placed_in_service_date":"2026-11-01","acquisition_cost":6000,"useful_life_months":60})
    if id=="create-maintenance-plan":return client.post("/api/v1/maintenance/plans",json={"code":"TRAIN-FAN-CARE","name":"Fan safety check","asset_id":v["asset"],"interval_days":30,"next_due_date":"2026-12-01","checklist":"Check guard and clean filter"})
    if id=="create-maintenance-work-order":return client.post("/api/v1/maintenance/work-orders",json={"asset_id":v["asset"],"title":"Inspect fan guard","priority":"high","scheduled_date":"2026-12-01","description":v["reference"],"parts":[]})
    if id=="start-maintenance-work":return client.post("/api/v1/maintenance/work-orders/training-work/start")
    if id=="complete-costed-maintenance":return client.post("/api/v1/maintenance/work-orders/training-work/complete",json={"labor_cost":v["work_labor"],"external_cost":v["work_external"],"downtime_hours":v["work_downtime"],"completion_notes":v["reference"]})
    if id=="complete-maintenance-work":return client.post("/api/v1/maintenance/work-orders/training-work/complete",json={"labor_cost":0,"external_cost":0,"downtime_hours":0})
    if id=="prepare-depreciation-run":return client.post("/api/v1/depreciation-runs",json={"period":"2026-11"})
    run=client.get("/api/v1/depreciation-runs").json()[0]
    return client.post(f"/api/v1/depreciation-runs/{run['id']}/post")


@pytest.mark.parametrize("lesson",LESSONS,ids=lambda lesson:lesson.id)
def test_property_real_outcomes_all_modes(learner,lesson):
    from training.scenarios import values
    for mode in ("guided","assisted","independent"):
        if mode=="guided":begin(learner,lesson.id,lesson.roles[0])
        else:
            response=learner.post("/api/v1/training/start",json={"lesson_id":lesson.id,"mode":mode})
            assert response.status_code==200,response.text
            learner.headers["X-Training-Attempt"]=response.json()["attempt_id"]
        assert not learner.post("/api/v1/training/check",json={"answer":"no"}).json()["passed"]
        response=perform(learner,lesson,values(lesson,mode))
        expected=200 if lesson.id in {"start-maintenance-work","complete-maintenance-work","complete-costed-maintenance","post-reviewed-depreciation"} else 201
        assert response.status_code==expected,response.text
        result=learner.post("/api/v1/training/check",json={"answer":"no"}).json()
        assert result["passed"],result
        assert learner.get("/api/v1/training/me").json()["attempt"]["checkpoint"]==len(lesson.steps)


def test_laundry_is_not_clean_availability(learner):
    from training.scenarios import values
    from training.curriculum import BY_ID
    lesson=BY_ID["send-used-linen-to-laundry"]
    begin(learner,lesson.id,"inventory_manager")
    v=values(lesson,"guided")
    response=learner.post("/api/v1/property/movements",json={"item_id":v["linen"],"quantity":v["quantity"],"source_location_id":v["property_source"],"destination_location_id":v["property_destination"],"source_condition_id":v["property_from_condition"],"destination_condition_id":"10000000-0000-5000-8000-000000000001","movement_reason_id":v["property_reason"],"reference":v["reference"]})
    assert response.status_code==201,response.text
    result=learner.post("/api/v1/training/check",json={"answer":"no"}).json()
    assert not result["passed"]
    assert "In laundry" in result["message"]


def test_posted_depreciation_cannot_be_posted_twice(learner):
    from training.scenarios import values
    from training.curriculum import BY_ID
    lesson=BY_ID["post-reviewed-depreciation"]
    begin(learner,lesson.id,"inventory_manager")
    v=values(lesson,"guided")
    assert perform(learner,lesson,v).status_code==200
    assert perform(learner,lesson,v).status_code==409
    assert learner.post("/api/v1/training/check",json={"answer":"no"}).json()["passed"]
