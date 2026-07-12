"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { FeedbackBanner } from "../../../components/FeedbackBanner";
import { StatusBadge } from "../../../components/StatusBadge";
import { api } from "../../../lib/api";

type Identity={canonical_user_id:string;employee_identity_key:string;email:string;full_name:string;role:string;is_active:boolean};
type MasterRow={canonical_id:string;code:string;name:string;is_active:boolean};
type Workspace={summary:{identity_count:number;active_identity_count:number;item_count:number;active_item_count:number;location_count:number;active_location_count:number;supplier_count:number;active_supplier_count:number};identities:Identity[];items:MasterRow[];locations:MasterRow[];suppliers:MasterRow[]};

export default function Page(){
 const[data,setData]=useState<Workspace|null>(null);const[busy,setBusy]=useState(false);const[feedback,setFeedback]=useState<{tone:"success"|"error"|"info";title:string;message?:string}|null>(null);
 const load=useCallback(async()=>{try{setData(await api<Workspace>("/master-data/workspace"))}catch(error){setFeedback({tone:"error",title:"Master data workspace unavailable",message:(error as Error).message})}},[]);
 useEffect(()=>{void load()},[load]);
 async function publish(){setBusy(true);try{const result=await api<{published:{destination:string}[]}>("/master-data/publish",{method:"POST",body:JSON.stringify({destinations:["staff","command-center","accounting"]})});setFeedback({tone:"success",title:"Master data snapshot queued",message:`Published to ${result.published.map(row=>row.destination).join(", ")}.`})}catch(error){setFeedback({tone:"error",title:"Publishing failed",message:(error as Error).message})}finally{setBusy(false)}}
 const table=(title:string,rows:MasterRow[])=><section className="card section-gap"><h2>{title}</h2><div className="table-wrap"><table><thead><tr><th>Canonical ID</th><th>Code</th><th>Name</th><th>Status</th></tr></thead><tbody>{rows.map(row=><tr key={row.canonical_id}><td>{row.canonical_id}</td><td>{row.code}</td><td>{row.name}</td><td><StatusBadge status={row.is_active?"active":"inactive"}/></td></tr>)}</tbody></table></div></section>;
 return <AppShell title="Shared Identity & Master Data" description="Canonical identities, items, locations, and suppliers used across Inventory, Staff, Command Center, and Accounting.">
  {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}
  <div className="topline"><Link href="/integrations">← Back to integrations</Link><button className="primary compact" disabled={busy} onClick={publish}>Publish snapshot</button></div>
  <section className="grid section-gap"><div className="card"><h2>Identities</h2><strong>{data?.summary.active_identity_count??0}</strong></div><div className="card"><h2>Items</h2><strong>{data?.summary.active_item_count??0}</strong></div><div className="card"><h2>Locations</h2><strong>{data?.summary.active_location_count??0}</strong></div><div className="card"><h2>Suppliers</h2><strong>{data?.summary.active_supplier_count??0}</strong></div></section>
  <section className="card section-gap"><h2>Operational identities</h2><p className="section-copy">The canonical user ID is the cross-system identity. Payroll and HR records remain outside Inventory; only operational identity, role, and active status are exposed here.</p><div className="table-wrap"><table><thead><tr><th>Canonical ID</th><th>Identity key</th><th>Name</th><th>Role</th><th>Status</th></tr></thead><tbody>{(data?.identities||[]).map(row=><tr key={row.canonical_user_id}><td>{row.canonical_user_id}</td><td>{row.employee_identity_key}</td><td>{row.full_name}</td><td>{row.role}</td><td><StatusBadge status={row.is_active?"active":"inactive"}/></td></tr>)}</tbody></table></div></section>
  {table("Items",data?.items||[])}
  {table("Locations",data?.locations||[])}
  {table("Suppliers",data?.suppliers||[])}
 </AppShell>;
}
