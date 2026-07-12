"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { FeedbackBanner } from "../../../components/FeedbackBanner";
import { StatusBadge } from "../../../components/StatusBadge";
import { api } from "../../../lib/api";
import { formatDateTime, formatMoney } from "../../../lib/formatters";

type EventRow={id:string;event_type:string;aggregate_type:string;aggregate_id:string;idempotency_key:string;status:string;attempts:number;max_attempts:number;last_error:string|null;created_at:string;processed_at:string|null;amount:string;debit_account:string|null;credit_account:string|null;mapped:boolean};
type Rule={event_type:string;debit:string|null;credit:string|null};
type Workspace={summary:{pending:number;completed:number;failed:number;dead_letter:number;unmapped:number;queued_value:string};rules:Rule[];events:EventRow[]};

export default function Page(){
 const[data,setData]=useState<Workspace|null>(null);const[status,setStatus]=useState("");const[busy,setBusy]=useState(false);const[feedback,setFeedback]=useState<{tone:"success"|"error"|"info";title:string;message?:string}|null>(null);
 const load=useCallback(async()=>{try{setData(await api<Workspace>(`/integrations/accounting/workspace${status?`?status=${status}`:""}`))}catch(error){setFeedback({tone:"error",title:"Accounting workspace unavailable",message:(error as Error).message})}},[status]);
 useEffect(()=>{void load()},[load]);
 async function requeue(id:string){setBusy(true);try{await api(`/integrations/accounting/events/${id}/requeue`,{method:"POST"});setFeedback({tone:"success",title:"Accounting event requeued"});await load()}catch(error){setFeedback({tone:"error",title:"Requeue failed",message:(error as Error).message})}finally{setBusy(false)}}
 return <AppShell title="Accounting Integration" description="Reconcile inventory accounting events, journal mappings, delivery status, and external acknowledgements.">
  {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}
  <div className="topline"><Link href="/integrations">← Back to integrations</Link><select value={status} onChange={event=>setStatus(event.target.value)}><option value="">All statuses</option><option value="pending">Pending</option><option value="processing">Processing</option><option value="completed">Completed</option><option value="failed">Failed</option><option value="dead_letter">Dead letter</option></select></div>
  <section className="grid section-gap"><div className="card"><h2>Pending</h2><strong>{data?.summary.pending??0}</strong></div><div className="card"><h2>Failed</h2><strong>{data?.summary.failed??0}</strong></div><div className="card"><h2>Dead letter</h2><strong>{data?.summary.dead_letter??0}</strong></div><div className="card"><h2>Queued value</h2><strong>{formatMoney(data?.summary.queued_value??0)}</strong></div></section>
  <section className="card section-gap"><h2>Journal mapping rules</h2><p className="section-copy">Each inventory event is translated into an accounting intent before delivery. Unmapped events require review and should not be treated as posted journal entries.</p><div className="table-wrap"><table><thead><tr><th>Event type</th><th>Debit</th><th>Credit</th></tr></thead><tbody>{(data?.rules||[]).map(rule=><tr key={rule.event_type}><td>{rule.event_type}</td><td>{rule.debit||"Non-financial"}</td><td>{rule.credit||"Non-financial"}</td></tr>)}</tbody></table></div></section>
  <section className="card section-gap"><h2>Accounting event reconciliation</h2><div className="table-wrap"><table><thead><tr><th>Created</th><th>Event</th><th>Aggregate</th><th>Debit</th><th>Credit</th><th>Amount</th><th>Status</th><th>Attempts</th><th>Error</th><th>Action</th></tr></thead><tbody>{(data?.events||[]).map(row=><tr key={row.id}><td>{formatDateTime(row.created_at)}</td><td>{row.event_type}</td><td>{row.aggregate_type}: {row.aggregate_id}</td><td>{row.debit_account||"—"}</td><td>{row.credit_account||"—"}</td><td>{formatMoney(row.amount)}</td><td><StatusBadge status={row.mapped?row.status:"unmapped"}/></td><td>{row.attempts}/{row.max_attempts}</td><td>{row.last_error||"—"}</td><td>{["failed","dead_letter"].includes(row.status)?<button className="secondary compact" disabled={busy} onClick={()=>requeue(row.id)}>Requeue</button>:"—"}</td></tr>)}</tbody></table></div></section>
 </AppShell>;
}
