"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "../../../lib/api";
import { trainingEnabled, type TrainingAttempt } from "../../../lib/inventory-training";
import "../training.css";

type Learner = { id:string; name:string; role:string; attempts:TrainingAttempt[] };
export default function Management(){
  const[key,setKey]=useState("");const[learners,setLearners]=useState<Learner[]|null>(null);const[error,setError]=useState("");const[roles,setRoles]=useState<Record<string,string>>({});
  async function load(){try{const[catalogue,result]=await Promise.all([api<{roles:Record<string,string>}>("/training/catalogue"),api<{learners:Learner[]}>("/training/management",{headers:{"X-Training-Manager-Key":key}})]);setRoles(catalogue.roles);setLearners(result.learners);setError("")}catch(exception){setError((exception as Error).message)}}
  async function assign(learner:Learner,role:string){try{await api("/training/assign",{method:"POST",headers:{"X-Training-Manager-Key":key},body:JSON.stringify({learner_id:learner.id,role})});await load()}catch(exception){setError((exception as Error).message)}}
  if(!trainingEnabled)return <main>Trainer review is available only in Inventory Training.</main>;
  return <main className="inventory-training"><Link href="/training">← Training course</Link><p className="training-eyebrow">Trainer review</p><h1>See where employees need help.</h1><p>Review practical results, hints and corrections. These are training records and do not change production access.</p>{error&&<p className="training-error" role="alert">{error}</p>}
    {!learners?<form onSubmit={event=>{event.preventDefault();void load()}}><label>Trainer access code<input type="password" autoComplete="off" value={key} onChange={event=>setKey(event.target.value)}/></label><button className="training-primary">Open training progress</button></form>:<><button onClick={()=>void load()}>Refresh progress</button>{learners.map(learner=>{const independent=learner.attempts.filter(row=>row.status==="passed"&&row.mode==="independent");return <section key={learner.id} className="training-change"><h2>{learner.name}</h2><label>Assigned training path<select value={learner.role} onChange={event=>void assign(learner,event.target.value)}>{Object.entries(roles).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><p>{new Set(independent.map(row=>`${row.role}:${row.lesson_id}`)).size} skills demonstrated independently · {learner.attempts.reduce((total,row)=>total+row.hints,0)} hints used · {learner.attempts.reduce((total,row)=>total+row.mistakes,0)} corrections or failed actions</p><div className="table-wrap"><table><caption>Practice and assessment history for {learner.name}</caption><thead><tr><th>Lesson</th><th>Level</th><th>Result</th><th>Hints</th><th>Corrections</th><th>Started (Manila)</th></tr></thead><tbody>{learner.attempts.map(attempt=><tr key={attempt.id}><td>{attempt.lesson_id}</td><td>{attempt.mode}</td><td>{attempt.status==="passed"?"Passed":attempt.status==="reset"?"Reset; repeat recommended":"In progress"}</td><td>{attempt.hints}</td><td>{attempt.mistakes}</td><td>{new Date(attempt.started_at.replace(" ","T")+"Z").toLocaleString("en-PH",{timeZone:"Asia/Manila"})}</td></tr>)}</tbody></table></div></section>})}</>}
  </main>;
}
