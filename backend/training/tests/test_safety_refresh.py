"""The refreshed lessons require real source refusals and replacement evidence."""
import pytest
from conftest import begin
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import IntegrationEvent,StockBalance,StockReservation,PurchaseOrder,PosSaleEvent,StockDocument
from training.curriculum import BY_ID
from training.safety_lessons import LESSONS
from training.scenarios import values,engine_for,practical_question


def perform(client,lesson,v):
    if lesson.id=='staff-meal-reserved-stock':
        body={'meal_name':'Training reserved-stock check','location_id':v['store'],'servings':4,
              'lines':[{'item_id':v['chicken'],'quantity':v['meal_reserved_need']}]}
        assert client.post('/api/v1/staff-meals/preview',json=body).status_code==409
        return client.post('/api/v1/staff-meals',json=body)
    path='/api/v1/integrations/accounting/events/training-safety-event/requeue' if lesson.id.endswith('dedicated') else '/api/v1/integration-events/training-safety-event/retry'
    return client.post(path)


@pytest.mark.parametrize('lesson',LESSONS,ids=lambda lesson:lesson.id)
def test_safety_lesson_requires_observed_real_outcome_all_modes(learner,lesson):
    for mode in ('guided','assisted','independent'):
        if mode=='guided':begin(learner,lesson.id,lesson.roles[0])
        else:
            started=learner.post('/api/v1/training/start',json={'lesson_id':lesson.id,'mode':mode})
            assert started.status_code==200,started.text
            learner.headers['X-Training-Attempt']=started.json()['attempt_id']
        assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']
        result=perform(learner,lesson,values(lesson,mode))
        assert result.status_code==(200 if lesson.id=='retry-reviewed-outbound-event' else 409),result.text
        checked=learner.post('/api/v1/training/check',json={'answer':'no'}).json()
        assert checked['passed'],checked
        assert checked['evidence']['stock_integrity']


def test_replacement_receipt_preserves_original_rejection_and_requires_new_delivery(learner):
    prepared=begin(learner,'replacement-delivery','receiver')
    lesson=prepared['lesson'];profile=learner.get('/api/v1/receiving/workspace').json()
    po=next(row for row in profile['purchase_orders'] if row['id']=='training-po')
    assert po['replacement_required'] and float(po['outstanding_quantity'])==2
    assert po['status']=='partially_received'
    body={'delivery_reference':lesson['reference'],'idempotency_key':'replacement-original','lines':[{
        'purchase_order_line_id':'training-po-line','received_quantity':2,'accepted_quantity':2,'rejected_quantity':0}]}
    posted=learner.post('/api/v1/receiving/purchase-orders/training-po',json=body)
    assert posted.status_code==201,posted.text
    assert learner.post('/api/v1/receiving/purchase-orders/training-po',json=body).json()['id']==posted.json()['id']
    checked=learner.post('/api/v1/training/check',json={'answer':'no'}).json()
    assert checked['passed'],checked
    po=learner.get('/api/v1/purchase-orders/training-po/detail').json()
    assert float(po['lines'][0]['received_quantity'])==12
    assert float(po['lines'][0]['accepted_quantity'])==10
    assert float(po['lines'][0]['rejected_quantity'])==2
    assert float(po['lines'][0]['outstanding_quantity'])==0
    history=learner.get('/api/v1/receiving/workspace').json()['receipts']
    assert len(history)==2 and sum(float(row['rejected_value']) for row in history)==400


@pytest.mark.parametrize('id',['inspect-unused-sale-void','inspect-cooked-sale-return'])
def test_financial_training_keeps_original_cost_without_any_reversal(learner,id):
    begin(learner,id,'viewer')
    profile=learner.get('/api/v1/training/me').json()
    path=learner.app.state.training_store.root/f"attempt-{learner.headers['X-Training-Attempt']}.sqlite"
    engine=engine_for(path)
    try:
        with Session(engine) as db:
            assert db.scalar(select(StockDocument.id).where(StockDocument.document_type=='pos_sale_reversal')) is None
            follows=list(db.scalars(select(PosSaleEvent).where(PosSaleEvent.event_type!='sale_completed')))
            assert follows and all(row.stock_document_id is None for row in follows)
        response=learner.get(profile['lesson']['inspection_api_path'])
        assert response.status_code==200
        _,answer,_=practical_question(BY_ID[id],'guided')
        checked=learner.post('/api/v1/training/check',json={'answer':'no','observation':answer})
        assert checked.json()['passed'],checked.text
    finally:engine.dispose()


def test_new_local_refusal_does_not_enable_external_delivery_or_other_intake(learner):
    begin(learner,'refuse-accepted-accounting-dedicated','owner')
    for path in ['/api/v1/integration-events/process','/api/v1/integrations/accounting/receipts','/api/v1/integrations/pos/events','/api/v1/integrations/accounting/events/another-event/requeue']:
        assert learner.post(path,json={}).status_code==403,path
    response=learner.post('/api/v1/integrations/accounting/events/training-safety-event/requeue')
    assert response.status_code==409


def test_unrelated_physical_shortage_cannot_pass_reserved_stock_exercise(learner):
    begin(learner,'staff-meal-reserved-stock','inventory_manager')
    proposal={'meal_name':'Training reserved-stock check','location_id':'training-store','servings':4,
              'lines':[{'item_id':'training-chicken','quantity':25}]}
    for path in ['/api/v1/staff-meals/preview','/api/v1/staff-meals']:
        assert learner.post(path,json=proposal).status_code==409
    assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']
    assert perform(learner,BY_ID['staff-meal-reserved-stock'],values(BY_ID['staff-meal-reserved-stock'],'guided')).status_code==409
    assert learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']
