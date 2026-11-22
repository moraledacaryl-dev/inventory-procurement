"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "../../components/AppShell";
import { Can } from "../../components/SessionContext";
import { DataTable } from "../../components/DataTable";
import { FeedbackBanner } from "../../components/FeedbackBanner";
import { FormField, FormSection } from "../../components/FormField";
import { StatusBadge } from "../../components/StatusBadge";
import { api } from "../../lib/api";

type Location={id:string;code:string;name:string;is_active:boolean};
type Count={id:string;count_number:string;location_id:string;location_code:string;location_name:string;status:string;notes:string|null;blind_count:boolean;approval_threshold:string;created_at:string;posted_document_id:string|null;progress:{total_lines:number;counted_lines:number;remaining_lines:number;completion_percent:number;variance_lines:number;absolute_variance:string;estimated_value_variance:string;live_drift_lines:number}};

export default function CountsPage(){
  const router=useRouter();
  const[locations,setLocations]=useState<Location[]>([]);
  const[counts,setCounts]=useState<Count[]>([]);
  const[loading,setLoading]=useState(true);
  const[saving,setSaving]=useState(false);
  const[error,setError]=useState("");
  const[feedback,setFeedback]=useState<{tone:"success"|"error"|"info";title:string;message?:string}|null>(null);

  const load=useCallback(async()=>{setLoading(true);setError("");try{const[l,c]=await Promise.all([api<Location[]>("/locations"),api<Count[]>("/counts/workspace")]);setLocations(l.filter(row=>row.is_active));setCounts(c)}catch(exception){setError((exception as Error).message)}finally{setLoading(false)}},[]);
  useEffect(()=>{void load()},[load]);

  async function create(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget;const data=new FormData(form);setSaving(true);setFeedback(null);try{const count=await api<Count>("/counts",{method:"POST",body:JSON.stringify({location_id:data.get("location_id"),notes:data.get("notes")||null,blind_count:data.get("blind_count")==="on",approval_threshold:Number(data.get("approval_threshold")||0)})});form.reset();router.push(`/counts/${count.id}`)}catch(exception){setFeedback({tone:"error",title:"Count could not be created",message:(exception as Error).message})}finally{setSaving(false)}}


  return <AppShell title="Counts" description="Count what you can see on the shelf, then save and send it for review.">
    <Can permission="counts.create"><details className="card workflow-disclosure"><summary><div className="topline"><div><h2>Start a new count</h2><p>Pick the storage area you will count. You will enter item quantities on the next screen.</p></div></div><span className="disclosure-mark" aria-hidden="true">+</span></summary><div className="workflow-disclosure-body"><form onSubmit={create}><FormSection title="Where will you count?"><FormField label="Location" name="count-location" required><select name="location_id" required defaultValue=""><option value="">Select location</option>{locations.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></FormField><FormField label="Review limit (for managers)" name="count-threshold" required hint="Set how much difference an authorized approver may accept automatically. Leave 0 unless your supervisor tells you otherwise. Staff counts with differences can still require approval."><input name="approval_threshold" type="number" min="0" step="0.0001" defaultValue="0"/></FormField><FormField label="Notes" name="count-notes" optional><textarea name="notes"/></FormField><label className="check-control"><input type="checkbox" name="blind_count" defaultChecked/><span><strong>Count without seeing expected stock</strong><small>Recommended: the number already saved in the system stays hidden until review.</small></span></label></FormSection><div className="form-actions"><button className="primary" disabled={saving}>{saving?"Starting…":"Start counting items"}</button></div></form>{feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}</div></details></Can>

    {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}
    <section className="card section-gap"><div className="topline"><div><h2>Counts in progress and completed</h2><p>Choose Continue to finish a count. Choose Review if a count needs approval.</p></div></div><DataTable columns={["Count","Storage area","Status","Items counted","Differences","Next step"]} rows={counts.map(count=>[<Link className="catalogue-link" href={`/counts/${count.id}`} key={count.id}>{count.count_number}</Link>,`${count.location_code} — ${count.location_name}`,<StatusBadge key={`${count.id}-status`} status={count.status}/>,`${count.progress.counted_lines} / ${count.progress.total_lines}`,count.progress.variance_lines,<Link className="catalogue-link" href={`/counts/${count.id}`} key={`${count.id}-action`}>{count.status==="open"?"Continue counting":count.status==="pending_approval"?"Review count":"View count"}</Link>])} rowIds={counts.map(row=>row.id)} loading={loading} error={error} onRetry={()=>void load()} searchPlaceholder="Search counts or locations" exportFileName="hidden-oasis-count-sessions" emptyTitle="No count sessions" emptyMessage="Start a count for your storage area."/></section>
  </AppShell>;
}
