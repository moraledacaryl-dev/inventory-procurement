"""Saved selling configuration, accountable cancellation and base-unit outcomes."""
import pytest
from conftest import begin
from training.extensions_lessons import LESSONS
from training.extensions_scenarios import group


def perform(client,lesson,v):
    id=lesson.id
    if id=="counter-foundations":return client.get("/api/v1/counts/training-count/detail")
    if id in {"create-conditional-price-rule","deactivate-conditional-price-rule"}:
        create=id.startswith("create")
        return client.request("POST" if create else "PUT","/api/v1/fnb/pos-rules/pricing"+("" if create else "/training-rule"),json={"name":"Training drink and pastry" if create else "Training weekend promotion","qualifier_tag":"train-drink","target_tag":"train-pastry","priority":100,"is_active":create})
    if id in {"create-reusable-add-ons","correct-reusable-add-on-price"}:
        create=id.startswith("create")
        return client.request("POST" if create else "PUT","/api/v1/fnb/pos-rules/modifiers"+("" if create else "/training-modifier"),json={"name":"Training pizza extras","group":group(30 if create else 35),"is_active":True})
    if id in {"cancel-unstarted-production","cancel-started-production"}:
        return client.post("/api/v1/production-batches/training-batch/cancel",json={"reason":"Service plan changed","material_disposition":"No materials issued; ingredients remain in storage" if id=="cancel-started-production" else None})
    return client.post("/api/v1/stock/issues",json={"location_id":v['store'],"reason":"Service replenishment","lines":[{"item_id":v['service_item'],"quantity":v['quantity'],"reason":"Service replenishment"}]})


@pytest.mark.parametrize("lesson",LESSONS,ids=lambda lesson:lesson.id)
def test_extensions_real_outcomes_all_modes(learner,lesson):
    from training.scenarios import values
    for mode in ("guided","assisted","independent"):
        if mode=="guided":begin(learner,lesson.id,lesson.roles[0])
        else:
            response=learner.post("/api/v1/training/start",json={"lesson_id":lesson.id,"mode":mode})
            assert response.status_code==200,response.text
            learner.headers['X-Training-Attempt']=response.json()['attempt_id']
        check={"answer":lesson.answer,"observation":"kg"}
        assert not learner.post("/api/v1/training/check",json=check).json()['passed']
        response=perform(learner,lesson,values(lesson,mode))
        assert response.status_code in {200,201},response.text
        result=learner.post("/api/v1/training/check",json=check).json()
        assert result['passed'],result
        assert learner.get('/api/v1/training/me').json()['attempt']['checkpoint']==len(lesson.steps)


def test_started_cancellation_requires_material_disposition(learner):
    begin(learner,'cancel-started-production','inventory_manager')
    rejected=learner.post('/api/v1/production-batches/training-batch/cancel',json={'reason':'Service plan changed'})
    assert rejected.status_code==422,rejected.text
    assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']


@pytest.mark.parametrize('id,wrong',[('issue-cafe-case',1),('issue-bar-volume',750)])
def test_packaging_quantity_cannot_replace_actual_base_unit_handover(learner,id,wrong):
    begin(learner,id,'inventory_manager')
    posted=learner.post('/api/v1/stock/issues',json={'location_id':'training-store','reason':'Service replenishment','lines':[{'item_id':'training-service-item','quantity':wrong,'reason':'Service replenishment'}]})
    assert posted.status_code==201,posted.text
    assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']


def test_changed_unrelated_stock_cannot_certify_a_selling_configuration(learner):
    from training.curriculum import BY_ID
    from training.scenarios import values
    lesson=BY_ID['create-conditional-price-rule'];begin(learner,lesson.id,'inventory_manager')
    assert perform(learner,lesson,values(lesson,'guided')).status_code==201
    assert learner.post('/api/v1/stock/issues',json={'location_id':'training-store','lines':[{'item_id':'training-amenities','quantity':1}]}).status_code==201
    assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']
