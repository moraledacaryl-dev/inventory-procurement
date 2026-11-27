"""Participant-owned final exams with fresh, source-verified practical records."""
import json
import uuid
from pathlib import Path
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from training.curriculum import BY_ID, VERSION
from training.paths import BY_PATH
from training.employee_copy import employee_feedback
from training.exams import ASSESSMENT_VERSION, blueprint, public_blueprint, prerequisites, grade_knowledge, grade_practical, normalize


def public_exam(row):
    result={key:value for key,value in row.items() if key!="learner_id"}
    for key in ("blueprint","answers_draft","result"):
        result[key]=json.loads(result[key])
    return result


def owned_current_exam(store,learner,exam_id):
    row=store.exam(learner["id"],exam_id)
    if not row:raise HTTPException(404,"This final check was not found in your training history.")
    if row["path_id"]!=learner["path_id"] or row["role"]!=learner["role"]:raise HTTPException(409,"Return to this final check's duty course before continuing it.")
    if row["curriculum_version"]!=VERSION or row["assessment_version"]!=ASSESSMENT_VERSION:raise HTTPException(409,"This final check has been updated. Keep its history and start the current version.")
    return row


def validate_exam_attempt(store,learner,exam_id,lesson_id,mode):
    row=owned_current_exam(store,learner,exam_id)
    if row["status"]!="active":raise HTTPException(409,"This final check is already graded. Start a fresh retake for another result.")
    if mode!="independent" or lesson_id not in blueprint(row["path_id"],row["module"])["practical_lessons"]:raise HTTPException(403,"Use the independent tasks assigned to this final check.")
    return row


def practical_results(store,root,learner,row):
    from training.scenarios import engine_for, values, verify, practical_question, inspection_endpoint, read_only_unchanged
    results=[]
    for lesson_id in blueprint(row["path_id"],row["module"])["practical_lessons"]:
        lesson=BY_ID[lesson_id]
        with store.connect() as registry:
            saved=registry.execute("SELECT * FROM attempts WHERE exam_id=? AND learner_id=? AND lesson_id=? AND path_id=? AND role=? AND mode='independent' AND curriculum_version=? ORDER BY rowid DESC LIMIT 1",(row["id"],learner["id"],lesson_id,row["path_id"],row["role"],VERSION)).fetchone()
        attempt=dict(saved) if saved else None
        if not attempt:
            results.append({"lesson_id":lesson_id,"title":lesson.title,"attempt_id":None,"score":0,"critical_pass":False,"correction":"Start and complete this task on your own."});continue
        path=root/f"attempt-{attempt['id']}.sqlite"
        if not path.exists():raise HTTPException(503,"A saved final task is unavailable. Your history is safe. Ask the trainer to restore its training backup or start a fresh retake.")
        engine=engine_for(path)
        try:
            with Session(engine) as business:
                if lesson.workflow.startswith("read_"):
                    evidence=json.loads(attempt["evidence"])
                    question,answer,_=practical_question(lesson,"independent")
                    with store.connect() as registry:
                        read=registry.execute("SELECT 1 FROM events WHERE attempt_id=? AND kind='record_read' AND json_extract(detail,'$.path')=? LIMIT 1",(attempt["id"],inspection_endpoint(lesson,business))).fetchone()
                    untouched=read_only_unchanged(business,values(lesson,"independent")["actor"])
                    ok=bool(read and untouched and evidence.get("record_inspection") and normalize(evidence.get("observation",""))==normalize(answer))
                    if lesson.workflow=="read_pos":
                        from training.pos_review_scenarios import verify_pos_review
                        valid,_=verify_pos_review(business,lesson,values(lesson,"independent"));ok=ok and valid
                    if lesson.workflow=="read_report":
                        from training.report_scenarios import verify_report
                        valid,_=verify_report(business,lesson,values(lesson,"independent"));ok=ok and valid
                    if lesson.workflow=="read_procurement":
                        from training.procurement_scenarios import verify_procurement_inspection
                        valid,_=verify_procurement_inspection(business,lesson,"independent");ok=ok and valid
                    evidence={"record_inspection":bool(ok),"record_unchanged":bool(untouched),"correction":"Inspect the actual record, enter its observation through Check my work, and keep it unchanged."}
                else:ok,evidence=verify(business,lesson,"independent",store.business_actions(attempt["id"]))
        finally:engine.dispose()
        score=evidence.get("practical_score",100 if ok else 0)
        critical=evidence.get("critical_pass",bool(ok))
        if attempt["hints"]:
            score=0;critical=False;evidence={**evidence,"correction":"This final task used a hint. Start a fresh independent task in this final check."}
        correction=employee_feedback(evidence.get("correction", ""),lesson,values(lesson,"independent")) if score<100 else None
        results.append({"lesson_id":lesson_id,"title":lesson.title,"attempt_id":attempt["id"],"score":score,"critical_pass":bool(critical),"evidence":evidence,"correction":correction})
    return results


def register_assessments(router,store,root:Path,identity):
    class ExamStart(BaseModel):
        module: str | None = Field(default=None,pattern="^[A-Z]$")
        restart: bool = False

    class Answers(BaseModel):
        answers: dict[str,str] = Field(default_factory=dict,max_length=20)
        revision: int = Field(default=0,ge=0)

    def checked_answers(payload,row):
        allowed={question.id for question in row["questions"]}
        if not set(payload.answers)<=allowed or any(len(value)>200 for value in payload.answers.values()):raise HTTPException(422,"Answer only these final-check questions, using no more than 200 characters per answer.")
        return payload.answers

    @router.get("/exams")
    def exam_catalogue(request:Request):
        learner=identity(request)
        path=BY_PATH[learner["path_id"]]
        history=store.history(learner["id"]);exams=store.exams(learner["id"])
        modules=sorted({BY_ID[id].module for id in path.lessons})
        return {"path_id":path.id,"path_title":path.title,"assessment_version":ASSESSMENT_VERSION,"blueprints":[{**public_blueprint(row),"readiness":prerequisites(row,history,exams)} for row in [blueprint(path.id,module) for module in modules+[None]]],"history":[public_exam(row) for row in exams if row["path_id"]==path.id]}

    @router.post("/exams/start")
    def start_exam(payload:ExamStart,request:Request):
        learner=identity(request)
        try:row=blueprint(learner["path_id"],payload.module)
        except ValueError as exc:raise HTTPException(403,str(exc)) from exc
        with store.connect() as registry:
            existing=registry.execute("SELECT * FROM exams WHERE learner_id=? AND path_id=? AND module IS ? AND status='active'",(learner["id"],learner["path_id"],payload.module)).fetchone()
        if existing and not payload.restart and existing["curriculum_version"]==VERSION and existing["assessment_version"]==ASSESSMENT_VERSION:return public_exam(owned_current_exam(store,learner,existing["id"]))
        ready=prerequisites(row,store.history(learner["id"]),store.exams(learner["id"]))
        if not ready["ready"]:raise HTTPException(409,{"message":"Complete the applicable learning before starting this final check.",**ready})
        id=str(uuid.uuid4())
        with store.connect() as registry:
            registry.execute("BEGIN IMMEDIATE")
            # Serialize starts from two tabs. Continue the winner rather than
            # issuing two active exams or replacing an unseen concurrent start.
            current=registry.execute("SELECT * FROM exams WHERE learner_id=? AND path_id=? AND module IS ? AND status='active'",(learner["id"],learner["path_id"],payload.module)).fetchone()
            if current and not payload.restart and current["curriculum_version"]==VERSION and current["assessment_version"]==ASSESSMENT_VERSION:return public_exam(dict(current))
            if current:registry.execute("UPDATE exams SET status='reset',completed_at=CURRENT_TIMESTAMP WHERE id=?",(current["id"],))
            registry.execute("INSERT INTO exams(id,learner_id,path_id,role,module,curriculum_version,assessment_version,blueprint) VALUES (?,?,?,?,?,?,?,?)",(id,learner["id"],learner["path_id"],learner["role"],payload.module,VERSION,ASSESSMENT_VERSION,json.dumps(public_blueprint(row))))
        return public_exam(store.exam(learner["id"],id))

    @router.get("/exams/{exam_id}")
    def get_exam(exam_id:str,request:Request):
        learner=identity(request);row=store.exam(learner["id"],exam_id)
        if not row:raise HTTPException(404,"This final check was not found in your training history.")
        historical=row["path_id"]!=learner["path_id"] or row["role"]!=learner["role"] or row["curriculum_version"]!=VERSION or row["assessment_version"]!=ASSESSMENT_VERSION
        return {**public_exam(row),"historical":historical,**({"practical":practical_results(store,root,learner,row)} if row["status"]=="active" and not historical else {})}

    @router.post("/exams/{exam_id}/draft")
    def draft_exam(exam_id:str,payload:Answers,request:Request):
        learner=identity(request);exam=owned_current_exam(store,learner,exam_id)
        if exam["status"]!="active":raise HTTPException(409,"This final check is already graded; its result is preserved.")
        answers=checked_answers(payload,blueprint(exam["path_id"],exam["module"]))
        with store.connect() as registry:
            changed=registry.execute("UPDATE exams SET answers_draft=?,draft_revision=draft_revision+1 WHERE id=? AND status='active' AND draft_revision=?",(json.dumps(answers),exam_id,payload.revision)).rowcount
        if not changed:raise HTTPException(409,"The final answers changed or were graded in another tab. Reconnect to review the saved answers before editing again.")
        return {"saved":True,"revision":payload.revision+1}

    @router.post("/exams/{exam_id}/submit")
    def submit_exam(exam_id:str,payload:Answers,request:Request):
        learner=identity(request);exam=owned_current_exam(store,learner,exam_id)
        if exam["status"] in {"passed","failed"}:return public_exam(exam)
        if exam["status"]!="active":raise HTTPException(409,"This final check was restarted. Open the fresh retake.")
        row=blueprint(exam["path_id"],exam["module"]);answers=checked_answers(payload,row)
        knowledge=grade_knowledge(row,answers)
        practical=practical_results(store,root,learner,exam)
        practical_grade=grade_practical(practical)
        score=practical_grade["score"]
        critical=knowledge["critical_pass"] and practical_grade["critical_pass"]
        passed=knowledge["score"]>=85 and score>=90 and critical
        result={"learner_name":learner["name"],"path_title":row["path_title"],"role":exam["role"],"passed":passed,"knowledge":knowledge,"practical_score":score,"critical_score":100 if critical else 0,"practical":practical,"thresholds":row["thresholds"],"assessment_version":ASSESSMENT_VERSION,"curriculum_version":VERSION,"certificate":f"TRAINING-{exam_id}" if passed and exam["module"] is None else None,"meaning":"This certifies local training performance only. It grants no production access and does not verify Staff identity or externally delivered journals."}
        with store.connect() as registry:
            registry.execute("UPDATE exams SET status=?,completed_at=CURRENT_TIMESTAMP,answers_draft=?,result=? WHERE id=? AND status='active'",("passed" if passed else "failed",json.dumps(answers),json.dumps(result),exam_id))
        return public_exam(store.exam(learner["id"],exam_id))
