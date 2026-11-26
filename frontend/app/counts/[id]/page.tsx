"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "../../../components/AppShell";
import { Can } from "../../../components/SessionContext";
import { ConfirmDialog } from "../../../components/ConfirmDialog";
import { ErrorState, LoadingState } from "../../../components/AsyncState";
import { FeedbackBanner } from "../../../components/FeedbackBanner";
import { StatusBadge } from "../../../components/StatusBadge";
import { api } from "../../../lib/api";
import { formatDateTime, formatMoney, formatQuantity } from "../../../lib/formatters";

type CountLine={id:string;item_id:string;sku:string;item_name:string;system_quantity:string|null;snapshot_quantity:string|null;live_quantity:string|null;counted_quantity:string|null;variance_quantity:string|null;live_drift_quantity:string|null;note:string|null};
type CountDetail={id:string;count_number:string;location_id:string;location_code:string;location_name:string;status:string;notes:string|null;blind_count:boolean;approval_threshold:string;created_by_user_id:string;approved_by_user_id:string|null;approved_at:string|null;created_at:string;posted_document_id:string|null;progress:{total_lines:number;counted_lines:number;remaining_lines:number;completion_percent:number;variance_lines:number|null;absolute_variance:string|null;estimated_value_variance:string|null;live_drift_lines:number|null};lines:CountLine[]};
type DraftLine={item_id:string;counted_quantity:string;note:string};

type PendingAction="submit"|"approve"|"cancel"|null;

export default function CountDetailPage(){
  const{id}=useParams<{id:string}>();
  const[data,setData]=useState<CountDetail|null>(null);
  const[draft,setDraft]=useState<Record<string,DraftLine>>({});
  const[loading,setLoading]=useState(true);
  const[saving,setSaving]=useState(false);
  const[error,setError]=useState("");
  const[feedback,setFeedback]=useState<{tone:"success"|"error"|"info"|"warning";title:string;message?:string}|null>(null);
  const[pending,setPending]=useState<PendingAction>(null);
  const[recountIds,setRecountIds]=useState<string[]>([]);
  const[recountReason,setRecountReason]=useState("");

  const hydrate=(detail:CountDetail)=>{setData(detail);setDraft(Object.fromEntries(detail.lines.map(line=>[line.item_id,{item_id:line.item_id,counted_quantity:line.counted_quantity??"",note:line.note??""}])))};
  const load=useCallback(async()=>{setLoading(true);setError("");try{hydrate(await api<CountDetail>(`/counts/${id}/detail`))}catch(exception){setError((exception as Error).message)}finally{setLoading(false)}},[id]);
  useEffect(()=>{void load()},[load]);

  const changed=useMemo(()=>data?data.lines.some(line=>{const row=draft[line.item_id];return row&&(row.counted_quantity!==(line.counted_quantity??"")||row.note!==(line.note??""))}):false,[data,draft]);
  const allCounted=useMemo(()=>data?data.lines.every(line=>draft[line.item_id]?.counted_quantity!=="" && draft[line.item_id]?.counted_quantity!==undefined):false,[data,draft]);
  const validDraft=useMemo(()=>data?data.lines.every(line=>{const value=draft[line.item_id]?.counted_quantity??"";return value===""||(Number.isFinite(Number(value))&&Number(value)>=0)}):false,[data,draft]);
  const enteredCount=useMemo(()=>data?data.lines.filter(line=>(draft[line.item_id]?.counted_quantity??"")!=="").length:0,[data,draft]);
  const canSubmit=allCounted&&validDraft&&!changed;

  async function save(){if(!data)return;if(!validDraft){setFeedback({tone:"error",title:"Check your counts",message:"Enter 0 or a positive number for each counted item. Do not use negative quantities."});return}const lines=data.lines.filter(line=>{const row=draft[line.item_id];return row&&row.counted_quantity!==""}).map(line=>({item_id:line.item_id,counted_quantity:Number(draft[line.item_id].counted_quantity),note:draft[line.item_id].note||null}));if(!lines.length){setFeedback({tone:"error",title:"Enter at least one counted quantity"});return}setSaving(true);setFeedback(null);try{hydrate(await api<CountDetail>(`/counts/${id}/entries`,{method:"PUT",body:JSON.stringify({lines})}));setFeedback({tone:"success",title:"Count progress saved",message:`${lines.length} line(s) are stored. You can leave and continue later.`})}catch(exception){setFeedback({tone:"error",title:"Count progress could not be saved",message:(exception as Error).message})}finally{setSaving(false)}}

  async function runAction(action:PendingAction){if(!action)return;setSaving(true);setFeedback(null);try{let result:CountDetail;if(action==="submit")result=await api(`/counts/${id}/submit`,{method:"POST"});else if(action==="approve")result=await api(`/counts/${id}/approve-guided`,{method:"POST"});else result=await api(`/counts/${id}/cancel-guided`,{method:"POST"});hydrate(result);setFeedback({tone:"success",title:action==="submit"?(result.status==="pending_approval"?"Count submitted for approval":"Count posted"):action==="approve"?"Count approved and posted":"Count cancelled",message:result.posted_document_id?"An immutable count-adjustment document was created.":undefined});setPending(null)}catch(exception){setFeedback({tone:"error",title:"Action could not be completed",message:(exception as Error).message});setPending(null)}finally{setSaving(false)}}

  async function requestRecount(){if(!recountIds.length||!recountReason.trim()){setFeedback({tone:"error",title:"Select variance lines and enter a recount reason"});return}setSaving(true);try{hydrate(await api<CountDetail>(`/counts/${id}/recount`,{method:"POST",body:JSON.stringify({item_ids:recountIds,reason:recountReason.trim()})}));setRecountIds([]);setRecountReason("");setFeedback({tone:"success",title:"Recount requested",message:"Selected lines were cleared and the session returned to open status."})}catch(exception){setFeedback({tone:"error",title:"Recount could not be requested",message:(exception as Error).message})}finally{setSaving(false)}}

  if(error)return <AppShell title="Count session"><ErrorState title="Count session unavailable" message={error} onRetry={()=>void load()}/></AppShell>;
  if(loading||!data)return <AppShell title="Count session"><LoadingState title="Loading count session" rows={6}/></AppShell>;

  // A masked blind-count field is unknown to this viewer, not zero.
  const canSeeVariance=data.progress.variance_lines!==null;
  const showQuantity=(value:string|null)=>value===null?"—":formatQuantity(value);

  return <AppShell title={data.count_number} description="Count each item in this location, save your work, and send it for review.">
    <div className="count-detail-header"><div><Link href="/counts" className="back-link">← Count sessions</Link><div className="item-detail-title"><h2>{data.count_number}</h2><StatusBadge status={data.status}/></div><p>{data.location_code} — {data.location_name} · Created {formatDateTime(data.created_at)} · {data.blind_count?"Blind count":"Visible count"}</p></div><div className="row-actions"><button data-training="count-refresh" className="secondary" disabled={changed||saving} onClick={()=>void load()}>Refresh count</button>{data.posted_document_id?<Can permission="inventory.read" fallback={<span>Adjustment recorded</span>}><Link className="secondary" href={`/stock/documents/${data.posted_document_id}`}>Open stock document</Link></Can>:null}</div></div>

    <section className="count-metrics"><div><span>Completion</span><strong>{data.progress.completion_percent}%</strong><small>{data.progress.counted_lines}/{data.progress.total_lines} saved items</small></div>
      {!canSeeVariance?<div><span>Count mode</span><strong>Blind count</strong><small>{data.status==="pending_approval"?"Submitted for approval. Only authorized approvers can see expected quantities and differences.":"Recorded stock stays hidden until submission."}</small></div>:<>
        <div><span>Items with differences</span><strong>{data.progress.variance_lines}</strong><small>{formatQuantity(data.progress.absolute_variance)} total difference</small></div>
        <div><span>Estimated difference value</span><strong>{formatMoney(data.progress.estimated_value_variance)}</strong><small>Based on item cost</small></div>
        <div><span>Stock changes during count</span><strong>{data.progress.live_drift_lines}</strong><small>Ask your manager if stock moved while counting.</small></div>
        <div><span>Review limit</span><strong>{formatQuantity(data.approval_threshold)}</strong><small>Largest item difference</small></div>
      </>}
    </section>

    {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}
    {(data.progress.live_drift_lines??0)>0&&canSeeVariance&&data.status!=="posted"&&!(data.status==="open"&&data.blind_count)?<FeedbackBanner tone="warning" title="Stock changed after this count started" message="Posting is blocked if stock moved after this count started. Ask your supervisor to start a fresh count."/>:null}

    <section className="card section-gap"><div className="topline"><div><h2>{data.status==="open"?"Step 1: Count the items":"Step 2: Review the count"}</h2><p>{data.status==="open"?"Count the items in this location. Enter 0 if none are there. Save what you have counted before submitting.":"Check differences and request another count if needed."}</p></div></div>
      {data.status==="open"?<div className="count-guidance" data-testid="count-progress"><label htmlFor="current-count-progress"><strong>{enteredCount} of {data.lines.length} items entered</strong><span>{changed?"You have changes that are not saved yet.":"Your latest entries are saved."}</span></label><progress id="current-count-progress" value={enteredCount} max={Math.max(1,data.lines.length)}/>{!validDraft?<p className="field-error" role="alert">A count must be 0 or higher.</p>:null}</div>:null}
      <div className="table-wrap count-table-wrap"><table><thead><tr>{data.status==="pending_approval"?<Can permission="counts.approve"><th>Recount</th></Can>:null}<th>Item</th>{canSeeVariance?<th>Snapshot</th>:null}{canSeeVariance?<th>Live</th>:null}<th>Counted</th>{data.status!=="open"&&canSeeVariance?<th>Variance</th>:null}{canSeeVariance?<th>Changed during count</th>:null}<th>Note</th></tr></thead><tbody>{data.lines.map(line=>{const editable=data.status==="open";const row=draft[line.item_id];return <tr key={line.item_id} className={line.variance_quantity&&Number(line.variance_quantity)!==0?"variance-row":""}>{data.status==="pending_approval"?<Can permission="counts.approve"><td data-label="Recount"><input type="checkbox" aria-label={`Request recount of ${line.item_name}`} checked={recountIds.includes(line.item_id)} onChange={event=>setRecountIds(current=>event.target.checked?[...current,line.item_id]:current.filter(id=>id!==line.item_id))}/></td></Can>:null}<td data-label="Item"><Can permission="items.read" fallback={<span>{line.sku} — {line.item_name}</span>}><Link href={`/items/${line.item_id}`}>{line.sku} — {line.item_name}</Link></Can></td>{canSeeVariance?<td data-label="Starting stock">{showQuantity(line.snapshot_quantity)}</td>:null}{canSeeVariance?<td data-label="Current stock">{showQuantity(line.live_quantity)}</td>:null}<td data-label="Your count">{editable?<input className="count-input" type="number" min="0" step="0.0001" inputMode="decimal" aria-label={`Counted quantity for ${line.item_name}`} aria-invalid={row?.counted_quantity!==""&&row?.counted_quantity!==undefined&&(!Number.isFinite(Number(row.counted_quantity))||Number(row.counted_quantity)<0)} placeholder="Enter 0 if none" value={row?.counted_quantity??""} onChange={event=>setDraft(current=>({...current,[line.item_id]:{...current[line.item_id],item_id:line.item_id,counted_quantity:event.target.value}}))}/>:formatQuantity(line.counted_quantity??0)}</td>{data.status!=="open"&&canSeeVariance?<td data-label="Difference" className={Number(line.variance_quantity)<0?"negative":Number(line.variance_quantity)>0?"positive":""}>{line.variance_quantity===null?"—":`${Number(line.variance_quantity)>0?"+":""}${formatQuantity(line.variance_quantity)}`}</td>:null}{canSeeVariance?<td data-label="Stock change" className={Number(line.live_drift_quantity)!==0?"warning-text":""}>{Number(line.live_drift_quantity)>0?"+":""}{showQuantity(line.live_drift_quantity)}</td>:null}<td data-label="Note">{editable?<input className="count-note" aria-label={`Note for ${line.item_name}`} placeholder="Optional note" value={row?.note??""} onChange={event=>setDraft(current=>({...current,[line.item_id]:{...current[line.item_id],item_id:line.item_id,note:event.target.value}}))}/>:line.note||"—"}</td></tr>})}</tbody></table></div>
      {data.status==="open"?<Can permission="counts.create"><div className="count-actions">
        <button data-training="count-save" className="secondary" disabled={!changed||!validDraft||saving} onClick={()=>void save()}>{saving?"Saving…":"Save my counts"}</button>
        <Can permission="counts.submit"><button data-training="count-submit" className="primary" disabled={!canSubmit||saving} onClick={()=>setPending("submit")}>Submit saved count</button></Can>
      </div>{changed?<p className="workflow-hint" role="status">Save your entered numbers first. Submitting only uses numbers already saved.</p>:!allCounted?<p className="workflow-hint" role="status">Finish counting all {data.lines.length} items before you can submit.</p>:null}</Can>:null}
      {data.status==="pending_approval"?<Can permission="counts.approve"><div className="recount-panel"><label><span>Recount reason</span><input aria-label="Recount reason" value={recountReason} onChange={event=>setRecountReason(event.target.value)} placeholder="Explain why selected lines must be counted again"/></label><div className="count-actions"><button data-training="count-recount" className="secondary" disabled={!recountIds.length||!recountReason.trim()||saving} onClick={()=>void requestRecount()}>Request selected recount</button><button data-training="count-approve" className="primary" disabled={saving} onClick={()=>setPending("approve")}>Approve and post</button></div></div></Can>:null}
    </section>

    {data.status==="open"||data.status==="pending_approval"?<Can permission="counts.approve"><div className="danger-zone section-gap"><div><strong>Cancel count session</strong><span>Cancellation preserves the audit record and does not post any stock movement.</span></div><button data-training="count-cancel" className="secondary danger-text" onClick={()=>setPending("cancel")}>Cancel count</button></div></Can>:null}

    <ConfirmDialog open={Boolean(pending)} title={pending==="submit"?"Submit this count?":pending==="approve"?"Approve and post this count?":"Cancel this count session?"} description={pending==="submit"?"All saved quantities will be evaluated against the snapshot. Variance adjustments require independent approval when your role or the configured threshold requires review.":pending==="approve"?"The count will reconcile against live stock and create an immutable adjustment document.":"No stock movement will be posted. The session will remain available for audit."} confirmLabel={pending==="submit"?"Submit count":pending==="approve"?"Approve and post":"Cancel count"} tone={pending==="cancel"?"danger":"default"} busy={saving} onConfirm={()=>void runAction(pending)} onCancel={()=>setPending(null)}/>
  </AppShell>;
}
