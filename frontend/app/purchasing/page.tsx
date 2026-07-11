"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Can } from "../../components/SessionContext";
import { FeedbackBanner } from "../../components/FeedbackBanner";
import { ProcurementPlanningPanel } from "../../components/ProcurementPlanningPanel";
import { QuotationPurchaseOrderWorkspace } from "../../components/QuotationPurchaseOrderWorkspace";
import { api } from "../../lib/api";

type Item={id:string;sku:string;name:string};
type Supplier={id:string;code:string;name:string;is_active:boolean};
type Location={id:string;code:string;name:string;is_active:boolean};
type PR={id:string;requisition_number:string;department:string;status:string;lines:{item_id:string;quantity:string;estimated_unit_cost:string}[]};
type DraftLine={item_id:string;quantity:string;price:string};
const blankLine=():DraftLine=>({item_id:"",quantity:"",price:""});

export default function PurchasingPage(){
 const[items,setItems]=useState<Item[]>([]);const[suppliers,setSuppliers]=useState<Supplier[]>([]);const[locations,setLocations]=useState<Location[]>([]);const[prs,setPrs]=useState<PR[]>([]);const[poLines,setPoLines]=useState<DraftLine[]>([blankLine()]);const[feedback,setFeedback]=useState<{tone:"success"|"error"|"info";title:string;message?:string}|null>(null);const[busy,setBusy]=useState(false);
 const load=useCallback(async()=>{try{const[i,s,l,r]=await Promise.all([api<Item[]>("/items"),api<Supplier[]>("/suppliers"),api<Location[]>("/locations"),api<PR[]>("/requisitions")]);setItems(i);setSuppliers(s.filter(row=>row.is_active));setLocations(l.filter(row=>row.is_active));setPrs(r)}catch(error){setFeedback({tone:"error",title:"Purchasing data unavailable",message:(error as Error).message})}},[]);useEffect(()=>{void load()},[load]);
 function updateLine(index:number,key:keyof DraftLine,value:string){setPoLines(lines=>lines.map((line,i)=>i===index?{...line,[key]:value}:line))}
 async function createPO(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget;const data=new FormData(form);const lines=poLines.filter(row=>row.item_id&&Number(row.quantity)>0&&Number(row.price)>0).map(row=>({item_id:row.item_id,ordered_quantity:Number(row.quantity),unit_price:Number(row.price)}));if(!lines.length){setFeedback({tone:"error",title:"Add at least one valid purchase-order line"});return}setBusy(true);try{await api("/purchase-orders",{method:"POST",body:JSON.stringify({supplier_id:data.get("supplier_id"),requisition_id:data.get("requisition_id")||null,delivery_location_id:data.get("delivery_location_id"),expected_delivery_date:data.get("expected_delivery_date")||null,notes:data.get("notes")||null,lines})});form.reset();setPoLines([blankLine()]);setFeedback({tone:"success",title:"Purchase order created",message:"The order is in draft status and requires approval before receiving."});await load()}catch(error){setFeedback({tone:"error",title:"Purchase order could not be created",message:(error as Error).message})}finally{setBusy(false)}}
 return <AppShell title="Purchasing" description="Plan replenishment, approve demand, compare supplier quotations, award sourcing decisions, and control purchase orders.">
  {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}
  <ProcurementPlanningPanel locations={locations} onChanged={load}/>
  <QuotationPurchaseOrderWorkspace suppliers={suppliers} locations={locations} onChanged={load}/>
  <Can permission="procurement.*"><section className="card section-gap"><div className="topline"><div><h2>Manual purchase order</h2><p>Use this only when no quotation award applies. Approved requisitions remain required when linked.</p></div></div><form onSubmit={createPO}><div className="purchasing-header-form"><select name="supplier_id" required defaultValue=""><option value="">Select supplier</option>{suppliers.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select><select name="requisition_id" defaultValue=""><option value="">Approved requisition (optional)</option>{prs.filter(row=>row.status==="approved").map(row=><option key={row.id} value={row.id}>{row.requisition_number} — {row.department}</option>)}</select><select name="delivery_location_id" required defaultValue=""><option value="">Delivery location</option>{locations.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select><input name="expected_delivery_date" type="date"/><input name="notes" placeholder="Commercial or delivery notes"/></div><div className="po-line-editor">{poLines.map((line,index)=><div className="po-line" key={index}><select value={line.item_id} onChange={event=>updateLine(index,"item_id",event.target.value)} required><option value="">Select item</option>{items.map(row=><option key={row.id} value={row.id}>{row.sku} — {row.name}</option>)}</select><input type="number" min="0.0001" step="0.0001" placeholder="Quantity" value={line.quantity} onChange={event=>updateLine(index,"quantity",event.target.value)} required/><input type="number" min="0.0001" step="0.0001" placeholder="Unit price" value={line.price} onChange={event=>updateLine(index,"price",event.target.value)} required/><button type="button" className="text-button danger-text" disabled={poLines.length===1} onClick={()=>setPoLines(lines=>lines.filter((_,i)=>i!==index))}>Remove</button></div>)}</div><div className="form-actions"><button type="button" className="secondary" onClick={()=>setPoLines(lines=>[...lines,blankLine()])}>Add line</button><button className="primary" disabled={busy}>Create draft PO</button></div></form></section></Can>
 </AppShell>;
}
