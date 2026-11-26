"""One sandbox retains linked learner and independent counterpart outcomes."""
import pytest
from conftest import begin


def perform_monthly(client,v):
    body={"lines":[{"item_id":v["chicken"],"counted_quantity":v["quantity"]},{"item_id":v["amenities"],"counted_quantity":v["cap_kit_count"]}]}
    saved=client.put("/api/v1/counts/training-count/entries",json=body)
    assert saved.status_code==200,saved.text
    assert all(line["snapshot_quantity"] is None for line in saved.json()["lines"])
    submitted=client.post("/api/v1/counts/training-count/submit")
    assert submitted.status_code==200,submitted.text
    refreshed=client.get("/api/v1/counts/training-count/detail")
    assert refreshed.status_code==200
    assert refreshed.json()["status"]=="posted"
    return refreshed.json()


def receive(client,v):
    result=client.post("/api/v1/receiving/purchase-orders/training-po",json={"delivery_reference":v["reference"],"lines":[{"purchase_order_line_id":v["po-line"],"received_quantity":v["quantity"],"accepted_quantity":v["quantity"]-2,"rejected_quantity":2,"discrepancy_reason":"damaged or unusable goods"}]})
    assert result.status_code==201,result.text
    return result.json()


def return_one(client,v):
    result=client.post("/api/v1/receiving/purchase-orders/training-po/returns",json={"reason":"quality failure","lines":[{"purchase_order_line_id":v["po-line"],"quantity":1}]})
    assert result.status_code==201,result.text
    return result.json()


@pytest.mark.parametrize("lesson,role",[("cap-monthly-count","counter"),("cap-monthly-count","inventory_manager"),("cap-monthly-count","owner"),("cap-delivery-recovery","receiver"),("cap-delivery-recovery","owner")])
def test_linked_capstone_in_every_assigned_role_and_mode(learner,lesson,role):
    from training.curriculum import BY_ID
    from training.scenarios import values
    for mode in ("guided","assisted","independent"):
        if mode=="guided":begin(learner,lesson,role)
        else:
            response=learner.post("/api/v1/training/start",json={"lesson_id":lesson,"mode":mode})
            assert response.status_code==200,response.text
            learner.headers["X-Training-Attempt"]=response.json()["attempt_id"]
        v=values(BY_ID[lesson],mode)
        assert not learner.post("/api/v1/training/check",json={"answer":"no"}).json()["passed"]
        if lesson=="cap-monthly-count":
            detail=perform_monthly(learner,v)
            assert detail["created_by_user_id"]==v["actor"]
            assert detail["approved_by_user_id"]==v["reviewer"]
        else:
            receipt=receive(learner,v)
            assert not learner.post("/api/v1/training/check",json={"answer":"no"}).json()["passed"]
            returned=return_one(learner,v)
            assert receipt["purchase_order_id"]==returned["purchase_order_id"]==v["po"]
        result=learner.post("/api/v1/training/check",json={"answer":"no"}).json()
        assert result["passed"],result
        assert result["evidence"]["practical_score"]==100
        assert result["evidence"]["critical_pass"]
        assert all(row["passed"] for row in result["evidence"]["objectives"])
        if lesson=="cap-monthly-count":assert "physical_quantity" not in result["evidence"] and "snapshot" not in str(result["evidence"])
        assert learner.get("/api/v1/training/me").json()["attempt"]["checkpoint"]==len(BY_ID[lesson].steps)


def test_delivery_capstone_resumes_at_return_without_another_receipt(learner):
    from training.scenarios import values
    from training.curriculum import BY_ID
    started=begin(learner,"cap-delivery-recovery","receiver")
    v=values(BY_ID["cap-delivery-recovery"],"guided")
    receive(learner,v)
    me=learner.get("/api/v1/training/me").json()
    assert me["attempt"]["id"]==started["attempt_id"]
    assert me["attempt"]["checkpoint"]==9
    return_one(learner,v)
    assert learner.post("/api/v1/training/check",json={"answer":"no"}).json()["passed"]


def test_monthly_capstone_refresh_is_real_evidence_after_submission(learner):
    from training.scenarios import values
    from training.curriculum import BY_ID
    begin(learner,"cap-monthly-count","counter")
    v=values(BY_ID["cap-monthly-count"],"guided")
    assert learner.get("/api/v1/counts/training-count/detail").status_code==200
    assert learner.put("/api/v1/counts/training-count/entries",json={"lines":[{"item_id":v["chicken"],"counted_quantity":v["quantity"]},{"item_id":v["amenities"],"counted_quantity":v["cap_kit_count"]}]}).status_code==200
    assert learner.post("/api/v1/counts/training-count/submit").status_code==200
    result=learner.post("/api/v1/training/check",json={"answer":"no"}).json()
    assert not result["passed"] and result["evidence"]["critical_pass"]
    assert learner.get("/api/v1/training/me").json()["attempt"]["checkpoint"]==5
    assert learner.get("/api/v1/counts/training-count/detail").json()["status"]=="posted"
    assert learner.post("/api/v1/training/check",json={"answer":"no"}).json()["passed"]


def test_wrong_later_return_fails_linked_integrity(learner):
    from training.scenarios import values
    from training.curriculum import BY_ID
    begin(learner,"cap-delivery-recovery","receiver")
    v=values(BY_ID["cap-delivery-recovery"],"guided")
    receive(learner,v)
    assert learner.post("/api/v1/receiving/purchase-orders/training-po/returns",json={"reason":"quality failure","lines":[{"purchase_order_line_id":v["po-line"],"quantity":2}]}).status_code==201
    result=learner.post("/api/v1/training/check",json={"answer":"no"}).json()
    assert not result["passed"] and not result["evidence"]["critical_pass"]


def perform_housekeeping(client,v):
    response=client.post('/api/v1/stock/issues',json={'item_id':v['amenities'],'location_id':v['store'],'lines':[{'item_id':v['amenities'],'quantity':v['quantity'],'reason':'Room preparation'}]})
    assert response.status_code==201,response.text
    for quantity,source,from_condition,destination,to_condition,reason,ref in [
        (4,v['store'],v['prop_clean'],v['kitchen'],v['prop_in_use'],v['prop_issue'],'TRAIN-ROOM-ISSUE'),
        (2,v['kitchen'],v['prop_in_use'],v['store'],v['prop_laundry'],v['prop_wash'],'TRAIN-LAUNDRY'),
        (1,v['store'],v['prop_laundry'],v['store'],v['prop_clean'],v['prop_wash'],'TRAIN-CLEAN')]:
        response=client.post('/api/v1/property/movements',json={'item_id':v['linen'],'quantity':quantity,'source_location_id':source,'source_condition_id':from_condition,'destination_location_id':destination,'destination_condition_id':to_condition,'movement_reason_id':reason,'reference':ref})
        assert response.status_code==201,response.text


def perform_owner(client,v):
    for decision,notes in [('accepted','verified need'),('completed','handover confirmed')]:
        response=client.post('/api/v1/integrations/operations/requests/training-connected-request/decision',json={'decision':decision,'notes':notes,'assigned_to_user_id':v['colleague']})
        assert response.status_code==200,response.text
        assert response.json()['workflow_status']==decision
        if decision=='accepted':
            me=client.get('/api/v1/training/me').json()
            assert me['attempt']['checkpoint']==4
    response=client.post('/api/v1/integrations/accounting/events/training-retry/requeue')
    assert response.status_code==200,response.text


@pytest.mark.parametrize('lesson,role,perform',[('cap-housekeeping','inventory_manager',perform_housekeeping),('cap-housekeeping','owner',perform_housekeeping),('cap-owner-review','owner',perform_owner)])
def test_cross_workspace_capstones_in_all_modes(learner,lesson,role,perform):
    from training.scenarios import values
    from training.curriculum import BY_ID
    for mode in ('guided','assisted','independent'):
        if mode=='guided':begin(learner,lesson,role)
        else:
            response=learner.post('/api/v1/training/start',json={'lesson_id':lesson,'mode':mode})
            assert response.status_code==200,response.text
            learner.headers['X-Training-Attempt']=response.json()['attempt_id']
        v=values(BY_ID[lesson],mode)
        assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']
        perform(learner,v)
        result=learner.post('/api/v1/training/check',json={'answer':'no'}).json()
        assert result['passed'],result
        assert result['evidence']['critical_pass']
        assert learner.get('/api/v1/training/me').json()['attempt']['checkpoint']==len(BY_ID[lesson].steps)


def perform_busy(client,v):
    response=client.post('/api/v1/quotations',json={'requisition_id':'training-requisition','supplier_id':v['supplier'],'delivery_days':1,'payment_terms_days':v['terms'],'notes':v['reference'],'lines':[{'item_id':v['chicken'],'quantity':v['quantity'],'unit_price':220}]})
    assert response.status_code==201,response.text
    response=client.post('/api/v1/requisitions/training-requisition/award-quotation',json={'quotation_id':response.json()['id'],'delivery_location_id':v['store']})
    assert response.status_code==201,response.text
    order=client.get(f"/api/v1/purchase-orders/{response.json()['purchase_order_id']}/detail")
    assert order.status_code==200,order.text
    assert order.json()['purchase_order']['status']=='partially_received'
    for _ in range(2):assert client.get('/api/v1/training/me').status_code==200


def perform_restaurant(client,v):
    response=client.post('/api/v1/production-batches/training-batch/start')
    assert response.status_code==200,response.text
    response=client.post('/api/v1/production-batches/training-batch/execute',json={'actual_output_quantity':v['quantity'],'output_waste_quantity':0,'materials':[{'item_id':v['chicken'],'actual_quantity':v['cap_material']}]})
    assert response.status_code==200,response.text
    for _ in range(2):assert client.get('/api/v1/training/me').status_code==200
    response=client.post('/api/v1/staff-meals',json={'meal_name':'Training staff lunch','servings':1,'location_id':v['store'],'lines':[{'item_id':v['alfredo'],'quantity':2}]})
    assert response.status_code==201,response.text
    assert client.post('/api/v1/integrations/pos/events',json={}).status_code==403


@pytest.mark.parametrize('lesson,role,perform',[('cap-busy-weekend','procurement_officer',perform_busy),('cap-busy-weekend','owner',perform_busy),('cap-restaurant-service','inventory_manager',perform_restaurant),('cap-restaurant-service','owner',perform_restaurant)])
def test_commercial_and_food_chains_all_modes(learner,lesson,role,perform):
    from training.scenarios import values
    from training.curriculum import BY_ID
    for mode in ('guided','assisted','independent'):
        if mode=='guided':begin(learner,lesson,role)
        else:
            response=learner.post('/api/v1/training/start',json={'lesson_id':lesson,'mode':mode})
            assert response.status_code==200,response.text
            learner.headers['X-Training-Attempt']=response.json()['attempt_id']
        v=values(BY_ID[lesson],mode)
        result=learner.post('/api/v1/training/check',json={'answer':'no'})
        assert result.status_code==200,result.text
        assert not result.json()['passed']
        perform(learner,v)
        result=learner.post('/api/v1/training/check',json={'answer':'no'}).json()
        assert result['passed'],result
        assert result['evidence']['critical_pass']
        assert result['evidence']['practical_score']==100
        assert learner.get('/api/v1/training/me').json()['attempt']['checkpoint']==len(BY_ID[lesson].steps)


def test_interrupted_colleague_review_recovers_without_duplicate_adjustment(learner,monkeypatch,app):
    from sqlalchemy.orm import Session
    from sqlalchemy import select,func
    from training.scenarios import engine_for
    from app.models.inventory import StockDocument
    from app.api.routes import guided_counts
    started=begin(learner,'cap-monthly-count','counter')
    assert learner.put('/api/v1/counts/training-count/entries',json={'lines':[{'item_id':'training-chicken','counted_quantity':21},{'item_id':'training-amenities','counted_quantity':12}]}).status_code==200
    original=guided_counts.approve_guided_count
    def outage(*args,**kwargs):raise RuntimeError('Synthetic interrupted colleague')
    monkeypatch.setattr(guided_counts,'approve_guided_count',outage)
    assert learner.post('/api/v1/counts/training-count/submit').status_code==200
    assert learner.get('/api/v1/training/me').status_code==503
    monkeypatch.setattr(guided_counts,'approve_guided_count',original)
    for _ in range(3):assert learner.get('/api/v1/training/me').json()['attempt']['checkpoint']==5
    assert learner.get('/api/v1/counts/training-count/detail').json()['status']=='posted'
    assert learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']
    engine=engine_for(app.state.training_store.root/f"attempt-{started['attempt_id']}.sqlite")
    with Session(engine) as db:assert db.scalar(select(func.count()).select_from(StockDocument).where(StockDocument.document_type=='count_adjustment'))==1
    engine.dispose()


@pytest.mark.parametrize('lesson,role,perform',[('cap-housekeeping','inventory_manager',perform_housekeeping),('cap-owner-review','owner',perform_owner),('cap-busy-weekend','procurement_officer',perform_busy),('cap-restaurant-service','inventory_manager',perform_restaurant)])
def test_capstone_reset_preserves_history_and_removes_previous_business_outcomes(learner,lesson,role,perform):
    from training.scenarios import values
    from training.curriculum import BY_ID
    old=begin(learner,lesson,role)
    perform(learner,values(BY_ID[lesson],'guided'))
    new=learner.post('/api/v1/training/start',json={'lesson_id':lesson}).json()
    assert old['attempt_id']!=new['attempt_id']
    assert learner.post('/api/v1/training/check',json={'answer':'no'}).status_code==409
    learner.headers['X-Training-Attempt']=new['attempt_id']
    result=learner.post('/api/v1/training/check',json={'answer':'no'}).json()
    assert not result['passed'] and not result['evidence']['critical_pass']
    assert any(row['id']==old['attempt_id'] and row['status']=='reset' for row in learner.get('/api/v1/training/me').json()['history'])
