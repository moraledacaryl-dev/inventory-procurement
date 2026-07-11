"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { DataTable } from "../../components/DataTable";
import { API, api } from "../../lib/api";

type Audit={id:string;action:string;entity_type:string;entity_id:string|null;created_at:string};
type Note={id:string;title:string;message:string;severity:string;is_read:boolean;created_at:string};
type SupplierPerformance={supplier_id:string;supplier_code:string;supplier_name:string;purchase_orders:number;completed_orders:number;ordered_value:string;received_value:string;accepted_value:string;rejected_value:string;acceptance_rate:string;on_time_rate:string;average_delivery_variance_days:string};

export default function Page(){
  const[audit,setAudit]=useState<Audit[]>([]);
  const[notes,setNotes]=useState<Note[]>([]);
  const[suppliers,setSuppliers]=useState<SupplierPerformance[]>([]);
  const[msg,setMsg]=useState("");

  const load=useCallback(async()=>{
    try{
      const[a,n,s]=await Promise.all([api<Audit[]>("/audit-logs?limit=50"),api<Note[]>("/notifications"),api<SupplierPerformance[]>("/supplier-performance")]);
      setAudit(a);setNotes(n);setSuppliers(s);
    }catch(error){setMsg((error as Error).message)}
  },[]);
  useEffect(()=>{void load()},[load]);

  function download(path:string){
    fetch(`${API}${path}`,{credentials:"include",headers:{"X-Requested-With":"HiddenOasisInventory"}}).then(async response=>{
      if(response.status===401){window.location.assign(`/login?expired=1&next=${encodeURIComponent(window.location.pathname)}`);return}
      if(!response.ok)throw new Error("Export failed");
      const blob=await response.blob(),url=URL.createObjectURL(blob),anchor=document.createElement("a");
      anchor.href=url;anchor.download=path.includes("balances")?"stock-balances.csv":"items.csv";anchor.click();URL.revokeObjectURL(url);
    }).catch(error=>setMsg(error.message));
  }

  return <AppShell title="Reports & Activity">
    <section className="grid"><div className="card"><h2>Exports</h2><p>Download operational data for review and controlled migration.</p><div className="button-row"><button className="secondary" onClick={()=>download("/exports/items.csv")}>Export items</button><button className="secondary" onClick={()=>download("/exports/balances.csv")}>Export balances</button></div></div><div className="card"><h2>Notifications</h2><p>{notes.filter(x=>!x.is_read).length} unread operational alerts.</p></div><div className="card"><h2>Audit trail</h2><p>{audit.length} recent recorded actions displayed.</p></div></section>
    <section className="card section-gap"><h2>Supplier performance</h2><p>Acceptance and delivery timing are calculated from actual purchase orders and goods receipts.</p><DataTable columns={["Supplier","POs","Completed","Ordered value","Received value","Acceptance %","On-time %","Avg. delivery variance"]} rows={suppliers.map(x=>[`${x.supplier_code} — ${x.supplier_name}`,x.purchase_orders,x.completed_orders,Number(x.ordered_value).toFixed(2),Number(x.received_value).toFixed(2),`${x.acceptance_rate}%`,`${x.on_time_rate}%`,`${x.average_delivery_variance_days} days`])}/></section>
    <section className="card section-gap"><h2>Notifications</h2><DataTable columns={["Date","Severity","Title","Message","State"]} rows={notes.map(x=>[new Date(x.created_at).toLocaleString(),x.severity,x.title,x.message,x.is_read?"Read":"Unread"])}/></section>
    <section className="card section-gap"><h2>Recent audit activity</h2><DataTable columns={["Date","Action","Entity","ID"]} rows={audit.map(x=>[new Date(x.created_at).toLocaleString(),x.action,x.entity_type,x.entity_id||""])}/></section>
    {msg&&<p className="status">{msg}</p>}
  </AppShell>
}
