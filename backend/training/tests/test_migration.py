"""Real multipart CSV upload, guarded apply and owned practice input."""
import pytest
from fastapi.testclient import TestClient
from conftest import begin
from training.csv_lessons import LESSONS


def upload(client,lesson,filename=None,content=None):
    fixture=client.get('/api/v1/training/practice-file')
    assert fixture.status_code==200,fixture.text
    data=fixture.json()
    from training.csv_fixtures import CSV_FILES
    return client.post('/api/v1/migration/imports/'+CSV_FILES[lesson.id][1]+'/validate',files={'file':(filename or data['filename'],data['content'] if content is None else content,'text/csv')})


@pytest.mark.parametrize('lesson',LESSONS,ids=lambda lesson:lesson.id)
def test_migration_real_outcomes_all_modes(learner,lesson):
    for mode in ('guided','assisted','independent'):
        if mode=='guided':begin(learner,lesson.id,'owner')
        else:
            response=learner.post('/api/v1/training/start',json={'lesson_id':lesson.id,'mode':mode})
            assert response.status_code==200,response.text
            learner.headers['X-Training-Attempt']=response.json()['attempt_id']
        assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']
        response=upload(learner,lesson)
        assert response.status_code==201,response.text
        data=response.json()
        if lesson.id=='reject-invalid-csv':
            assert data['status']=='invalid' and data['errors'][0]['line']==3
            assert learner.post('/api/v1/migration/imports/'+data['job_id']+'/apply').status_code==409
        else:
            assert data['status']=='validated'
            before=learner.get('/api/v1/training/me').json()['attempt']['mistakes']
            applied=learner.post('/api/v1/migration/imports/'+data['job_id']+'/apply')
            expected=409 if lesson.id=='refuse-duplicate-opening-import' else 200
            assert applied.status_code==expected,applied.text
            if expected==409:assert learner.get('/api/v1/training/me').json()['attempt']['mistakes']==before
        checked=learner.post('/api/v1/training/check',json={'answer':'no'}).json()
        assert checked['passed'],checked
        assert learner.get('/api/v1/training/me').json()['attempt']['checkpoint']==len(lesson.steps)


def test_practice_files_are_fixed_owned_and_bound_to_the_current_tab(learner,app):
    from training.curriculum import BY_ID
    begun=begin(learner,'import-item-catalogue','owner')
    data=learner.get('/api/v1/training/practice-file').json()
    assert set(data)=={'filename','content'}
    assert data['filename']=='training-items.csv' and 'TRAIN-MILK' in data['content']
    other=TestClient(app)
    assert other.get('/api/v1/training/practice-file').status_code==401
    next=learner.post('/api/v1/training/start',json={'lesson_id':'import-supplier-catalogue'}).json()
    assert learner.get('/api/v1/training/practice-file').status_code==409
    learner.headers['X-Training-Attempt']=next['attempt_id']
    assert learner.get('/api/v1/training/practice-file').json()['filename']=='training-suppliers.csv'
    begin(learner,'available-stock','owner')
    assert learner.get('/api/v1/training/practice-file').status_code==404


def test_opening_apply_cannot_be_repeated(learner):
    from training.curriculum import BY_ID
    begin(learner,'import-initial-balances','owner')
    assert learner.get('/api/v1/stock/movements').json()==[]
    job=upload(learner,BY_ID['import-initial-balances']).json()
    path='/api/v1/migration/imports/'+job['job_id']+'/apply'
    assert learner.post(path).status_code==200
    assert learner.post(path).status_code==409
    movements=learner.get('/api/v1/stock/movements').json()
    assert len(movements)==1 and movements[0]['quantity']=='5.0000'


def test_wrong_imported_cost_does_not_pass(learner):
    from training.curriculum import BY_ID
    lesson=BY_ID['import-item-catalogue'];begin(learner,lesson.id,'owner')
    data=learner.get('/api/v1/training/practice-file').json()
    job=upload(learner,lesson,content=data['content'].replace(',12,75',',12,750')).json()
    assert learner.post('/api/v1/migration/imports/'+job['job_id']+'/apply').status_code==200
    assert not learner.post('/api/v1/training/check',json={'answer':'no'}).json()['passed']


def test_validated_source_job_resumes_without_another_upload(learner):
    from training.curriculum import BY_ID
    begin(learner,'import-item-catalogue','owner')
    job=upload(learner,BY_ID['import-item-catalogue']).json()
    profile=learner.get('/api/v1/training/me').json()
    assert profile['attempt']['checkpoint']==3
    assert learner.post('/api/v1/migration/imports/'+job['job_id']+'/apply').status_code==200
    assert learner.get('/api/v1/training/me').json()['attempt']['checkpoint']==4
    assert len(learner.get('/api/v1/migration/imports').json())==1
