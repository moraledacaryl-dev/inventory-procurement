"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "../../../../components/AppShell";
import { FeedbackBanner } from "../../../../components/FeedbackBanner";
import { StatusBadge } from "../../../../components/StatusBadge";
import { api } from "../../../../lib/api";
import { formatMoney, formatQuantity } from "../../../../lib/formatters";

type Material={item_id:string;planned_quantity:string;unit_cost:string;planned_cost:string;optional:boolean};
type Detail={batch:{id:string;batch_number:string;recipe_id:string;location_id:string;planned_quantity:string;actual_quantity:string|null;status:string;notes:string|null;stock_document_id:string|null;created_at:string;completed_at:string|null};recipe:{id:string;code:string;name:string;version:number;output_item_id:string;yield_quantity:string};materials:Material[];planned_total_cost:string;planned_cost_per_output_unit:string};
type Item={id:string;sku:string;name:string};

export default function Page(){
 const params=useParams<{id:string}>();
 const[detail,setDetail]=useState<Detail|null>(null);const[items,setItems]=useState<Item[]>([]);const[actuals,setActuals]=useState<Record<string,string>>({});const[actualOutput,setActualOutput]=useState("");const[waste,setWaste]=useState("0");const[notes,setNotes]=useState("");const[busy,setBusy]=useState(false);const[feedback,setFeedback]=useState<{tone:"success"|"error"|"info";title:string;message?:string}|null>(null);
 const load=useCallback(async()=>{try{const[d,i]=await Promise.all([api<Detail>(`/production-batches/${params.id}/execution-detail`),api<Item[]>("/items")]);setDetail(d);setItems(i);setActualOutput(d.batch.actual_quantity||d.batch.planned_quantity);setActuals(Object.fromEntries(d.materials.map(line=>[line.item_id,line.planned_quantity])))}catch(error){setFeedback({tone:"error",title:"Production batch unavailable",message:(error as Error).message})}},[params.id]);
 useEffect(()=>{void load()},[load]);
 const item=(id:string)=>{const row=items.find(x=>x.id===id);return row?`${row.sku} — ${row.name}`:id};
 async function run(action:()=>Promise<unknown>,title:string){setBusy(true);try{await action();setFeedback({tone:"success",title});await load()}catch(error){setFeedback({tone:"error",title:"Action could not be completed",message:(error as Error).message})}finally{setBusy(false)}}
 async function cancelBatch(){const reason=window.prompt("Why is this production batch being cancelled?");if(!reason||reason.trim().length<3)return;await run(()=>api(`/production-batches/${detail?.batch.id}/cancel`,{method:"POST",body:JSON.stringify({reason:reason.trim()})}),"Batch cancelled")}
 if(!detail)return <AppShell title="Production execution" description="Loading governed batch execution.">{feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}</AppShell>;
 const canStart=detail.batch.status==="planned";const canExecute=detail.batch.status==="in_progress";const canCancel=["planned","in_progress"].includes(detail.batch.status);
 return <AppShell title={detail.batch.batch_number} description={`${detail.recipe.code} v${detail.recipe.version} — ${detail.recipe.name}`}>
  {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}
  <div className="topline"><Link href="/production">← Back to production</Link><StatusBadge status={detail.batch.status}/></div>
  <section className="grid section-gap"><div className="card"><h2>Planned output</h2><strong>{formatQuantity(detail.batch.planned_quantity)}</strong></div><div className="card"><h2>Planned batch cost</h2><strong>{formatMoney(detail.planned_total_cost)}</strong></div><div className="card"><h2>Planned unit cost</h2><strong>{formatMoney(detail.planned_cost_per_output_unit)}</strong></div></section>
  <section className="card section-gap"><h2>Execution controls</h2><p className="section-copy">Start the batch before posting actual ingredient usage and finished output. Completion posts good output only; rejected output is recorded separately as waste evidence.</p><div className="inline-form">{canStart?<button className="primary compact" disabled={busy} onClick={()=>run(()=>api(`/production-batches/${detail.batch.id}/start`,{method:"POST"}),"Batch started")}>Start batch</button>:null}{canCancel?<button className="secondary compact" disabled={busy} onClick={cancelBatch}>Cancel batch</button>:null}{detail.batch.stock_document_id?<Link className="secondary compact" href={`/stock/documents/${detail.batch.stock_document_id}`}>Open stock document</Link>:null}</div></section>
  <section className="card section-gap"><h2>Actual material usage</h2><div className="table-wrap"><table><thead><tr><th>Ingredient</th><th>Planned</th><th>Unit cost</th><th>Planned cost</th><th>Actual used</th></tr></thead><tbody>{detail.materials.map(line=><tr key={line.item_id}><td>{item(line.item_id)}{line.optional?" (optional)":""}</td><td>{formatQuantity(line.planned_quantity)}</td><td>{formatMoney(line.unit_cost)}</td><td>{formatMoney(line.planned_cost)}</td><td><input type="number" min={line.optional?"0":"0.000001"} step="0.000001" value={actuals[line.item_id]??""} disabled={!canExecute||busy} onChange={event=>setActuals(current=>({...current,[line.item_id]:event.target.value}))}/></td></tr>)}</tbody></table></div></section>
  <section className="card section-gap"><h2>Complete production</h2><div className="inline-form"><input type="number" min="0.0001" step="0.0001" value={actualOutput} disabled={!canExecute||busy} onChange={event=>setActualOutput(event.target.value)} placeholder="Good output added to stock"/><input type="number" min="0" step="0.0001" value={waste} disabled={!canExecute||busy} onChange={event=>setWaste(event.target.value)} placeholder="Rejected / wasted output"/><input value={notes} disabled={!canExecute||busy} onChange={event=>setNotes(event.target.value)} placeholder="Execution notes"/><button className="primary compact" disabled={!canExecute||busy||Number(actualOutput)<=0} onClick={()=>run(()=>api(`/production-batches/${detail.batch.id}/execute`,{method:"POST",body:JSON.stringify({actual_output_quantity:Number(actualOutput),output_waste_quantity:Number(waste||0),notes:notes||null,materials:detail.materials.map(line=>({item_id:line.item_id,actual_quantity:Number(actuals[line.item_id])}))})}),"Production completed and stock posted")}>Complete and post</button></div></section>
 </AppShell>;
}
