"""All assigned read roles inspect actual permitted records and unchanged results."""
import pytest
from sqlalchemy import select
from conftest import begin
from training.curriculum import LESSONS,BY_ID
from training.scenarios import practical_question,engine_for,inspection_endpoint,values
from training.report_scenarios import PERIOD_FILTERS,verify_report
from training.pos_review_scenarios import verify_pos_review
from app.models import StockBalance,CountSession,PosSaleEvent,User
from sqlalchemy.orm import Session

READ_ROLES=[(lesson.id,role) for lesson in LESSONS if lesson.workflow.startswith("read_") for role in lesson.roles]
NEW_READS=[lesson.id for lesson in LESSONS if lesson.workflow in {"read_report","read_pos"}]

def inspect(client,id):
    profile=client.get("/api/v1/training/me").json()
    path=profile["lesson"]["inspection_api_path"]
    return client.get(path,params=profile["lesson"].get("inspection_query") or {})

@pytest.mark.parametrize("id,role",READ_ROLES)
def test_every_assigned_read_role_can_observe_the_required_live_source_record(learner,id,role):
    begin(learner,id,role)
    record=inspect(learner,id)
    assert record.status_code==200,(id,role,record.text)
    _,observation,_=practical_question(BY_ID[id],"guided")
    if id=="supplier-profile":assert next(row for row in record.json()["items"] if row["item_id"]=="training-chicken")["lead_time_days"]==3
    if id=="interpret-posted-count":
        line=record.json()["lines"][0]
        assert line["variance_quantity"] is not None,record.text
    result=learner.post("/api/v1/training/check",json={"answer":BY_ID[id].answer,"observation":observation})
    assert result.status_code==200,result.text
    assert result.json()["passed"],result.json()

@pytest.mark.parametrize("id",NEW_READS)
@pytest.mark.parametrize("mode",["assisted","independent"])
def test_new_review_modes_require_the_actual_record_and_preserve_real_result(learner,id,mode):
    begin(learner,id,"owner")
    for previous in (["guided"] if mode=="assisted" else ["guided","assisted"]):
        if previous!="guided":
            started=learner.post("/api/v1/training/start",json={"lesson_id":id,"mode":previous});assert started.status_code==200,started.text
            learner.headers["X-Training-Attempt"]=started.json()["attempt_id"]
        _,answer,_=practical_question(BY_ID[id],previous)
        assert inspect(learner,id).status_code==200
        assert learner.post("/api/v1/training/check",json={"answer":BY_ID[id].answer,"observation":answer}).json()["passed"]
    started=learner.post("/api/v1/training/start",json={"lesson_id":id,"mode":mode});assert started.status_code==200,started.text
    learner.headers["X-Training-Attempt"]=started.json()["attempt_id"]
    lesson=BY_ID[id];_,observation,_=practical_question(lesson,mode)
    payload={"answer":lesson.answer,"observation":observation}
    assert not learner.post("/api/v1/training/check",json=payload).json()["passed"]
    assert inspect(learner,id).status_code==200
    assert not learner.post("/api/v1/training/check",json={**payload,"observation":"wrong record"}).json()["passed"]
    assert learner.post("/api/v1/training/check",json=payload).json()["passed"]


def test_period_issues_requires_the_exact_item_location_type_and_dates_not_an_unfiltered_read(learner):
    begin(learner,"interpret-period-issues","viewer")
    payload={"answer":"no","observation":"-6"}
    for omit in PERIOD_FILTERS:
        params={key:value for key,value in PERIOD_FILTERS.items() if key!=omit}
        assert learner.get("/api/v1/stock/ledger",params=params).status_code==200
        assert not learner.post("/api/v1/training/check",json=payload).json()["passed"],omit
    record=inspect(learner,"interpret-period-issues").json()
    assert len(record["rows"])==1
    assert record["rows"][0]["reference"]=="TRAIN-PERIOD-ISSUE"
    assert float(record["summary"]["net_quantity"])==-6
    assert float(record["rows"][0]["running_quantity"])==16
    assert learner.post("/api/v1/training/check",json=payload).json()["passed"]


def test_cooked_return_cannot_restore_ingredients_and_same_event_cannot_change_identity(learner):
    begin(learner,"inspect-cooked-sale-return","owner")
    from app.api.routes.production import process_pos_event
    from app.schemas.production import PosSaleEventIn
    from fastapi import HTTPException
    path=learner.app.state.training_store.root/f"attempt-{learner.headers['X-Training-Attempt']}.sqlite"
    engine=engine_for(path)
    try:
        with Session(engine) as db:
            original=db.scalar(select(PosSaleEvent).where(PosSaleEvent.external_event_id=="TRAIN-SALE-COMPLETED"))
            changed={**original.payload,"external_sale_id":"TRAIN-DIFFERENT-SALE"}
            with pytest.raises(HTTPException) as conflict:process_pos_event(PosSaleEventIn.model_validate(changed),db,db.get(User,"training-colleague"))
            assert conflict.value.status_code==409
            with pytest.raises(HTTPException) as conflict:process_pos_event(PosSaleEventIn(external_event_id="TRAIN-UNSAFE-RETURN",external_sale_id="TRAIN-SALE",event_type="sale_returned",lines=[{"external_product_id":"TRAIN-POS-ALFREDO","quantity":1,"inventory_disposition":"restore_stock"}]),db,db.get(User,"training-colleague"))
            assert conflict.value.status_code==409
            assert verify_pos_review(db,BY_ID["inspect-cooked-sale-return"],values(BY_ID["inspect-cooked-sale-return"],"guided"))[0]
    finally:engine.dispose()
