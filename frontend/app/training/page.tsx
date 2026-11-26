"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, logout } from "../../lib/api";
import {rememberTrainingAttempt} from "../../lib/training-session";
import { mastery, trainingEnabled, type TrainingCatalogue, type TrainingLesson, type TrainingProfile } from "../../lib/inventory-training";
import "./training.css";

export default function TrainingPage() {
  const [catalogue, setCatalogue] = useState<TrainingCatalogue | null>(null);
  const [profile, setProfile] = useState<TrainingProfile | null>(null);
  const [selected, setSelected] = useState<TrainingLesson | null>(null);
  const [pathId, setPathId] = useState("stockroom");
  const [name, setName] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"course" | "reference" | "simulations">("course");
  const lessonDialog = useRef<HTMLDialogElement>(null);
  useEffect(()=>{if(selected&&!lessonDialog.current?.open)lessonDialog.current?.showModal()},[selected]);
  const load = useCallback(async () => {
    if (!trainingEnabled) return;
    try {
      const result = await api<TrainingCatalogue>("/training/catalogue");
      if (result.environment !== "isolated-training") throw new Error("This server is not the training environment.");
      setCatalogue(result);
      const me = await api<TrainingProfile>("/training/me").catch(() => null);
      setProfile(me);
      if (me) { setName(me.learner.name); setPathId(me.learner.path_id||"role-"+me.learner.role); if (me.attempt) rememberTrainingAttempt(me.attempt.id); }
    } catch (exception) { setError((exception as Error).message); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const activePath=catalogue?.paths.find(path=>path.id===(profile?.learner.path_id||pathId));
  const chosenPath=catalogue?.paths.find(path=>path.id===pathId);
  const role=profile?.learner.role||chosenPath?.role||"inventory_manager";
  const lessons = useMemo(() => catalogue?.lessons.filter(lesson => lesson.roles.includes(role) && (!activePath||activePath.lessons.includes(lesson.id)) && `${lesson.title} ${lesson.concept} ${lesson.rule}`.toLowerCase().includes(search.toLowerCase())) || [], [catalogue, activePath, role, search]);
  const assigned = catalogue?.lessons.filter(lesson => lesson.roles.includes(role)&&(!activePath||activePath.lessons.includes(lesson.id))) || [];
  const completed = assigned.filter(lesson => mastery(profile?.history || [], lesson, profile?.learner.role || role).independent).length;
  const next = assigned.find(lesson => !mastery(profile?.history || [], lesson, profile?.learner.role || role).independent);

  async function enrol(targetPath=pathId) {
    setBusy(true); setError("");
    try { const path=catalogue?.paths.find(row=>row.id===targetPath);if(!path)throw new Error("Choose your assigned duty course.");await api("/training/enrol", {method:"POST", body:JSON.stringify({name, role:path.role,path_id:path.id})}); setSelected(null); await load(); }
    catch (exception) { setError((exception as Error).message); }
    finally { setBusy(false); }
  }
  async function start(lesson: TrainingLesson, mode: string) {
    setBusy(true); setError("");
    try {
      const result = await api<{attempt_id:string;lesson:TrainingLesson}>("/training/start", {method:"POST", body:JSON.stringify({lesson_id:lesson.id, mode})});
      rememberTrainingAttempt(result.attempt_id);
      window.location.assign(result.lesson.route);
    } catch (exception) { setError((exception as Error).message); setBusy(false); }
  }
  if (!trainingEnabled) return <main className="inventory-training"><h1>Training is a separate application</h1><p>Use your resort&apos;s Inventory Training link. Training is unavailable in the operational deployment.</p><Link href="/">Return home</Link></main>;
  return <main className="inventory-training">
    <header className="training-masthead"><Link href="/training" className="training-brand">Hidden Oasis <span>Inventory training</span></Link><span className="training-environment">TRAINING ONLY · Fictional records</span></header>
    {error && <div className="training-error" role="alert"><p>{error}</p><button onClick={()=>void load()}>Try again</button></div>}
    {!catalogue && !error && <p role="status">Preparing your training…</p>}
    {catalogue && !profile && <section className="training-welcome">
      <p className="training-eyebrow">Learn with the actual Inventory screens</p><h1>Practise your work.<br/>Build confidence, one task at a time.</h1>
      <p>Learn how supplies move through Hidden Oasis, practise safely, then show what you can do on your own. Training uses fictional records in a separate environment.</p>
      <form onSubmit={event=>{event.preventDefault();void enrol()}} className="training-enrol">
        <label>Your name<input autoComplete="given-name" required maxLength={80} value={name} onChange={event=>setName(event.target.value)}/></label>
        <label>Your training responsibilities<select value={pathId} onChange={event=>setPathId(event.target.value)}>{catalogue.paths.map(path=><option key={path.id} value={path.id}>{path.title}</option>)}</select></label><p>{chosenPath?.description}</p>
        <p>Choose the work you have been assigned. You can practise another path later. Choosing a path here gives no access to production.</p>
        <button className="training-primary" disabled={busy}>{busy?"Preparing…":"Start training"}</button>
      </form>
    </section>}
    {catalogue && profile && <>
      <section className="training-overview"><div><p className="training-eyebrow">{activePath?.title||catalogue.roles[profile.learner.role]}</p><h1>Welcome back, {profile.learner.name}.</h1><p>Learn the situation, practise with guidance, then try a new task on your own.</p></div><div className="training-progress"><strong>{completed} / {assigned.length}</strong><span>skills demonstrated independently</span><progress aria-label="Training progress" value={completed} max={Math.max(1,assigned.length)}/></div></section>
      <section className="training-next"><div><span>Your next step</span><h2>{profile.attempt?.status==="active"?profile.lesson?.title:next?.title||"Review your training"}</h2><p>{profile.attempt?.status==="active"?"Your saved practice is ready to continue.":"Start with a worked example. You will use the same controls as Inventory."}</p></div>{profile.attempt?.status==="active"&&profile.lesson?<Link className="training-primary" href={profile.lesson.route}>Continue practice →</Link>:next?<button className="training-primary" onClick={()=>setSelected(next)}>Continue training →</button>:<Link className="training-primary" href="/training/assessments">Open final checks →</Link>}</section>
      <p className="training-final-link"><Link href="/training/assessments">Module and duty-course final checks →</Link></p>
      <nav className="training-tabs" aria-label="Training library"><button aria-current={tab==="course"?"page":undefined} onClick={()=>setTab("course")}>Your course</button><button aria-current={tab==="reference"?"page":undefined} onClick={()=>setTab("reference")}>Quick reference</button><button aria-current={tab==="simulations"?"page":undefined} onClick={()=>setTab("simulations")}>Resort simulations</button></nav>
      {tab!=="simulations"&&<label className="training-search">Find a lesson or situation<input type="search" placeholder="Try partial delivery, count, waste…" value={search} onChange={event=>setSearch(event.target.value)}/></label>}
      {tab==="simulations"?<div className="training-simulations">{catalogue.capstones.map(capstone=><section key={capstone.id}><h2>{capstone.title}</h2><p>{capstone.linked?"Complete the connected actions in one evolving practice record. Simulated colleagues handle their authorized responsibilities.":"Work through your authorized tasks. Each exercise has a separate practice record; this sequence has not yet become a linked capstone."}</p><ol>{capstone.lessons.map(id=>{const lesson=catalogue.lessons.find(row=>row.id===id)!;const allowed=lesson.roles.includes(profile.learner.role);return <li key={id}>{allowed?<button onClick={()=>setSelected(lesson)}>{lesson.title}</button>:<span>{lesson.title} · another role</span>}</li>})}</ol></section>)}</div>:<div className="training-lessons">{lessons.map(lesson=>{const status=mastery(profile.history,lesson,profile.learner.role);return <article key={lesson.id}><span className="training-module">{lesson.module}</span><div><button className="training-lesson-title" onClick={()=>setSelected(lesson)}>{lesson.title}</button><p>{tab==="reference"?lesson.rule:lesson.concept}</p><span className="training-skill-status">{status.independent?"Independent task passed":status.assisted?"Ready for independent assessment":status.guided?"Guided practice passed":"Ready to learn"}</span></div><button className="training-open" onClick={()=>setSelected(lesson)} aria-label={`Open ${lesson.title}`}>→</button></article>})}{!lessons.length&&<p>No matching lessons. Try a shorter word or clear the search.</p>}</div>}
      <details className="training-change"><summary>Practise another training path</summary><p>Your previous attempts stay in your history. The current practice closes when you change paths.</p><label>Responsibilities<select value={pathId} onChange={event=>setPathId(event.target.value)}>{catalogue.paths.map(path=><option key={path.id} value={path.id}>{path.title}</option>)}</select></label><p>{chosenPath?.description}</p><button disabled={busy} onClick={()=>void enrol()}>Use this training path</button></details>
      {profile.assignments.length>1&&<section className="training-change"><h2>Your duty courses</h2><p>Your shared skills and earlier course results stay in your history.</p><div className="training-course-choices">{profile.assignments.map(assignment=>{const path=catalogue.paths.find(row=>row.id===assignment.path_id);if(!path)return null;const completed=catalogue.lessons.filter(lesson=>path.lessons.includes(lesson.id)&&mastery(profile.history,lesson,path.role).independent).length;return <button key={path.id} disabled={busy||path.id===profile.learner.path_id} onClick={()=>void enrol(path.id)}>{path.title} · {completed}/{path.lessons.length}</button>})}</div></section>}
      <footer className="training-footer"><p>A training pass demonstrates practice competence. Production permissions require separate authorization.</p><Link href="/training/management">Trainer progress review</Link><button disabled={busy} onClick={()=>{setBusy(true);void logout().catch(exception=>{setError((exception as Error).message);setBusy(false)})}}>Sign out for another employee</button></footer>
    </>}
    {selected&&profile&&<dialog ref={lessonDialog} onCancel={()=>setSelected(null)} className="training-lesson" aria-label="Lesson overview"><button className="training-back" onClick={()=>setSelected(null)}>← Back to your course</button><p className="training-eyebrow">Module {selected.module} · Watch and understand</p><h2>{selected.title}</h2><h3>The situation</h3><p>{selected.situation}</p><h3>What this means</h3><p>{selected.concept}</p><h3>A worked example</h3><p>{selected.example}</p><h3>Remember this</h3><p className="training-rule">{selected.rule}</p><h3>Your practice</h3><p>You will work in the actual Inventory screen. Perform the task and answer a short check. The application checks the actual result before marking it passed.</p>
      {selected.global_access&&<p className="training-example">This practice includes an approved assignment across locations. In real work, use only the locations and financial limits assigned to you. Ask the authorized colleague when access is missing.</p>}
      <div className="training-levels">{(["guided","assisted","independent"] as const).map((mode,index)=>{const status=mastery(profile.history,selected,profile.learner.role);const disabled=busy||(mode==="assisted"&&!status.guided)||(mode==="independent"&&(!status.guided||!status.assisted));return <div key={mode}><strong>{index+2}. {mode==="guided"?"Guided practice":mode==="assisted"?"Try with help available":"Independent assessment"}</strong><p>{mode==="guided"?"Follow one highlighted action at a time.":mode==="assisted"?"Use the situation; request a hint if needed.":"A different task, without step-by-step guidance."}</p><button className={mode==="guided"?"training-primary":""} disabled={disabled} onClick={()=>void start(selected,mode)}>{status[mode]?"Repeat":"Start"} {mode} practice</button></div>})}</div>
      <details><summary>Workflow reference</summary><p>{selected.rule}</p><ul>{selected.steps.map((step,index)=><li key={index}>{step.instruction}</li>)}</ul></details>
    </dialog>}
  </main>;
}
