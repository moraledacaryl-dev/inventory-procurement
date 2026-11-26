"""Local decision/retry controls never enable integration intake or delivery."""
import pytest
from conftest import begin
from training.connected_lessons import LESSONS
from training.connected_scenarios import local_control_allowed


def perform(client,lesson,assignee="training-colleague"):
    if lesson.module=="W":return client.post("/api/v1/integrations/accounting/events/training-retry/requeue")
    decision,notes={"accept-accountable-operations-work":("accepted","verified need"),"reject-duplicate-operations-work":("rejected","duplicate demand"),"complete-evidenced-operations-work":("completed","handover confirmed")}[lesson.id]
    return client.post("/api/v1/integrations/operations/requests/training-connected-request/decision",json={"decision":decision,"notes":notes,"assigned_to_user_id":assignee if decision=="accepted" else None})


@pytest.mark.parametrize("lesson",LESSONS,ids=lambda lesson:lesson.id)
def test_real_local_integration_outcomes_all_modes(learner,lesson):
    for mode in ("guided","assisted","independent"):
        if mode=="guided":begin(learner,lesson.id,"owner")
        else:
            response=learner.post("/api/v1/training/start",json={"lesson_id":lesson.id,"mode":mode})
            assert response.status_code==200,response.text
            learner.headers["X-Training-Attempt"]=response.json()["attempt_id"]
        assert not learner.post("/api/v1/training/check",json={"answer":"no"}).json()["passed"]
        response=perform(learner,lesson)
        assert response.status_code==200,response.text
        result=learner.post("/api/v1/training/check",json={"answer":"no"}).json()
        assert result["passed"],result
        assert result["evidence"]["external_delivery_started"] is False
        assert learner.get("/api/v1/training/me").json()["attempt"]["checkpoint"]==len(lesson.steps)


@pytest.mark.parametrize("path",["/integrations/pos/events","/integrations/operations/requests","/integrations/staff/employees","/integrations/accounting/receipts","/integration-events/process","/master-data/publish"])
def test_local_decision_exception_does_not_enable_external_services(learner,path):
    begin(learner,"accept-accountable-operations-work","owner")
    assert learner.post("/api/v1"+path,json={}).status_code==403


def test_control_allowlist_is_exact_and_task_scoped():
    from training.curriculum import BY_ID
    lesson=BY_ID["requeue-failed-accounting-handoff"]
    path="/api/v1/integrations/accounting/events/training-retry/requeue"
    assert local_control_allowed("POST",path,lesson)
    for method in ("GET","PUT","PATCH","DELETE"):assert not local_control_allowed(method,path,lesson)
    for suffix in ("/process","/extra","?deliver=true"):
        assert not local_control_allowed("POST",path+suffix,lesson)
    assert not local_control_allowed("POST",path,BY_ID["accounting-proof"])


def test_wrong_accountable_person_does_not_pass(learner):
    from training.curriculum import BY_ID
    begin(learner,"accept-accountable-operations-work","owner")
    assert perform(learner,BY_ID["accept-accountable-operations-work"],assignee="training-actor").status_code==200
    result=learner.post("/api/v1/training/check",json={"answer":"no"}).json()
    assert not result["passed"]
    assert "Fictional colleague" in result["message"]


def test_accepted_accounting_event_still_cannot_be_requeued(learner,app):
    from sqlalchemy.orm import Session
    from training.scenarios import engine_for
    from app.models.operations import IntegrationEvent
    started=begin(learner,"requeue-failed-accounting-handoff","owner")
    engine=engine_for(app.state.training_store.root/f"attempt-{started['attempt_id']}.sqlite")
    with Session(engine) as db:
        event=db.get(IntegrationEvent,"training-retry")
        event.payload={**event.payload,"accounting_receipt":{"accepted":True}}
        db.commit()
    engine.dispose()
    response=learner.post("/api/v1/integrations/accounting/events/training-retry/requeue")
    assert response.status_code==409,response.text
    assert "Accepted accounting events" in response.text
