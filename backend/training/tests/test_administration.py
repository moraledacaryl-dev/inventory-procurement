"""Actual restricted controls and unchanged stock; no fabricated release pass."""
import pytest
from conftest import begin
from training.admin_lessons import LESSONS


def perform(client,id,v):
    requests={
      'assign-location-approval-scope':('POST','/access-scopes',{'user_id':v['purchaser'],'location_id':v['store'],'approval_limit':v['scope_limit']}),
      'create-operating-department':('POST','/classification/dimensions',{'dimension_type':'department','code':'train-cafe','name':'Training café outlet','workspace_id':v['fnb']}),
      'retire-unused-classification':('PATCH','/classification/dimensions/training-old-department',{'is_active':False}),
      'classify-legacy-ingredient':('PATCH','/classification/items/training-chicken',{'primary_workspace_id':v['fnb'],'item_type_id':v['ingredient']}),
      'create-accounting-mapping':('POST','/accounting-mappings',{'event_key':'inventory.stock_document.posted','debit_account':'TRAIN-INVENTORY','credit_account':'TRAIN-CLEARING','description':'Training reviewer-approved mapping'}),
      'save-report-scope':('POST','/saved-views',{'module_key':'operating-summary','name':'Training F&B review','filters':{'workspace_id':v['fnb']},'columns':['stock_value','reusable_units','net_fixed_assets','overdue_maintenance'],'is_default':False}),
      'acknowledge-operational-alert':('POST','/notifications/training-review-alert/read',None),
      'submit-workflow-feedback':('POST','/feedback',{'category':'usability','severity':'normal','page':'/counts','message':'Training: count field difficult to read on phone'}),
      'resolve-verified-feedback':('PATCH','/feedback/training-feedback',{'status':'resolved'}),
      'resolve-verified-incident':('PATCH','/incidents/training-incident',{'status':'resolved'}),
      'record-assurance-review':('POST','/reports/final-assurance/record',None),
      'run-isolated-acceptance':('POST','/acceptance-runs',{'environment':'production-candidate','notes':'Practice only; no release authorization'}),
      'check-isolated-rollout':('POST','/rollout/smoke-test',None),
    }
    method,path,body=requests[id]
    return client.request(method,'/api/v1'+path,**({'json':body} if body is not None else {}))


@pytest.mark.parametrize('lesson',LESSONS,ids=lambda lesson:lesson.id)
def test_administrative_outcomes_all_modes(learner,lesson):
    from training.scenarios import values
    for mode in ('guided','assisted','independent'):
        if mode=='guided':begin(learner,lesson.id,lesson.roles[0])
        else:
            started=learner.post('/api/v1/training/start',json={'lesson_id':lesson.id,'mode':mode})
            assert started.status_code==200,started.text
            learner.headers['X-Training-Attempt']=started.json()['attempt_id']
        assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']
        response=perform(learner,lesson.id,values(lesson,mode))
        assert response.status_code in {200,201},response.text
        if lesson.id=='run-isolated-acceptance':assert response.json()['status']=='failed'
        if lesson.id=='check-isolated-rollout':assert response.json()['checks']['backup_present'] is False
        checked=learner.post('/api/v1/training/check',json={'answer':'no'}).json()
        assert checked['passed'],checked
        assert checked['evidence']['stock_integrity']
        assert learner.get('/api/v1/training/me').json()['attempt']['checkpoint']==len(lesson.steps)


def test_wrong_or_broader_scope_cannot_pass(learner):
    begin(learner,'assign-location-approval-scope','owner')
    response=learner.post('/api/v1/access-scopes',json={'user_id':'training-purchaser','approval_limit':1000})
    assert response.status_code==201,response.text
    assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']


def test_reading_an_alert_does_not_complete_its_underlying_stock_work(learner):
    begin(learner,'acknowledge-operational-alert','inventory_manager')
    assert learner.get('/api/v1/notifications').status_code==200
    assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']
    response=learner.post('/api/v1/notifications/training-review-alert/read')
    assert response.status_code==200 and response.json()['is_read']
    assert learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']


def test_a_reconciled_ledger_does_not_hide_the_missing_backup(learner):
    begin(learner,'record-assurance-review','owner')
    response=learner.post('/api/v1/reports/final-assurance/record')
    assert response.status_code==200,response.text
    data=response.json()
    assert data['summary']['stock_mismatches']==0
    assert data['overall_status']=='critical'
    assert next(check for check in data['checks'] if check['key']=='backup')['status']=='failed'
