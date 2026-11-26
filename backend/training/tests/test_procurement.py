"""Purchasing decisions, relationships, refusal and recovery evidence."""
import pytest
from conftest import begin
from training.procurement_lessons import LESSONS


def perform(client,lesson,v,cheap=False):
    id=lesson.id
    if id in {"approve-purchase-request","request-self-approval","reject-duplicate-request"}:
        path="/requisitions/training-requisition/"+("reject" if id=="reject-duplicate-request" else "approve")
        return client.post("/api/v1"+path)
    if id=="record-supplier-quotation":return client.post("/api/v1/quotations",json={"requisition_id":"training-requisition","supplier_id":v["supplier"],"delivery_days":1,"payment_terms_days":v["terms"],"notes":v["reference"],"lines":[{"item_id":v["chicken"],"quantity":v["quantity"],"unit_price":220}]})
    if id=="award-timely-quotation":return client.post("/api/v1/requisitions/training-requisition/award-quotation",json={"quotation_id":"training-quote-cheap" if cheap else "training-quote-fast","delivery_location_id":v["store"]})
    if id=="purchase-approval-limit":return client.post("/api/v1/purchase-orders/training-po/approve")
    if id=="amend-draft-order":return client.patch("/api/v1/purchase-orders/training-po/amend",json={"notes":v["reference"],"lines":[{"item_id":v["chicken"],"ordered_quantity":v["quantity"],"unit_price":220}]})
    if id=="cancel-unreceived-order":return client.post("/api/v1/purchase-orders/training-po/cancel-workspace")


@pytest.mark.parametrize("lesson",LESSONS,ids=lambda lesson:lesson.id)
def test_procurement_real_outcomes_all_modes(learner,lesson):
    from training.scenarios import values,practical_question,inspection_endpoint
    for mode in ("guided","assisted","independent"):
        if mode=="guided":begin(learner,lesson.id,lesson.roles[0])
        else:
            response=learner.post("/api/v1/training/start",json={"lesson_id":lesson.id,"mode":mode})
            assert response.status_code==200,response.text
            learner.headers["X-Training-Attempt"]=response.json()["attempt_id"]
        body={"answer":lesson.answer}
        assert not learner.post("/api/v1/training/check",json=body).json()["passed"]
        if lesson.workflow.startswith("read_"):
            _,body["observation"],_=practical_question(lesson,mode)
            assert learner.get(inspection_endpoint(lesson)).status_code==200
            if lesson.id=="inspect-awarded-order":
                me=learner.get("/api/v1/training/me").json()
                assert not me["record_inspected"]
                assert learner.get(me["lesson"]["inspection_api_path"]).status_code==200
            if lesson.id!="inspect-awarded-order":
                controls=learner.get(inspection_endpoint(lesson)).json()["controls"]
                assert not controls["can_amend"]
                if lesson.id=="inspect-received-order-lock":assert not controls["can_cancel"]
        else:
            response=perform(learner,lesson,values(lesson,mode))
            expected=409 if lesson.id=="request-self-approval" else 403 if lesson.id=="purchase-approval-limit" else 201 if lesson.module=="K" else 200
            assert response.status_code==expected,response.text
        result=learner.post("/api/v1/training/check",json=body).json()
        assert result["passed"],result
        if lesson.steps:assert learner.get("/api/v1/training/me").json()["attempt"]["checkpoint"]==len(lesson.steps)


def test_lowest_price_missing_deadline_does_not_pass(learner):
    from training.curriculum import BY_ID
    from training.scenarios import values
    lesson=BY_ID["award-timely-quotation"]
    begin(learner,lesson.id,"procurement_officer")
    assert perform(learner,lesson,values(lesson,"guided"),cheap=True).status_code==201
    result=learner.post("/api/v1/training/check",json={"answer":"no"}).json()
    assert not result["passed"]
    assert "two days" in result["message"]


def test_award_recovers_committed_result_without_duplicate_order(learner):
    from training.curriculum import BY_ID
    from training.scenarios import values
    lesson=BY_ID["award-timely-quotation"]
    begin(learner,lesson.id,"procurement_officer")
    assert perform(learner,lesson,values(lesson,"guided")).status_code==201
    assert learner.get("/api/v1/training/me").json()["attempt"]["checkpoint"]==len(lesson.steps)
    assert perform(learner,lesson,values(lesson,"guided")).status_code==409
    orders=learner.get("/api/v1/purchase-orders").json()
    assert len([row for row in orders if row["quotation_id"]=="training-quote-fast"])==1


def test_workspace_summary_cannot_replace_inspecting_the_linked_order(learner):
    begin(learner,"inspect-awarded-order","procurement_officer")
    assert learner.get("/api/v1/procurement/quotation-workspace").status_code==200
    result=learner.post("/api/v1/training/check",json={"answer":"no","observation":"draft"}).json()
    assert not result["passed"]
    path=learner.get("/api/v1/training/me").json()["lesson"]["inspection_api_path"]
    assert learner.get(path).status_code==200
    assert learner.post("/api/v1/training/check",json={"answer":"no","observation":"draft"}).json()["passed"]


def test_inspection_cannot_pass_after_changing_the_record(learner):
    begin(learner,"inspect-approved-order-lock","procurement_officer")
    assert learner.post("/api/v1/purchase-orders/training-po/cancel-workspace").status_code==200
    assert learner.get("/api/v1/purchase-orders/training-po/detail").status_code==200
    assert not learner.post("/api/v1/training/check",json={"answer":"no","observation":"approved"}).json()["passed"]
