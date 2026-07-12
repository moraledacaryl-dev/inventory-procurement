"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { FeedbackBanner } from "../../../components/FeedbackBanner";
import { StatusBadge } from "../../../components/StatusBadge";
import { api } from "../../../lib/api";
import { formatDateTime } from "../../../lib/formatters";

type Mapping={id:string;pos_system:string;external_product_id:string;recipe_id:string;location_id:string;is_active:boolean;recipe_status:string;healthy:boolean};
type EventRow={id:string;external_event_id:string;external_sale_id:string;pos_system:string;event_type:string;status:string;stock_document_id:string|null;reversal_of_event_id:string|null;error:string|null;processed_at:string};
type Workspace={summary:{mapping_count:number;active_mapping_count:number;inactive_mapping_count:number;stale_mapping_count:number;processed_event_count:number;failed_event_count:number};mappings:Mapping[];events:EventRow[]};

export default function Page(){
 const[data,setData]=useState<Workspace|null>(null);const[busy,setBusy]=useState(false);const[feedback,setFeedback]=useState<{tone:"success"|"error"|"info";title:string;message?:string}|null>(null);
 const load=useCallback(async()=>{try{setData(await api<Workspace>("/integrations/pos/workspace"))}catch(error){setFeedback({tone:"error",title:"POS workspace unavailable",message:(error as Error).message})}},[]);
 useEffect(()=>{void load()},[load]);
 async function toggle(row:Mapping){setBusy(true);try{await api(`/pos-mappings/${row.id}/${row.is_active?"deactivate":"activate"}`,{method:"POST"});setFeedback({tone:"success",title:`Mapping ${row.is_active?"deactivated":"activated"}`});await load()}catch(error){setFeedback({tone:"error",title:"Mapping update failed",message:(error as Error).message})}finally{setBusy(false)}}
 return <AppShell title="POS Synchronization" description="Govern product mappings, verify recipe readiness, inspect sale consumption events, and reconcile reversals.">
  {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}
  <div className="topline"><Link href="/integrations">← Back to integrations</Link></div>
  <section className="grid section-gap"><div className="card"><h2>Active mappings</h2><strong>{data?.summary.active_mapping_count??0}</strong></div><div className="card"><h2>Stale mappings</h2><strong>{data?.summary.stale_mapping_count??0}</strong></div><div className="card"><h2>Processed events</h2><strong>{data?.summary.processed_event_count??0}</strong></div><div className="card"><h2>Failed events</h2><strong>{data?.summary.failed_event_count??0}</strong></div></section>
  <section className="card section-gap"><h2>Product mappings</h2><p className="section-copy">Only active mappings linked to approved recipes should consume stock. Stale mappings require review before further POS sales.</p><div className="table-wrap"><table><thead><tr><th>POS</th><th>Product ID</th><th>Recipe</th><th>Location</th><th>Recipe status</th><th>Health</th><th>Action</th></tr></thead><tbody>{(data?.mappings||[]).map(row=><tr key={row.id}><td>{row.pos_system}</td><td>{row.external_product_id}</td><td>{row.recipe_id}</td><td>{row.location_id}</td><td><StatusBadge status={row.recipe_status}/></td><td><StatusBadge status={row.healthy?"healthy":"attention"}/></td><td><button className="secondary compact" disabled={busy} onClick={()=>toggle(row)}>{row.is_active?"Deactivate":"Activate"}</button></td></tr>)}</tbody></table></div></section>
  <section className="card section-gap"><h2>Recent POS events</h2><div className="table-wrap"><table><thead><tr><th>Processed</th><th>Event</th><th>Sale</th><th>Type</th><th>Status</th><th>Stock document</th><th>Error</th></tr></thead><tbody>{(data?.events||[]).map(row=><tr key={row.id}><td>{formatDateTime(row.processed_at)}</td><td>{row.external_event_id}</td><td>{row.external_sale_id}</td><td>{row.event_type}</td><td><StatusBadge status={row.status}/></td><td>{row.stock_document_id?<Link href={`/stock/documents/${row.stock_document_id}`}>Open</Link>:"—"}</td><td>{row.error||"—"}</td></tr>)}</tbody></table></div></section>
 </AppShell>;
}
