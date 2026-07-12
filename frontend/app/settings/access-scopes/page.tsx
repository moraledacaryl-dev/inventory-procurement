"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { Can } from "../../../components/SessionContext";
import { DataTable } from "../../../components/DataTable";
import { FeedbackBanner } from "../../../components/FeedbackBanner";
import { api } from "../../../lib/api";

type User={id:string;email:string;full_name:string;role:string};
type Dimension={id:string;name:string;dimension_type:string};
type Location={id:string;name:string};
type Scope={id:string;user_id:string;workspace_id:string|null;department_id:string|null;location_id:string|null;record_class_id:string|null;approval_limit:string;is_active:boolean};

export default function Page(){
 const[users,setUsers]=useState<User[]>([]),[scopes,setScopes]=useState<Scope[]>([]),[workspaces,setWorkspaces]=useState<Dimension[]>([]),[departments,setDepartments]=useState<Dimension[]>([]),[classes,setClasses]=useState<Dimension[]>([]),[locations,setLocations]=useState<Location[]>([]),[feedback,setFeedback]=useState<{tone:"success"|"error"|"info";title:string;message?:string}|null>(null),[busy,setBusy]=useState(false);
 const load=useCallback(async()=>{try{const[u,s,w,d,c,l]=await Promise.all([api<User[]>("/access-scope-users"),api<Scope[]>("/access-scopes"),api<Dimension[]>("/classification/dimensions?dimension_type=workspace&active=true"),api<Dimension[]>("/classification/dimensions?dimension_type=department&active=true"),api<Dimension[]>("/classification/dimensions?dimension_type=record_class&active=true"),api<Location[]>("/locations")]);setUsers(u);setScopes(s);setWorkspaces(w);setDepartments(d);setClasses(c);setLocations(l)}catch(e){setFeedback({tone:"error",title:"Access scopes unavailable",message:(e as Error).message})}},[]);useEffect(()=>{void load()},[load]);
 const userName=(id:string)=>users.find(x=>x.id===id)?.full_name||id,dim=(rows:Dimension[],id:string|null)=>rows.find(x=>x.id===id)?.name||"All",loc=(id:string|null)=>locations.find(x=>x.id===id)?.name||"All";
 async function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();const f=e.currentTarget,d=new FormData(f);setBusy(true);try{await api("/access-scopes",{method:"POST",body:JSON.stringify({user_id:d.get("user"),workspace_id:d.get("workspace")||null,department_id:d.get("department")||null,location_id:d.get("location")||null,record_class_id:d.get("record_class")||null,approval_limit:Number(d.get("approval_limit")||0),is_active:true})});setFeedback({tone:"success",title:"Operational scope added"});f.reset();await load()}catch(e){setFeedback({tone:"error",title:"Scope could not be added",message:(e as Error).message})}finally{setBusy(false)}}
 return <AppShell title="Operational Access" description="Limit users by workspace, department, location, record class, and approval authority without hardcoded role names.">
  {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}
  <Can permission="users.*"><section className="card"><h2>Add operational scope</h2><form className="inline-form" onSubmit={submit}><select name="user" required><option value="">User</option>{users.map(x=><option key={x.id} value={x.id}>{x.full_name} — {x.role}</option>)}</select><select name="workspace"><option value="">All workspaces</option>{workspaces.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><select name="department"><option value="">All departments</option>{departments.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><select name="location"><option value="">All locations</option>{locations.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><select name="record_class"><option value="">All record classes</option>{classes.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select><input name="approval_limit" type="number" min="0" step="0.01" placeholder="Approval limit"/><button className="primary compact" disabled={busy}>Add scope</button></form></section></Can>
  <section className="card section-gap"><h2>Configured scopes</h2><DataTable columns={["User","Workspace","Department","Location","Record class","Approval limit","Active"]} rows={scopes.map(x=>[userName(x.user_id),dim(workspaces,x.workspace_id),dim(departments,x.department_id),loc(x.location_id),dim(classes,x.record_class_id),`₱${Number(x.approval_limit).toLocaleString()}`,x.is_active?"Yes":"No"])} rowIds={scopes.map(x=>x.id)} searchPlaceholder="Search operational scopes" exportFileName="hidden-oasis-access-scopes" emptyTitle="No operational scopes" emptyMessage="Owners retain global access; configure scopes for other active users."/></section>
 </AppShell>
}
