"use client";

import { FormEvent, KeyboardEvent, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
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
 const searchParams=useSearchParams();
 const requestedView=searchParams.get("view");
 const[items,setItems]=useState<Item[]>([]);const[suppliers,setSuppliers]=useState<Supplier[]>([]);const[locations,setLocations]=useState<Location[]>([]);const[prs,setPrs]=useState<PR[]>([]);const[poLines,setPoLines]=useState<DraftLine[]>([blankLine()]);const[feedback,setFeedback]=useState<{tone:"success"|"error"|"info";title:string;message?:string}|null>(null);const[busy,setBusy]=useState(false);const[view,setView]=useState<"plan"|"requisitions"|"source"|"manual">("plan");
 useEffect(()=>{if(requestedView==="source"||requestedView==="manual"||requestedView==="requisitions")setView(requestedView);else setView("plan")},[requestedView]);
 const load=useCallback(async()=>{try{const[i,s,l,r]=await Promise.all([api<Item[]>("/items"),api<Supplier[]>("/suppliers"),api<Location[]>("/locations"),api<PR[]>("/requisitions")]);setItems(i);setSuppliers(s.filter(row=>row.is_active));setLocations(l.filter(row=>row.is_active));setPrs(r)}catch(error){setFeedback({tone:"error",title:"Purchasing data unavailable",message:(error as Error).message})}},[]);useEffect(()=>{void load()},[load]);
 function updateLine(index:number,key:keyof DraftLine,value:string){setPoLines(lines=>lines.map((line,i)=>i===index?{...line,[key]:value}:line))}
 function handleTabKey(event:KeyboardEvent<HTMLDivElement>){
   if(!["ArrowRight","ArrowLeft","Home","End"].includes(event.key))return;
   const buttons=Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
   const current=buttons.indexOf(document.activeElement as HTMLButtonElement);
   if(current<0||!buttons.length)return;
   event.preventDefault();
   const next=event.key==="Home"?0:event.key==="End"?buttons.length-1:
     (current+(event.key==="ArrowRight"?1:-1)+buttons.length)%buttons.length;
   buttons[next].focus();
   buttons[next].click();
 }
 async function createPO(event:FormEvent<HTMLFormElement>){event.preventDefault();if(poLines.some(row=>!row.item_id||!Number.isFinite(Number(row.quantity))||Number(row.quantity)<=0||!Number.isFinite(Number(row.price))||Number(row.price)<=0)){setFeedback({tone:"error",title:"Check every order line",message:"Choose an item and enter a quantity and price greater than zero for every line."});return}
   if(new Set(poLines.map(row=>row.item_id)).size!==poLines.length){setFeedback({tone:"error",title:"Duplicate item",message:"Use one line per item. Combine quantities before creating the purchase order."});return}
   const form=event.currentTarget;const data=new FormData(form);const lines=poLines.filter(row=>row.item_id&&Number(row.quantity)>0&&Number(row.price)>0).map(row=>({item_id:row.item_id,ordered_quantity:Number(row.quantity),unit_price:Number(row.price)}));if(!lines.length){setFeedback({tone:"error",title:"Add at least one valid purchase-order line"});return}setBusy(true);try{await api("/purchase-orders",{method:"POST",body:JSON.stringify({supplier_id:data.get("supplier_id"),requisition_id:data.get("requisition_id")||null,delivery_location_id:data.get("delivery_location_id"),expected_delivery_date:data.get("expected_delivery_date")||null,notes:data.get("notes")||null,lines})});form.reset();setPoLines([blankLine()]);setFeedback({tone:"success",title:"Purchase order created",message:"The order is in draft status and requires approval before receiving."});await load()}catch(error){setFeedback({tone:"error",title:"Purchase order could not be created",message:(error as Error).message})}finally{setBusy(false)}}
 return <AppShell title="Purchasing" description="See what needs buying, request approval, and prepare purchase orders.">
  {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}

  <section className="card purchasing-guide" aria-label="How purchasing works">
    <h2>Buy supplies step by step</h2>
    <ol className="workflow-steps" aria-label="Purchasing steps">
      <li className={view==="plan"?"active":""}>1. Find low stock</li>
      <li className={view==="requisitions"?"active":""}>2. Get approval</li>
      <li className={view==="source"?"active":""}>3. Compare &amp; order</li>
    </ol>
    <p className="workflow-hint">{view==="plan"?"Check what is running low. Select items and create a request to buy more.":
      view==="requisitions"?"An authorized manager checks requests before purchasing.":
      view==="source"?"Compare supplier offers and open purchase orders. Record arriving stock on the Receiving page.":
      "For managers only: create an order directly when no supplier quotation applies."}</p>
  </section>
  <div className="workspace-tabs" role="tablist" aria-label="Purchasing workspace" onKeyDown={handleTabKey}>
    <button id="purchase-tab-plan" aria-controls="purchase-panel-plan" type="button" role="tab" tabIndex={view==="plan"?0:-1} aria-selected={view==="plan"} className={view==="plan"?"active":""} onClick={()=>setView("plan")}>To order</button>
    <button id="purchase-tab-requisitions" aria-controls="purchase-panel-requisitions" type="button" role="tab" tabIndex={view==="requisitions"?0:-1} aria-selected={view==="requisitions"} className={view==="requisitions"?"active":""} onClick={()=>setView("requisitions")}>Requests for approval</button>
    <button id="purchase-tab-source" aria-controls="purchase-panel-source" type="button" role="tab" tabIndex={view==="source"?0:-1} aria-selected={view==="source"} className={view==="source"?"active":""} onClick={()=>setView("source")}>Quotes &amp; orders</button>
    <Can permission="procurement.*"><button id="purchase-tab-manual" aria-controls="purchase-panel-manual" type="button" role="tab" tabIndex={view==="manual"?0:-1} aria-selected={view==="manual"} className={view==="manual"?"active":""} onClick={()=>setView("manual")}>Manual order</button></Can>
  </div>
  {view==="plan"?<div id="purchase-panel-plan" role="tabpanel" aria-labelledby="purchase-tab-plan"><ProcurementPlanningPanel locations={locations} onChanged={load} view="planning"/></div>:null}
  {view==="requisitions"?<div id="purchase-panel-requisitions" role="tabpanel" aria-labelledby="purchase-tab-requisitions"><ProcurementPlanningPanel locations={locations} onChanged={load} view="requisitions"/></div>:null}
  {view==="source"?<div id="purchase-panel-source" role="tabpanel" aria-labelledby="purchase-tab-source"><QuotationPurchaseOrderWorkspace suppliers={suppliers} locations={locations} onChanged={load}/></div>:null}
  {view==="manual"?<Can permission="procurement.*"><section id="purchase-panel-manual" role="tabpanel" aria-labelledby="purchase-tab-manual" className="card"><div className="topline"><div><h2>Create a purchase order without a quotation</h2><p>Use only when your manager says no supplier quotation is needed. Check the supplier, delivery location and price before saving.</p></div></div><form onSubmit={createPO}><div className="purchasing-header-form"><label><span>Supplier</span><select name="supplier_id" aria-label="Supplier" required defaultValue=""><option value="">Select supplier</option>{suppliers.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></label><label><span>Approved request (optional)</span><select name="requisition_id" aria-label="Approved requisition" defaultValue=""><option value="">Approved requisition (optional)</option>{prs.filter(row=>row.status==="approved").map(row=><option key={row.id} value={row.id}>{row.requisition_number} — {row.department}</option>)}</select></label><label><span>Deliver to</span><select name="delivery_location_id" aria-label="Delivery location" required defaultValue=""><option value="">Delivery location</option>{locations.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></label><label><span>Expected delivery date</span><input name="expected_delivery_date" aria-label="Expected delivery date" type="date"/></label><label><span>Order notes (optional)</span><input name="notes" aria-label="Commercial or delivery notes" placeholder="Delivery instructions"/></label></div><div className="workflow-hint">Add every item to this order. Quantity and price must be greater than zero.</div><div className="po-line-editor">{poLines.map((line,index)=><div className="po-line" key={index}><select aria-label={`Purchase order line ${index+1} item`} value={line.item_id} onChange={event=>updateLine(index,"item_id",event.target.value)} required><option value="">Select item</option>{items.map(row=><option key={row.id} value={row.id}>{row.sku} — {row.name}</option>)}</select><input aria-label={`Purchase order line ${index+1} quantity`} type="number" min="0.0001" step="0.0001" placeholder="Quantity" value={line.quantity} onChange={event=>updateLine(index,"quantity",event.target.value)} required/><input aria-label={`Purchase order line ${index+1} unit price`} type="number" min="0.0001" step="0.0001" placeholder="Unit price" value={line.price} onChange={event=>updateLine(index,"price",event.target.value)} required/><button type="button" className="text-button danger-text" disabled={poLines.length===1} onClick={()=>setPoLines(lines=>lines.filter((_,i)=>i!==index))}>Remove</button></div>)}</div><div className="form-actions"><button type="button" className="secondary" onClick={()=>setPoLines(lines=>[...lines,blankLine()])}>Add line</button><button data-training="po-save" className="primary" disabled={busy}>Save draft order</button></div></form></section></Can>:null}
 </AppShell>;
}