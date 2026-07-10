"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { DataTable } from "../../components/DataTable";
import { api } from "../../lib/api";

type Summary={open_feedback:number;high_priority_feedback:number;open_incidents:number;critical_incidents:number;failed_acceptance_runs:number;dead_letter_events:number;status:string};
type Feedback={id:string;category:string;severity:string;page:string|null;message:string;status:string;created_at:string};
type Incident={id:string;incident_number:string;source:string;severity:string;title:string;status:string;request_id:string|null;created_at:string};
type Smoke={status:string;checks:Record<string,boolean>};

export default function Page(){
  const[summary,setSummary]=useState<Summary|null>(null);const[feedback,setFeedback]=useState<Feedback[]>([]);const[incidents,setIncidents]=useState<Incident[]>([]);const[smoke,setSmoke]=useState<Smoke|null>(null);const[msg,setMsg]=useState("");
  const load=useCallback(async()=>{try{const[s,f,i]=await Promise.all([api<Summary>("/rollout/summary"),api<Feedback[]>("/feedback"),api<Incident[]>("/incidents")]);setSummary(s);setFeedback(f);setIncidents(i)}catch(error){setMsg((error as Error).message)}},[]);
  useEffect(()=>{void load()},[load]);
  async function submitFeedback(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget,d=new FormData(form);try{await api("/feedback",{method:"POST",body:JSON.stringify({category:d.get("category"),severity:d.get("severity"),page:d.get("page")||null,message:d.get("message"),context:{user_agent:navigator.userAgent}})});form.reset();setMsg("Feedback submitted.");await load()}catch(error){setMsg((error as Error).message)}}
  async function runSmoke(){try{const result=await api<Smoke>("/rollout/smoke-test",{method:"POST"});setSmoke(result);setMsg(`Smoke test ${result.status}.`);await load()}catch(error){setMsg((error as Error).message)}}
  async function resolveFeedback(id:string){try{await api(`/feedback/${id}`,{method:"PATCH",body:JSON.stringify({status:"resolved"})});await load()}catch(error){setMsg((error as Error).message)}}
  async function resolveIncident(id:string){try{await api(`/incidents/${id}`,{method:"PATCH",body:JSON.stringify({status:"resolved"})});await load()}catch(error){setMsg((error as Error).message)}}
  return <AppShell title="Rollout & Stabilization">
    <section className="grid"><div className="card"><h2>Go-live decision</h2><strong>{summary?.status?.toUpperCase()||"LOADING"}</strong><p>High-priority feedback, critical incidents, and dead letters must be zero.</p></div><div className="card"><h2>Open feedback</h2><strong>{summary?.open_feedback??0}</strong><p>{summary?.high_priority_feedback??0} high priority</p></div><div className="card"><h2>Open incidents</h2><strong>{summary?.open_incidents??0}</strong><p>{summary?.critical_incidents??0} critical</p></div></section>
    <section className="card section-gap"><div className="topline"><div><h2>Operational smoke test</h2><p>Checks database, master access, stock reconciliation, integrations, and backup presence.</p></div><button className="primary compact" onClick={runSmoke}>Run smoke test</button></div>{smoke&&<DataTable columns={["Check","Result"]} rows={Object.entries(smoke.checks).map(([key,value])=>[key,value?"Passed":"Failed"])}/>}</section>
    <section className="card section-gap"><h2>Staff feedback</h2><form className="inline-form" onSubmit={submitFeedback}><select name="category" aria-label="Feedback category"><option value="bug">Bug</option><option value="usability">Usability</option><option value="data">Data</option><option value="training">Training</option><option value="request">Request</option></select><select name="severity" aria-label="Feedback severity"><option value="normal">Normal</option><option value="low">Low</option><option value="high">High</option><option value="critical">Critical</option></select><input name="page" placeholder="Page or workflow"/><textarea name="message" placeholder="Describe what happened or what was difficult" required/><button className="primary compact">Submit feedback</button></form><DataTable columns={["Date","Category","Severity","Page","Message","Status","Action"]} rows={feedback.map(x=>[new Date(x.created_at).toLocaleString(),x.category,x.severity,x.page||"",x.message,x.status,x.status!=="resolved"?<button className="secondary" onClick={()=>resolveFeedback(x.id)}>Resolve</button>:""])}/></section>
    <section className="card section-gap"><h2>Operational incidents</h2><DataTable columns={["Incident","Date","Source","Severity","Title","Request ID","Status","Action"]} rows={incidents.map(x=>[x.incident_number,new Date(x.created_at).toLocaleString(),x.source,x.severity,x.title,x.request_id||"",x.status,x.status!=="resolved"?<button className="secondary" onClick={()=>resolveIncident(x.id)}>Resolve</button>:""])}/></section>
    <section className="card section-gap"><h2>Pilot rollout gates</h2><div className="table-wrap"><table><tbody><tr><td>Staff group</td><td>Start with owner, inventory manager, receiver, and one café user</td></tr><tr><td>Duration</td><td>Operate in pilot for at least seven real business days</td></tr><tr><td>Daily review</td><td>Check feedback, incidents, dead letters, negative stock, and backup status</td></tr><tr><td>Reconciliation</td><td>Compare selected physical counts, POS consumption, and supplier receipts</td></tr><tr><td>Go-live</td><td>Proceed only when summary is GO and the latest acceptance and smoke tests pass</td></tr></tbody></table></div></section>
    {msg&&<p className="status" role="status">{msg}</p>}
  </AppShell>
}
