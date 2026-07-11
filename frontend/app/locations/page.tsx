"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
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
  const[saving,setSaving]=useState(false);
  const[error,setError]=useState("");
  const[feedback,setFeedback]=useState<{tone:"success"|"error";title:string;message?:string}|null>(null);

  const load=useCallback(async()=>{setLoading(true);setError("");try{setRows(await api<Location[]>("/locations"))}catch(exception){setError((exception as Error).message)}finally{setLoading(false)}},[]);
  useEffect(()=>{void load()},[load]);

  async function submit(event:FormEvent<HTMLFormElement>){
    event.preventDefault();
    const form=event.currentTarget;
    const data=new FormData(form);
    setSaving(true);setFeedback(null);
    try{
      await api("/locations",{method:"POST",body:JSON.stringify({code:String(data.get("code")).trim(),name:String(data.get("name")).trim(),location_type:data.get("type"),parent_id:data.get("parent_id")||null})});
      form.reset();
      setFeedback({tone:"success",title:"Location created",message:"The new location is available for stock and transfer workflows."});
      await load();
    }catch(exception){setFeedback({tone:"error",title:"Location could not be created",message:(exception as Error).message})}
    finally{setSaving(false)}
  }

  const parentName=(parentId:string|null)=>parentId?rows.find(row=>row.id===parentId)?.code||"Unknown":"Top level";

  return <AppShell title="Locations" description="Maintain the physical and operational hierarchy used by stock, receiving, transfers, counts, and production.">
    <section className="card"><h2>Add storage location</h2><form onSubmit={submit}><FormSection title="Location identity" description="Use stable codes and parent-child relationships that match actual operational control points."><FormField label="Code" name="location-code" required hint="Example: WH-A, CAFE-BAR, KITCHEN-DRY."><input name="code" required/></FormField><FormField label="Name" name="location-name" required><input name="name" required/></FormField><FormField label="Type" name="location-type" required><select name="type" defaultValue="storeroom"><option value="storeroom">Storeroom</option><option value="warehouse">Warehouse</option><option value="department">Department</option><option value="kitchen">Kitchen</option><option value="bar">Bar</option><option value="production">Production</option><option value="transit">Transit</option></select></FormField><FormField label="Parent location" name="location-parent" optional hint="Leave blank for a top-level location."><select name="parent_id" defaultValue=""><option value="">Top level</option>{rows.filter(row=>row.is_active).map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></FormField></FormSection><div className="form-actions"><button className="primary" disabled={saving}>{saving?"Creating location…":"Add location"}</button></div></form>{feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}</section>
    <section className="card section-gap"><div className="topline"><div><h2>Location hierarchy</h2><p>Open a location to review stock, policies, hierarchy, transfers, and lifecycle blockers.</p></div></div><DataTable columns={["Code","Name","Type","Parent","Status"]} rows={rows.map(row=>[<Link key={row.id} className="catalogue-link" href={`/locations/${row.id}`}>{row.code}</Link>,<Link key={`${row.id}-name`} className="catalogue-link" href={`/locations/${row.id}`}>{row.name}</Link>,row.location_type,parentName(row.parent_id),<StatusBadge key={`${row.id}-status`} status={row.is_active?"active":"inactive"}/>])} rowIds={rows.map(row=>row.id)} loading={loading} error={error} onRetry={()=>void load()} searchPlaceholder="Search code, name, type, parent, or status" exportFileName="hidden-oasis-locations" caption="Hidden Oasis location hierarchy" emptyTitle="No locations yet" emptyMessage="Create the first operational location."/></section>
  </AppShell>;
}
