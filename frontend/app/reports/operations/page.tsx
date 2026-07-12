"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { DataTable } from "../../../components/DataTable";
import { FeedbackBanner } from "../../../components/FeedbackBanner";
import { api } from "../../../lib/api";

type Workspace={id:string;name:string};
type Summary={workspace_id:string|null;stock_units:string;stock_value:string;reusable_units:string;gross_asset_cost:string;accumulated_depreciation:string;impairment_loss:string;net_fixed_assets:string;overdue_maintenance:number;open_work_orders:number;unclassified_items:number};
type SavedView={id:string;name:string;filters:Record<string,string>;is_default:boolean};

export default function Page(){
 const[workspaces,setWorkspaces]=useState<Workspace[]>([]),[workspace,setWorkspace]=useState(""),[summary,setSummary]=useState<Summary|null>(null),[views,setViews]=useState<SavedView[]>([]),[feedback,setFeedback]=useState<{tone:"success"|"error"|"info";title:string;message?:string}|null>(null);
 const load=useCallback(async(id=workspace)=>{try{const[w,s,v]=await Promise.all([api<Workspace[]>("/classification/dimensions?dimension_type=workspace&active=true"),api<Summary>(`/reports/operating-summary${id?`?workspace_id=${id}`:""}`),api<SavedView[]>("/saved-views?module_key=operating-summary")]);setWorkspaces(w);setSummary(s);setViews(v)}catch(e){setFeedback({tone:"error",title:"Operating report unavailable",message:(e as Error).message})}},[workspace]);
 useEffect(()=>{void load("")},[load]);
 async function saveView(e:FormEvent<HTMLFormElement>){e.preventDefault();const f=e.currentTarget,d=new FormData(f);try{await api("/saved-views",{method:"POST",body:JSON.stringify({module_key:"operating-summary",name:d.get("name"),filters:{workspace_id:workspace},columns:["stock_value","reusable_units","net_fixed_assets","overdue_maintenance"],is_default:Boolean(d.get("default"))})});setFeedback({tone:"success",title:"View saved"});f.reset();await load()}catch(e){setFeedback({tone:"error",title:"View could not be saved",message:(e as Error).message})}}
 const money=(value:string)=>`₱${Number(value||0).toLocaleString()}`;
 return <AppShell title="Operating Summary" description="Consolidated Hotel, F&B, shared-stock, reusable-property, asset, and maintenance reporting.">
  {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}
  <section className="card"><div className="toolbar"><label>Workspace<select value={workspace} onChange={e=>{setWorkspace(e.target.value);void load(e.target.value)}}><option value="">All Operations</option>{workspaces.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></label><form className="inline-form" onSubmit={saveView}><input name="name" placeholder="Saved view name" required/><label><input name="default" type="checkbox"/> Default</label><button className="secondary compact">Save view</button></form></div></section>
  {summary?<><section className="grid section-gap"><div className="card"><h2>Stock value</h2><strong>{money(summary.stock_value)}</strong><p>{Number(summary.stock_units).toLocaleString()} units</p></div><div className="card"><h2>Reusable property</h2><strong>{Number(summary.reusable_units).toLocaleString()}</strong><p>units in circulation</p></div><div className="card"><h2>Net fixed assets</h2><strong>{money(summary.net_fixed_assets)}</strong><p>{money(summary.accumulated_depreciation)} accumulated depreciation</p></div><div className="card"><h2>Operational exceptions</h2><strong>{summary.overdue_maintenance+summary.open_work_orders+summary.unclassified_items}</strong><p>{summary.overdue_maintenance} overdue maintenance · {summary.open_work_orders} open work orders · {summary.unclassified_items} unclassified items</p></div></section>
  <section className="card section-gap"><h2>Consolidated values</h2><DataTable columns={["Metric","Value"]} rows={[["Gross asset cost",money(summary.gross_asset_cost)],["Accumulated depreciation",money(summary.accumulated_depreciation)],["Impairment loss",money(summary.impairment_loss)],["Net fixed assets",money(summary.net_fixed_assets)],["Stock value",money(summary.stock_value)]]} rowIds={["gross","depreciation","impairment","net","stock"]} searchPlaceholder="Search metrics" exportFileName="hidden-oasis-operating-summary" emptyTitle="No operating values" emptyMessage="No records are available for this scope."/></section></>:null}
  <section className="card section-gap"><h2>Saved views</h2><DataTable columns={["Name","Scope","Default"]} rows={views.map(x=>[x.name,x.filters?.workspace_id||"All Operations",x.is_default?"Yes":"No"])} rowIds={views.map(x=>x.id)} searchPlaceholder="Search saved views" exportFileName="hidden-oasis-saved-views" emptyTitle="No saved views" emptyMessage="Save a reporting scope for quick reuse."/></section>
 </AppShell>
}
