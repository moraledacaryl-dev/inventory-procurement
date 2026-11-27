"""Real source maintenance operations and task-scoped analysis evidence."""
import pytest
from conftest import begin
from training.steward_lessons import LESSONS


def perform(client,lesson,v):
    id=lesson.id
    if id=='unlink-obsolete-supplier-item':
        row=client.get('/api/v1/items/training-chicken/configuration').json()['supplier_items'][0]
        return client.delete('/api/v1/supplier-items/'+row['id'])
    if id=='create-authorized-storage-location':return client.post('/api/v1/locations',json={'code':'TRAIN-CAFE-STORE','name':'Training café supplies','location_type':'storeroom','parent_id':v['store']})
    if id=='correct-storage-location-label':return client.patch('/api/v1/locations/training-kitchen',json={'name':'Training kitchen dry store'})
    if id=='stock-screen-signed-correction':return client.post('/api/v1/stock/adjustments',json={'location_id':v['store'],'reference':v['reference'],'lines':[{'item_id':v['chicken'],'quantity_delta':-v['quantity'],'unit_cost':200,'reason':'Verified opening correction'}]})
    if id=='assign-menu-selling-controls':
        row=next(row for row in client.get('/api/v1/fnb/menu').json() if row['id']=='training-review-menu')
        row['pricing_tags']=['train-main'];row['modifier_template_ids']=['training-menu-extras'];row['variants'][0]['conditional_prices']=[{'rule_id':'training-menu-rule','price':220}]
        return client.put('/api/v1/fnb/menu/training-review-menu',json=row)
    if id=='retry-eligible-inbound-event':return client.post('/api/v1/integration-events/training-pos-retry/retry')
    if id=='activate-verified-pos-mapping':return client.post('/api/v1/pos-mappings/training-pos-map/activate')
    return client.post('/api/v1/recipes/training-recipe/margin-scenario',json={'location_id':v['store'],'selling_price':v['margin_price']})


@pytest.mark.parametrize('lesson',LESSONS,ids=lambda lesson:lesson.id)
def test_steward_outcomes_all_modes(learner,lesson):
    from training.scenarios import values
    for mode in ('guided','assisted','independent'):
        if mode=='guided':begin(learner,lesson.id,lesson.roles[0])
        else:
            response=learner.post('/api/v1/training/start',json={'lesson_id':lesson.id,'mode':mode})
            assert response.status_code==200,response.text
            learner.headers['X-Training-Attempt']=response.json()['attempt_id']
        assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']
        response=perform(learner,lesson,values(lesson,mode))
        assert response.status_code in ({409} if lesson.id=='retry-eligible-inbound-event' else {200,201,204}),response.text
        checked=learner.post('/api/v1/training/check',json={'answer':'no'}).json()
        assert checked['passed'],checked
        assert checked['evidence']['stock_integrity']
        assert learner.get('/api/v1/training/me').json()['attempt']['checkpoint']==len(lesson.steps)


def test_margin_requires_the_latest_actual_calculation_with_correct_scope(learner,app):
    begin(learner,'calculate-food-margin','inventory_manager')
    url='/api/v1/recipes/training-recipe/margin-scenario'
    assert learner.get('/api/v1/recipes/training-recipe/costing-detail?location_id=training-store').status_code==200
    assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']
    calculated=learner.post(url,json={'location_id':'training-store','selling_price':250})
    assert calculated.status_code==200 and calculated.json()['gross_margin_percent']=='80.00'
    assert learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']
    # A later wrong analysis invalidates the live outcome of an exam too.
    assert learner.post(url,json={'location_id':'training-kitchen','selling_price':350}).status_code==200
    from sqlalchemy.orm import Session
    from training.scenarios import engine_for,verify
    from training.curriculum import BY_ID
    store=app.state.training_store
    with store.connect() as registry:attempt=dict(registry.execute('SELECT * FROM attempts ORDER BY rowid DESC LIMIT 1').fetchone())
    engine=engine_for(store.root/f"attempt-{attempt['id']}.sqlite")
    try:
        with Session(engine) as db:assert not verify(db,BY_ID['calculate-food-margin'],'guided',store.business_actions(attempt['id']))[0]
    finally:engine.dispose()


def test_calculation_capture_omits_unrelated_request_fields(learner,app):
    begin(learner,'calculate-food-margin','inventory_manager')
    assert learner.post('/api/v1/recipes/training-recipe/margin-scenario',json={'location_id':'training-store','selling_price':250,'unrelated_note':'DO-NOT-CAPTURE'}).status_code==200
    store=app.state.training_store
    with store.connect() as registry:rows=[row['detail'] for row in registry.execute("SELECT detail FROM events WHERE kind='business_action'")]
    assert any('calculation' in row for row in rows)
    assert not any('DO-NOT-CAPTURE' in row or 'unrelated_note' in row for row in rows)


def test_mapping_cannot_pass_after_its_recipe_is_retired(learner):
    begin(learner,'activate-verified-pos-mapping','owner')
    assert learner.post('/api/v1/pos-mappings/training-pos-map/activate').status_code==200
    assert learner.post('/api/v1/recipes/training-recipe/retire').status_code==200
    assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']
