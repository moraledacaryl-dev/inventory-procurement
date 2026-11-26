"""Fresh practical exams, critical thresholds, ownership and retained history."""
import json
import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from training.curriculum import BY_ID, VERSION
from training.paths import PATHS, BY_PATH, DutyPath
from training.exams import blueprint, public_blueprint, grade_knowledge, prerequisites, ASSESSMENT_VERSION


BLUEPRINTS=[(path.id,module) for path in PATHS for module in [None]+sorted({BY_ID[id].module for id in path.lessons})]


@pytest.mark.parametrize('path_id,module',BLUEPRINTS)
def test_every_duty_final_respects_permissions_and_explicit_scoring(path_id,module):
    row=blueprint(path_id,module);path=BY_PATH[path_id]
    assert set(row['practical_lessons'])<=set(row['lessons'])<=set(path.lessons)
    assert all(path.role in BY_ID[id].roles for id in row['lessons'])
    assert all('answer' not in question and 'correction' not in question for question in public_blueprint(row)['questions'])
    answers={question.id:question.answer for question in row['questions']}
    assert grade_knowledge(row,answers)['score']==100
    ordinary=next(question for question in row['questions'] if not question.critical)
    result=grade_knowledge(row,{**answers,ordinary.id:'incorrect'})
    assert result['score']>=85 and result['critical_pass']
    critical=next(question for question in row['questions'] if question.critical)
    result=grade_knowledge(row,{**answers,critical.id:'incorrect'})
    assert result['score']>=85 and not result['critical_pass']
    assert not prerequisites(row,[])['ready']
    if module is None:assert all(question.id.split('-')[1] in {BY_ID[id].module for id in path.lessons} for question in row['questions'] if question.id.startswith('final-'))


@pytest.fixture
def small_course(monkeypatch):
    path=DutyPath('test-stock-review','Test stock review','viewer','A bounded real read workflow.',('available-stock',),('available-stock',))
    monkeypatch.setitem(BY_PATH,path.id,path)
    return path


def enrol(client,path):
    response=client.post('/api/v1/training/enrol',json={'name':'Fictional final learner','role':path.role,'path_id':path.id})
    assert response.status_code==200,response.text
    return response.json()


def task(client,lesson_id,mode='guided',exam_id=None,perform=True):
    response=client.post('/api/v1/training/start',json={'lesson_id':lesson_id,'mode':mode,'exam_id':exam_id})
    assert response.status_code==200,response.text
    prepared=response.json();client.headers['X-Training-Attempt']=prepared['attempt_id']
    if perform:
        from training.scenarios import practical_question
        lesson=BY_ID[lesson_id]
        assert client.get(prepared['lesson']['inspection_api_path']).status_code==200
        _,answer,_=practical_question(lesson,mode)
        result=client.post('/api/v1/training/check',json={'answer':lesson.answer,'observation':answer})
        assert result.status_code==200,result.text
        assert result.json()['passed'],result.json()
    return prepared


def study(client,path,modes=('guided','assisted','independent')):
    for id in path.lessons:
        for mode in modes:task(client,id,mode)


def start_exam(client,module='A',restart=False):
    response=client.post('/api/v1/training/exams/start',json={'module':module,'restart':restart})
    assert response.status_code==200,response.text
    return response.json()


def answers(exam):
    return {question.id:question.answer for question in blueprint(exam['path_id'],exam['module'])['questions']}


def submit(client,exam,answer=None):
    response=client.post(f"/api/v1/training/exams/{exam['id']}/submit",json={'answers':answers(exam) if answer is None else answer})
    assert response.status_code==200,response.text
    return response.json()


def test_learning_prerequisites_and_historical_passes_cannot_replace_fresh_exam_work(learner,small_course):
    enrol(learner,small_course)
    assert learner.post('/api/v1/training/exams/start',json={'module':'A'}).status_code==409
    study(learner,small_course)
    exam=start_exam(learner)
    assert start_exam(learner)['id']==exam['id']
    # The previously passed independent task does not belong to this exam.
    result=submit(learner,exam)
    assert result['status']=='failed'
    assert result['result']['knowledge']['score']==100
    assert result['result']['practical_score']==0
    assert result['result']['critical_score']==0
    fresh=start_exam(learner)
    assert fresh['id']!=exam['id']
    practice=task(learner,'available-stock','independent',fresh['id'])
    assert practice['attempt_id'] not in [row.get('attempt_id') for row in result['result']['practical']]
    result=submit(learner,fresh)
    assert result['status']=='passed'
    assert not result['result']['certificate'] # module pass, not role certification
    assert len(learner.get('/api/v1/training/exams').json()['history'])==2


def test_one_noncritical_wrong_answer_meets_85_but_critical_error_never_passes(learner,small_course):
    enrol(learner,small_course);study(learner,small_course)
    exam=start_exam(learner);task(learner,'available-stock','independent',exam['id'])
    result=submit(learner,exam,{**answers(exam),'unit':'250'})
    assert result['result']['knowledge']['score']==85.71
    assert result['result']['practical_score']==100
    assert result['status']=='failed' and result['result']['critical_score']==0
    assert any(question['id']=='unit' and not question['passed'] for question in result['result']['knowledge']['questions'])
    fresh=start_exam(learner);task(learner,'available-stock','independent',fresh['id'])
    result=submit(learner,fresh,{**answers(fresh),'value':'400'})
    assert result['status']=='passed' and result['result']['knowledge']['score']==85.71
    assert result['result']['critical_score']==100


def test_hint_requires_a_fresh_independent_task_inside_the_same_exam(learner,small_course):
    enrol(learner,small_course);study(learner,small_course)
    exam=start_exam(learner)
    task(learner,'available-stock','independent',exam['id'],perform=False)
    assert learner.post('/api/v1/training/hint').status_code==200
    result=submit(learner,exam)
    assert result['status']=='failed'
    assert result['result']['practical_score']==0
    assert 'hint' in result['result']['practical'][0]['correction']


def test_module_and_role_finals_retain_frozen_results_and_real_fresh_evidence(learner,small_course):
    enrol(learner,small_course);study(learner,small_course)
    assert learner.post('/api/v1/training/exams/start',json={}).status_code==409
    module=start_exam(learner);task(learner,'available-stock','independent',module['id']);assert submit(learner,module)['status']=='passed'
    exam=start_exam(learner,None);fresh=task(learner,'available-stock','independent',exam['id'])
    result=submit(learner,exam)
    assert result['status']=='passed' and result['result']['certificate']==f"TRAINING-{exam['id']}"
    assert result['result']['practical'][0]['attempt_id']==fresh['attempt_id']
    assert result['result']['meaning'].startswith('This certifies local training performance only')
    assert submit(learner,exam,{} )==result
    assert learner.post(f"/api/v1/training/exams/{exam['id']}/draft",json={'answers':{}}).status_code==409
    assert learner.post('/api/v1/training/start',json={'lesson_id':'available-stock','mode':'independent','exam_id':exam['id']}).status_code==409


def test_exam_ownership_attempt_scope_and_answer_draft_recovery(learner,app,small_course):
    enrol(learner,small_course);study(learner,small_course)
    exam=start_exam(learner)
    saved={'available':'20','unit':'0.25'}
    assert learner.post(f"/api/v1/training/exams/{exam['id']}/draft",json={'answers':saved}).status_code==200
    assert learner.get(f"/api/v1/training/exams/{exam['id']}").json()['answers_draft']==saved
    assert learner.post(f"/api/v1/training/exams/{exam['id']}/draft",json={'answers':{'unrelated-secret':'x'}}).status_code==422
    other=TestClient(app);other.headers['X-Requested-With']='HiddenOasisInventory';enrol(other,small_course)
    assert other.get(f"/api/v1/training/exams/{exam['id']}").status_code==404
    assert other.post(f"/api/v1/training/exams/{exam['id']}/submit",json={'answers':{}}).status_code==404
    assert learner.post('/api/v1/training/start',json={'lesson_id':'available-stock','mode':'guided','exam_id':exam['id']}).status_code==403
    assert learner.post('/api/v1/training/exams/start',json={'module':'V'}).status_code==403


def test_duty_courses_preserve_multiple_assignments_and_real_role_boundaries(learner,app):
    first=enrol(learner,BY_PATH['housekeeping'])
    assert learner.post('/api/v1/training/start',json={'lesson_id':'create-maintenance-plan'}).status_code==403
    enrol(learner,BY_PATH['kitchen'])
    me=learner.get('/api/v1/training/me').json()
    assert me['learner']['id']==first['id']
    assert {row['path_id'] for row in me['assignments']}=={'housekeeping','kitchen'}
    assert learner.post('/api/v1/training/enrol',json={'name':'Mismatch','role':'viewer','path_id':'housekeeping'}).status_code==422
    assert learner.post('/api/v1/training/assign',json={'learner_id':first['id'],'path_id':'maintenance'}).status_code==403
    key=(app.state.training_store.root/'manager-key').read_text()
    assert learner.post('/api/v1/training/assign',headers={'X-Training-Manager-Key':key},json={'learner_id':first['id'],'path_id':'maintenance'}).status_code==200
    me=learner.get('/api/v1/training/me').json()
    assert me['learner']['path_id']=='maintenance' and len(me['assignments'])==3
    catalogue=learner.get('/api/v1/training/catalogue').json()
    assert all(path['role'] in catalogue['roles'] for path in catalogue['paths'])


def test_schema_two_migration_retains_attempts_and_adds_the_existing_role_course(tmp_path):
    from training.store import Store
    root=tmp_path/'inventory-training';root.mkdir()
    db=sqlite3.connect(root/'progress.sqlite')
    db.executescript("""
      CREATE TABLE schema_version(version INTEGER PRIMARY KEY);INSERT INTO schema_version VALUES(2);
      CREATE TABLE learners(id TEXT PRIMARY KEY,name TEXT NOT NULL,role TEXT NOT NULL,current_attempt TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
      CREATE TABLE attempts(id TEXT PRIMARY KEY,learner_id TEXT,lesson_id TEXT,mode TEXT,role TEXT,status TEXT DEFAULT 'active',hints INTEGER DEFAULT 0,mistakes INTEGER DEFAULT 0,checkpoint INTEGER DEFAULT 0,started_at TEXT DEFAULT CURRENT_TIMESTAMP,completed_at TEXT,evidence TEXT DEFAULT '{}',curriculum_version TEXT);
      INSERT INTO learners(id,name,role,current_attempt) VALUES('old-person','Fictional previous participant','counter','old-attempt');
      INSERT INTO attempts(id,learner_id,lesson_id,mode,role,status,curriculum_version) VALUES('old-attempt','old-person','blind-count','independent','counter','passed','previous-course');
    """);db.commit();db.close()
    store=Store(root)
    assert store.learner('old-person')['path_id']=='role-counter'
    assert store.history('old-person')[0]['status']=='passed'
    assert store.history('old-person')[0]['curriculum_version']=='previous-course'
    assert store.assignments('old-person')[0]['path_id']=='role-counter'
    assert Store(root).history('old-person')[0]['exam_id'] is None
    with store.connect() as db:assert db.execute('SELECT version FROM schema_version').fetchone()[0]==4


def test_final_rechecks_live_business_integrity_after_a_practice_pass(learner,monkeypatch):
    path=DutyPath('test-owner-inspection','Test owner inspection','owner','Actual source-authorized inspection.',('available-stock',),('available-stock',))
    monkeypatch.setitem(BY_PATH,path.id,path)
    enrol(learner,path);study(learner,path)
    exam=start_exam(learner);task(learner,'available-stock','independent',exam['id'])
    assert learner.get(f"/api/v1/training/exams/{exam['id']}").json()['practical'][0]['score']==100
    # A saved Passed flag cannot hide an actual later mutation in that sandbox.
    changed=learner.post('/api/v1/stock/receipts',json={'location_id':'training-store','lines':[{'item_id':'training-chicken','quantity':1,'unit_cost':200}]})
    assert changed.status_code==201,changed.text
    result=submit(learner,exam)
    assert result['status']=='failed' and result['result']['critical_score']==0
    assert not result['result']['practical'][0]['evidence']['record_unchanged']


def test_old_exam_version_and_cross_duty_attempts_cannot_satisfy_a_current_final(learner,app,small_course):
    enrol(learner,small_course);study(learner,small_course)
    exam=start_exam(learner)
    with app.state.training_store.connect() as db:db.execute("UPDATE exams SET assessment_version='retired-final' WHERE id=?",(exam['id'],))
    assert learner.get(f"/api/v1/training/exams/{exam['id']}").json()['historical']
    assert learner.post('/api/v1/training/start',json={'lesson_id':'available-stock','mode':'independent','exam_id':exam['id']}).status_code==409
    enrol(learner,BY_PATH['accounting-review'])
    assert learner.get(f"/api/v1/training/exams/{exam['id']}").json()['historical']


def test_stale_answer_draft_cannot_overwrite_a_newer_tab(learner,small_course):
    enrol(learner,small_course);study(learner,small_course)
    exam=start_exam(learner)
    response=learner.post(f"/api/v1/training/exams/{exam['id']}/draft",json={'answers':{'available':'20'},'revision':0})
    assert response.json()['revision']==1
    assert learner.post(f"/api/v1/training/exams/{exam['id']}/draft",json={'answers':{'available':'999'},'revision':0}).status_code==409
    saved=learner.get(f"/api/v1/training/exams/{exam['id']}").json()
    assert saved['answers_draft']=={'available':'20'} and saved['draft_revision']==1
    assert learner.post(f"/api/v1/training/exams/{exam['id']}/draft",json={'answers':{'available':'20','unit':'0.25'},'revision':1}).status_code==200


def test_a_completed_result_remains_readable_after_its_business_file_is_unavailable(learner,app,small_course):
    enrol(learner,small_course);study(learner,small_course)
    exam=start_exam(learner);practice=task(learner,'available-stock','independent',exam['id'])
    passed=submit(learner,exam)
    (app.state.training_store.root/f"attempt-{practice['attempt_id']}.sqlite").unlink()
    assert learner.get(f"/api/v1/training/exams/{exam['id']}").json()['result']==passed['result']
    assert learner.post('/api/v1/training/enrol',json={'name':'Renamed fictional participant','role':small_course.role,'path_id':small_course.id}).status_code==200
    frozen=learner.get(f"/api/v1/training/exams/{exam['id']}").json()['result']
    assert frozen==passed['result'] and frozen['learner_name']=='Fictional final learner'


@pytest.mark.parametrize('score,critical,passed',[(90,True,True),(89.99,True,False),(100,False,False)])
def test_practical_threshold_cannot_round_away_a_critical_failure(score,critical,passed):
    from training.exams import grade_practical
    result=grade_practical([{'score':score,'critical_pass':critical}])
    assert result['passed']==passed
    assert result['score']==score


def test_an_inspection_lesson_cannot_pass_after_changing_its_business_record(learner,monkeypatch):
    path=DutyPath('test-inspection-only','Test unchanged inspection','owner','Actual stock inspection.',('available-stock',),('available-stock',))
    monkeypatch.setitem(BY_PATH,path.id,path)
    enrol(learner,path)
    prepared=task(learner,'available-stock',perform=False)
    assert learner.get(prepared['lesson']['inspection_api_path']).status_code==200
    assert learner.post('/api/v1/stock/receipts',json={'location_id':'training-store','lines':[{'item_id':'training-chicken','quantity':1,'unit_cost':200}]}).status_code==201
    result=learner.post('/api/v1/training/check',json={'answer':'available','observation':'20'}).json()
    assert not result['passed'] and not result['evidence']['record_unchanged']
    assert 'inspection task' in result['message']
