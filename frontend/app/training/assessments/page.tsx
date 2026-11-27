"use client";

import Link from "next/link";
import {useCallback,useEffect,useRef,useState} from "react";
import {api} from "../../../lib/api";
import {rememberTrainingAttempt} from "../../../lib/training-session";
import {trainingEnabled,type TrainingCatalogue,type TrainingProfile,type TrainingLesson} from "../../../lib/inventory-training";
import type {ExamCatalogue,ExamRecord,ExamBlueprint} from "../../../lib/training-exams";
import "../training.css";

export default function Assessments(){
  const[data,setData]=useState<ExamCatalogue|null>(null);
  const[catalogue,setCatalogue]=useState<TrainingCatalogue|null>(null);
  const[profile,setProfile]=useState<TrainingProfile|null>(null);
  const[selected,setSelected]=useState<ExamRecord|null>(null);
  const[answers,setAnswers]=useState<Record<string,string>>({});
  const[answerExam,setAnswerExam]=useState("");
  const[busy,setBusy]=useState(false);
  const[saving,setSaving]=useState(false);
  const[error,setError]=useState("");
  const draftRevision=useRef(0);
  const serverRevisions=useRef<Record<string,number>>({});
  const pendingDraft=useRef<Promise<unknown>>(Promise.resolve());
  const queueDraft=useCallback((id:string,answers:Record<string,string>)=>{
    const request=pendingDraft.current.catch(()=>undefined).then(async()=>{
      const result=await api<{revision:number}>(`/training/exams/${id}/draft`,{method:"POST",body:JSON.stringify({answers,revision:serverRevisions.current[id]||0})});
      serverRevisions.current[id]=result.revision;return result;
    });pendingDraft.current=request;return request;
  },[]);
  const refreshCatalogue=useCallback(async()=>setData(await api<ExamCatalogue>("/training/exams")),[]);
  function applyExam(exam:ExamRecord){serverRevisions.current[exam.id]=exam.draft_revision;setSelected(exam);setAnswers(exam.answers_draft);setAnswerExam(exam.id);setSaving(false);window.history.replaceState(null,"",`/training/assessments?exam=${encodeURIComponent(exam.id)}`)}
  useEffect(()=>{
    if(!trainingEnabled)return;
    void Promise.all([api<ExamCatalogue>("/training/exams"),api<TrainingCatalogue>("/training/catalogue"),api<TrainingProfile>("/training/me")]).then(async([data,catalogue,profile])=>{
      setData(data);setCatalogue(catalogue);setProfile(profile);
      const wanted=new URLSearchParams(window.location.search).get("exam")||data.history.find(exam=>exam.status==="active"&&exam.assessment_version===data.assessment_version)?.id;
      if(wanted)applyExam(await api<ExamRecord>(`/training/exams/${encodeURIComponent(wanted)}`));
    }).catch(exception=>setError((exception as Error).message));
  },[]);
  useEffect(()=>{
    const revision=++draftRevision.current;
    if(busy||!selected||selected.historical||selected.status!=="active"||answerExam!==selected.id||JSON.stringify(answers)===JSON.stringify(selected.answers_draft))return;
    setSaving(true);
    const timer=window.setTimeout(()=>{
      void queueDraft(selected.id,answers).then(()=>{
        if(revision!==draftRevision.current)return;
        setSelected(previous=>previous?.id===selected.id?{...previous,answers_draft:answers}:previous);setSaving(false);
      }).catch(exception=>{if(revision===draftRevision.current){setSaving(false);setError((exception as Error).message)}});
    },400);
    return()=>window.clearTimeout(timer);
  },[answers,answerExam,selected,queueDraft,busy]);
  async function saveNow(){if(selected?.status==="active"&&!selected.historical&&answerExam===selected.id&&JSON.stringify(answers)!==JSON.stringify(selected.answers_draft))await queueDraft(selected.id,answers)}
  async function openExam(id:string){setBusy(true);setError("");try{await saveNow();applyExam(await api<ExamRecord>(`/training/exams/${id}`))}catch(exception){setError((exception as Error).message)}finally{setBusy(false)}}
  async function start(row:ExamBlueprint,restart=false){setBusy(true);setError("");try{await saveNow();const exam=await api<ExamRecord>("/training/exams/start",{method:"POST",body:JSON.stringify({module:row.module,restart})});applyExam(await api<ExamRecord>(`/training/exams/${exam.id}`));await refreshCatalogue()}catch(exception){setError((exception as Error).message)}finally{setBusy(false)}}
  async function startTask(id:string){if(!selected)return;setBusy(true);setError("");try{await saveNow();const result=await api<{attempt_id:string;lesson:TrainingLesson}>("/training/start",{method:"POST",body:JSON.stringify({lesson_id:id,mode:"independent",exam_id:selected.id})});rememberTrainingAttempt(result.attempt_id);window.location.assign(result.lesson.route)}catch(exception){setError((exception as Error).message);setBusy(false)}}
  async function submit(){if(!selected)return;setBusy(true);setError("");try{await saveNow();applyExam(await api<ExamRecord>(`/training/exams/${selected.id}/submit`,{method:"POST",body:JSON.stringify({answers})}));await refreshCatalogue()}catch(exception){setError((exception as Error).message)}finally{setBusy(false)}}
  async function allChecks(){setBusy(true);try{await saveNow();setSelected(null);setAnswerExam("");window.history.replaceState(null,"","/training/assessments");await refreshCatalogue()}catch(exception){setError((exception as Error).message)}finally{setBusy(false)}}
  if(!trainingEnabled)return <main className="inventory-training"><h1>Final checks are available in Inventory Training</h1><Link href="/">Return home</Link></main>;
  const tasks=selected?.practical||selected?.result.practical||[];
  const practicalScore=tasks.length?tasks.reduce((total,task)=>total+task.score,0)/tasks.length:0;
  const practicalReady=tasks.length===selected?.blueprint.practical_lessons.length&&tasks.every(task=>task.critical_pass)&&practicalScore>=90;
  const allAnswered=!!selected&&selected.blueprint.questions.every(question=>answers[question.id]?.trim());
  return <main className="inventory-training training-exams">
    <header className="training-masthead"><Link className="training-brand" href="/training">Hidden Oasis <span>Inventory training</span></Link><span className="training-environment">TRAINING ONLY</span></header>
    <p className="training-final-link"><Link href="/training">← Your duty course</Link></p>
    {error&&<div className="training-error" role="alert"><p>{error}</p><button disabled={busy} onClick={()=>window.location.reload()}>Reconnect to final checks</button></div>}
    {!data&&!error&&<p role="status">Preparing your final checks…</p>}
    {data&&!selected&&<>
      <p className="training-eyebrow">{data.path_title}</p><h1>Show what you can do.</h1><p>Finish your practice and module checks before taking your course final.</p>
      <p className="training-rule">Pass marks: 85% for questions and 90% for practical work. Required checks must all be correct. Complete final tasks without hints.</p>
      <div className="training-exam-list">{data.blueprints.map(row=>{
        const active=data.history.find(exam=>exam.module===row.module&&exam.status==="active"&&exam.assessment_version===data.assessment_version&&exam.curriculum_version===row.version);
        const passed=data.history.some(exam=>exam.module===row.module&&exam.status==="passed"&&exam.assessment_version===data.assessment_version&&exam.curriculum_version===row.version);
        return <section key={row.module||"course"} className="training-exam-entry"><div><h2>{row.title}</h2><p>{row.lessons.length} skills · {row.practical_lessons.length} practical task(s) · {row.questions.length} knowledge questions</p>
          {passed?<p className="training-skill-status">Current final passed</p>:!row.readiness?.ready&&<><p>Finish the learning before this final.</p>{!!row.readiness?.missing_lessons.length&&<p className="training-exam-missing">Still to practise: {row.readiness.missing_lessons.slice(0,3).map(id=>catalogue?.lessons.find(lesson=>lesson.id===id)?.title||id).join("; ")}{row.readiness.missing_lessons.length>3?` and ${row.readiness.missing_lessons.length-3} more`:""}.</p>}{!!row.readiness?.missing_module_finals.length&&<p>Module finals still needed: {row.readiness.missing_module_finals.join(", ")}.</p>}</>}
        </div><button className={row.module?"":"training-primary"} disabled={busy||!active&&!row.readiness?.ready} onClick={()=>active?void openExam(active.id):void start(row)}>{active?"Continue final check":passed?"Take a fresh final":"Start final check"}</button></section>
      })}</div>
      {!!data.history.length&&<section className="training-change"><h2>Your final-check history</h2><div className="training-exam-history">{data.history.map(exam=><button key={exam.id} disabled={busy} onClick={()=>void openExam(exam.id)}>{exam.blueprint.title} · {exam.status==="reset"?"Restarted":exam.status} · {new Date(exam.started_at.replace(" ","T")+"Z").toLocaleString("en-PH",{timeZone:"Asia/Manila"})}</button>)}</div></section>}
    </>}
    {selected&&<>
      <button disabled={busy} onClick={()=>void allChecks()}>← All final checks</button><p className="training-eyebrow">{selected.blueprint.path_title||data?.path_title}</p><h1>{selected.blueprint.title}</h1>
      {selected.status==="active"&&!selected.historical?<>
        <p>Complete the tasks without hints, then answer the questions. Your answers save automatically.</p>
        <section><h2>1. Perform the work</h2><div className="training-exam-list">{selected.blueprint.practical_lessons.map(id=>{
          const task=tasks.find(task=>task.lesson_id===id),lesson=catalogue?.lessons.find(lesson=>lesson.id===id);
          const current=profile?.attempt?.exam_id===selected.id&&profile.attempt.lesson_id===id&&profile.lesson;
          return <article className="training-exam-task" key={id}><h3>{lesson?.title||id}</h3><p>{task?.score===100&&task.critical_pass?"Task complete.":task?.correction||"Complete this task on your own."}</p>
            {!!task?.evidence?.objectives&&<ul>{task.evidence.objectives.filter(objective=>!objective.passed).map(objective=><li key={objective.id}>{objective.title}{objective.critical?" · must be correct":""}</li>)}</ul>}
            {current?<Link className="training-primary" href={current.route}>{task?.score===100?"Inspect your saved work":"Continue this practice"}</Link>:<button disabled={busy||task?.score===100&&task.critical_pass} className="training-primary" onClick={()=>void startTask(id)}>{task?.score===100?"Task complete":"Start fresh independent task"}</button>}
          </article>
        })}</div></section>
        <form onSubmit={event=>{event.preventDefault();void submit()}}><h2>2. Check your understanding</h2><p>Use a number when the question asks for an amount. For yes/no questions, type yes or no.</p>
          {selected.blueprint.questions.map((question,index)=><label key={question.id} className="training-exam-question">{index+1}. {question.prompt}{question.critical&&<span className="training-critical-rule">Must be correct</span>}<input data-training-question={question.id} autoComplete="off" maxLength={200} value={answers[question.id]||""} onChange={event=>setAnswers(previous=>({...previous,[question.id]:event.target.value}))}/></label>)}
          <p role="status" aria-live="polite">{saving?"Saving answers…":"Answers saved"}</p>
          {!practicalReady&&<p>Finish the practical tasks before submitting. The required unit, quantity and approval checks must be correct.</p>}
          <button className="training-primary" disabled={busy||!allAnswered||!practicalReady}>{busy?"Checking your saved work…":"Submit final check"}</button>
        </form>
      </>:<section className="training-exam-result" aria-label="Final check result"><h2>{selected.historical?"Previous final-check history":selected.status==="passed"?"Final check passed":selected.status==="reset"?"This final check was restarted":"Practise these points, then try a fresh final"}</h2>
        {selected.result.knowledge&&<><dl className="training-exam-scores"><div><dt>Knowledge</dt><dd>{selected.result.knowledge.score}% · needs 85%</dd></div><div><dt>Practical work</dt><dd>{selected.result.practical_score}% · needs 90%</dd></div><div><dt>Checks that must be correct</dt><dd>{selected.result.critical_score===100?"All required checks passed":"A required check needs correction"}</dd></div></dl>
          {!!selected.result.certificate&&<p className="training-rule">{selected.result.learner_name||(selected.historical?"The participant recorded in this history":profile?.learner.name)} passed {selected.result.path_title||selected.blueprint.path_title||catalogue?.paths.find(path=>path.id===selected.path_id)?.title||"the earlier duty course"}. Training certificate: <strong>{selected.result.certificate}</strong>.</p>}
          {selected.result.knowledge.questions.filter(question=>!question.passed).map(question=><div className="training-exam-correction" key={question.id}><h3>{question.prompt}</h3><p>{question.correction}</p></div>)}
          {selected.result.practical?.filter(task=>task.score<100||!task.critical_pass).map(task=><div className="training-exam-correction" key={task.lesson_id}><h3>{task.title}</h3><p>{task.correction}</p></div>)}
        </>}
        <p>This result stays in your history. A retake starts a new final.</p>{selected.historical&&<p>This is an earlier result. Complete the current course for a new result.</p>}<button className="training-primary" disabled={busy||selected.path_id!==profile?.learner.path_id} onClick={()=>void start(selected.blueprint,true)}>Start a fresh retake</button>
      </section>}
      <p className="training-final-link"><Link href="/training">Return to your course and practise</Link></p>
    </>}
    <footer className="training-footer"><Link href="/training/management">Trainer progress review</Link></footer>
  </main>;
}
