"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { DataTable } from "../../components/DataTable";
import { api } from "../../lib/api";

type POLine={id:string;item_id:string;ordered_quantity:string;received_quantity:string;unit_price:string};
type PO={id:string;purchase_order_number:string;status:string;lines:POLine[]};
type GR={id:string;goods_receipt_number:string;purchase_order_id:string;delivery_reference:string|null;received_at:string;lines:{accepted_quantity:string;rejected_quantity:string}[]};
type Entry={line_id:string;received:string;rejected:string};

export default function Page(){
  const[pos,setPos]=useState<PO[]>([]);
  const[receipts,setReceipts]=useState<GR[]>([]);
  const[selectedPoId,setSelectedPoId]=useState("");
  const[entries,setEntries]=useState<Entry[]>([]);
  const[msg,setMsg]=useState("");

  const load=useCallback(async()=>{
    try{
      const[p,g]=await Promise.all([api<PO[]>("/purchase-orders"),api<GR[]>("/goods-receipts")]);
      setPos(p);setReceipts(g);
    }catch(error){setMsg((error as Error).message)}
  },[]);

  useEffect(()=>{void load()},[load]);
  const selectedPo=useMemo(()=>pos.find(x=>x.id===selectedPoId),[pos,selectedPoId]);

  useEffect(()=>{
    if(!selectedPo){setEntries([]);return}
    setEntries(selectedPo.lines.filter(line=>Number(line.received_quantity)<Number(line.ordered_quantity)).map(line=>({line_id:line.id,received:"",rejected:"0"})));
  },[selectedPo]);

  const updateEntry=(lineId:string,key:"received"|"rejected",value:string)=>setEntries(rows=>rows.map(row=>row.line_id===lineId?{...row,[key]:value}:row));

  async function receive(event:FormEvent<HTMLFormElement>){
    event.preventDefault();const form=event.currentTarget;const values=new FormData(form);
    if(!selectedPo)return;
    const lines=entries.filter(entry=>Number(entry.received)>0).map(entry=>{
      const received=Number(entry.received),rejected=Number(entry.rejected||0);
      return {purchase_order_line_id:entry.line_id,received_quantity:String(received),accepted_quantity:String(received-rejected),rejected_quantity:String(rejected)};
    });
    if(!lines.length){setMsg("Enter a received quantity for at least one line.");return}
    if(lines.some(line=>Number(line.accepted_quantity)<0)){setMsg("Rejected quantity cannot exceed received quantity.");return}
    try{
      await api(`/purchase-orders/${selectedPo.id}/receipts`,{method:"POST",body:JSON.stringify({delivery_reference:values.get("reference")||null,notes:values.get("notes")||null,idempotency_key:values.get("idempotency_key")||null,lines})});
      form.reset();setSelectedPoId("");setMsg("Goods receipt posted.");await load();
    }catch(error){setMsg((error as Error).message)}
  }

  return <AppShell title="Receiving">
    <section className="card"><h2>Receive purchase order</h2><form onSubmit={receive}><div className="inline-form"><select name="po" required value={selectedPoId} onChange={e=>setSelectedPoId(e.target.value)}><option value="">Approved/open PO</option>{pos.filter(x=>["approved","partially_received"].includes(x.status)).map(x=><option key={x.id} value={x.id}>{x.purchase_order_number} — {x.status}</option>)}</select><input name="reference" placeholder="Delivery reference"/><input name="idempotency_key" placeholder="Unique receipt key (optional)"/><input name="notes" placeholder="Receiving notes"/></div>{selectedPo&&<div className="table-wrap"><table><thead><tr><th>Item</th><th>Ordered</th><th>Previously received</th><th>Outstanding</th><th>Received now</th><th>Rejected now</th><th>Accepted now</th></tr></thead><tbody>{selectedPo.lines.map(line=>{const entry=entries.find(x=>x.line_id===line.id);const outstanding=Number(line.ordered_quantity)-Number(line.received_quantity);const accepted=Math.max(0,Number(entry?.received||0)-Number(entry?.rejected||0));return <tr key={line.id}><td>{line.item_id}</td><td>{line.ordered_quantity}</td><td>{line.received_quantity}</td><td>{outstanding}</td><td><input value={entry?.received||""} disabled={!entry} onChange={e=>updateEntry(line.id,"received",e.target.value)} type="number" step="0.0001" min="0" max={outstanding}/></td><td><input value={entry?.rejected||"0"} disabled={!entry} onChange={e=>updateEntry(line.id,"rejected",e.target.value)} type="number" step="0.0001" min="0" max={entry?.received||0}/></td><td>{accepted}</td></tr>})}</tbody></table></div>}<button className="primary compact" disabled={!selectedPo}>Post multi-line receipt</button></form>{msg&&<p className="status">{msg}</p>}</section>
    <section className="card section-gap"><h2>Goods receipts</h2><DataTable columns={["GRN","PO","Delivery ref","Accepted","Rejected","Received at"]} rows={receipts.map(x=>[x.goods_receipt_number,pos.find(p=>p.id===x.purchase_order_id)?.purchase_order_number||x.purchase_order_id,x.delivery_reference||"",x.lines.reduce((s,l)=>s+Number(l.accepted_quantity),0),x.lines.reduce((s,l)=>s+Number(l.rejected_quantity),0),new Date(x.received_at).toLocaleString()])}/></section>
  </AppShell>
}
