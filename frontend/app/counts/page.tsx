"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Can } from "../../components/SessionContext";
import { DataTable } from "../../components/DataTable";
import { FeedbackBanner } from "../../components/FeedbackBanner";
import { FormField, FormSection } from "../../components/FormField";
import { StatusBadge } from "../../components/StatusBadge";
import { api } from "../../lib/api";
import { formatDateTime, formatMoney, formatQuantity } from "../../lib/formatters";

type Location={id:string;code:string;name:string;is_active:boolean};
type Count={id:string;count_number:string;location_id:string;location_code:string;location_name:string;status:string;notes:string|null;blind_count:boolean;approval_threshold:string;created_at:string;posted_document_id:string|null;progress:{total_lines:number;counted_lines:number;remaining_lines:number;completion_percent:number;variance_lines:number;absolute_variance:string;estimated_value_variance:string;live_drift_lines:number}};

export default function CountsPage(){
  const[locations,setLocations]=useState<Location[]>([]);
  const[counts,setCounts]=useState<Count[]>([]);
  const[loading,setLoading]=useState(true);
  const[saving,setSaving]=useState(false);
  const[error,setError]=useState("");
  const[feedback,setFeedback]=useState<{tone:"success"|"error"|"info";title:string;message?:string}|null>(null);

  const load=useCallback(async()=>{setLoading(true);setError("");try{const[l,c]=await Promise.all([api<Location[]>("/locations"),api<Count[]>("/counts/workspace")]);setLocations(l.filter(row=>row.is_active));setCounts(c)}catch(exception){setError((exception as Error).message)}finally{setLoading(false)}},[]);
  useEffect(()=>{void load()},[load]);

  async function create(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget;const data=new FormData(form);setSaving(true);setFeedback(null);try{const count=await api<Count>("/counts",{method:"POST",body:JSON.stringify({location_id:data.get("location_id"),notes:data.get("notes")||null,blind_count:data.get("blind_count")==="on",approval_threshold:Number(data.get("approval_threshold")||0)})});form.reset();setFeedback({tone:"success",title:"Count session created",message:`${count.count_number} is ready for counting.`});await load()}catch(exception){setFeedback({tone:"error",title:"Count could not be created",message:(exception as Error).message})}finally{setSaving(false)}}

  const rows=counts.map(count=>[
    <Link className="catalogue-link" href={`/counts/${count.id}`} key={count.id}>{count.count_number}</Link>,
    `${count.location_code} — ${count.location_name}`,
    <StatusBadge status={count.status} key={`${count.id}-status`}/>,
    count.blind_count?"Blind":"Visible",
    `${count.progress.counted_lines}/${count.progress.total_lines}`,
    `${count.progress.completion_percent}%`,
    count.progress.variance_lines,
    formatQuantity(count.progress.absolute_variance),
    formatMoney(count.progress.estimated_value_variance),
    count.progress.live_drift_lines,
    formatDateTime(count.created_at),
    count.posted_document_id?<Link className="catalogue-link" href={`/stock/documents/${count.posted_document_id}`} key={`${count.id}-doc`}>Open document</Link>:<Link className="catalogue-link" href={`/counts/${count.id}`} key={`${count.id}-action`}>{count.status==="open"?"Continue":count.status==="pending_approval"?"Review":"Open"}</Link>,
  ]);

  return <AppShell title="Counts" description="Run guided blind counts, save progress, review variances, request recounts, and post approved adjustments.">
    <Can permission="counts.create"><section className="card"><div className="topline"><div><h2>Start physical count</h2><p>Create a location-scoped count using a frozen stock snapshot. Blind mode hides expected quantities until review.</p></div></div><form onSubmit={create}><FormSection title="Count setup"><FormField label="Location" name="count-location" required><select name="location_id" required defaultValue=""><option value="">Select location</option>{locations.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></FormField><FormField label="Approval threshold" name="count-threshold" required hint="Largest absolute line variance allowed before approval is required. Use 0 for automatic posting."><input name="approval_threshold" type="number" min="0" step="0.0001" defaultValue="0"/></FormField><FormField label="Notes" name="count-notes" optional><textarea name="notes"/></FormField><label className="check-control"><input type="checkbox" name="blind_count" defaultChecked/><span><strong>Blind count</strong><small>Hide expected quantities from counters until submission or review.</small></span></label></FormSection><div className="form-actions"><button className="primary" disabled={saving}>{saving?"Creating count…":"Start count"}</button></div></form>{feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}</section></Can>

    <section className="card section-gap"><div className="topline"><div><h2>Count sessions</h2><p>Track completion, variances, stock drift, approval status, and posted adjustment documents.</p></div></div><DataTable columns={["Count","Location","Status","Mode","Progress","Complete","Variance lines","Absolute variance","Estimated value","Live drift","Created","Action"]} rows={rows} rowIds={counts.map(row=>row.id)} loading={loading} error={error} onRetry={()=>void load()} searchPlaceholder="Search count, location, status, or mode" exportFileName="hidden-oasis-count-sessions" emptyTitle="No count sessions" emptyMessage="Start the first physical count for an active location."/></section>
  </AppShell>;
}
