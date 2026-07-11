"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { DataTable } from "../../components/DataTable";
import { FeedbackBanner } from "../../components/FeedbackBanner";
import { FormField, FormSection } from "../../components/FormField";
import { StatusBadge } from "../../components/StatusBadge";
import { api } from "../../lib/api";

type Location={id:string;code:string;name:string;location_type:string;parent_id:string|null;is_active:boolean};

export default function Page(){
  const[rows,setRows]=useState<Location[]>([]);
  const[loading,setLoading]=useState(true);
  const[loadError,setLoadError]=useState("");
  const[saving,setSaving]=useState(false);
  const[feedback,setFeedback]=useState<{tone:"success"|"error";title:string;message?:string}|null>(null);
  const[showInactive,setShowInactive]=useState(false);

  const load=useCallback(async()=>{setLoading(true);setLoadError("");try{setRows(await api<Location[]>("/locations"))}catch(error){setLoadError((error as Error).message)}finally{setLoading(false)}},[]);
  useEffect(()=>{void load()},[load]);

  const visibleRows=useMemo(()=>showInactive?rows:rows.filter(row=>row.is_active),[rows,showInactive]);
  const parentLabel=(id:string|null)=>id?rows.find(row=>row.id===id)?.code||"Unknown":"Top level";

  async function submit(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setSaving(true);setFeedback(null);const form=event.currentTarget;const data=new FormData(form);
    try{
      await api("/locations",{method:"POST",body:JSON.stringify({code:data.get("code"),name:data.get("name"),location_type:data.get("type"),parent_id:data.get("parent_id")||null})});
      form.reset();setFeedback({tone:"success",title:"Location created",message:"The location is now available for stock and operational configuration."});await load();
    }catch(error){setFeedback({tone:"error",title:"Location could not be created",message:(error as Error).message})}
    finally{setSaving(false)}
  }

  return <AppShell title="Locations" description="Maintain the physical hierarchy used by stock, receiving, transfers, counts, and production.">
    <section className="card"><div className="topline"><div><h2>Add storage location</h2><p>Create top-level sites, warehouses, storerooms, departments, or nested storage areas.</p></div></div>
      <form onSubmit={submit}><FormSection title="Location identity"><FormField label="Code" name="location-code" required hint="Stable short code, such as WH-A or CAFE-BAR."><input name="code" required autoComplete="off"/></FormField><FormField label="Location name" name="location-name" required><input name="name" required/></FormField><FormField label="Location type" name="location-type" required><select name="type" defaultValue="storeroom"><option value="site">Site</option><option value="warehouse">Warehouse</option><option value="storeroom">Storeroom</option><option value="department">Department</option><option value="production">Production area</option><option value="transit">Transit area</option></select></FormField><FormField label="Parent location" name="location-parent" optional hint="Leave blank for a top-level location."><select name="parent_id" defaultValue=""><option value="">Top level</option>{rows.filter(row=>row.is_active).map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></FormField></FormSection><div className="form-actions"><button className="primary" disabled={saving}>{saving?"Creating location…":"Create location"}</button></div></form>
      {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}
    </section>

    <section className="card section-gap"><div className="topline"><div><h2>Location master</h2><p>Open a location to review hierarchy, stock exposure, policies, transfers, and lifecycle controls.</p></div><label className="catalogue-toggle"><input type="checkbox" checked={showInactive} onChange={event=>setShowInactive(event.target.checked)}/><span>Include inactive</span></label></div>
      <DataTable columns={["Code","Name","Type","Parent","Status"]} rows={visibleRows.map(row=>[<Link className="catalogue-link" href={`/locations/${row.id}`} key={row.id}>{row.code}</Link>,<Link className="catalogue-link" href={`/locations/${row.id}`} key={`${row.id}-name`}>{row.name}</Link>,row.location_type,parentLabel(row.parent_id),<StatusBadge key={`${row.id}-status`} status={row.is_active?"active":"inactive"}/>])} rowIds={visibleRows.map(row=>row.id)} loading={loading} error={loadError} onRetry={()=>void load()} searchPlaceholder="Search code, name, type, parent, or status" exportFileName="hidden-oasis-locations" caption="Hidden Oasis location master" emptyTitle="No locations found" emptyMessage="Create the first operational location or include inactive records."/>
    </section>
  </AppShell>
}
