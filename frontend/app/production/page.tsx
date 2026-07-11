"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Can } from "../../components/SessionContext";
import { DataTable } from "../../components/DataTable";
import { FeedbackBanner } from "../../components/FeedbackBanner";
import { StatusBadge } from "../../components/StatusBadge";
import { api } from "../../lib/api";
import { formatQuantity } from "../../lib/formatters";

type Item={id:string;sku:string;name:string};
type Location={id:string;code:string;name:string};
type Recipe={id:string;code:string;name:string;output_item_id:string;yield_quantity:string;version:number;status:string;lines:{ingredient_item_id:string;quantity:string;waste_factor:string}[]};
type Batch={id:string;batch_number:string;recipe_id:string;location_id:string;planned_quantity:string;actual_quantity:string|null;status:string;stock_document_id:string|null};
type Mapping={id:string;pos_system:string;external_product_id:string;recipe_id:string;location_id:string};
type Recon={pending_events:number;failed_events:number;dead_letter_events:number;unprocessed_pos_events:number;latest_pos_event_at:string|null};
type DraftLine={ingredient_item_id:string;quantity:string;waste_factor:string;optional:boolean};
const blank=():DraftLine=>({ingredient_item_id:"",quantity:"",waste_factor:"0",optional:false});

export default function Page(){
 const[items,setItems]=useState<Item[]>([]);const[locations,setLocations]=useState<Location[]>([]);const[recipes,setRecipes]=useState<Recipe[]>([]);const[batches,setBatches]=useState<Batch[]>([]);const[mappings,setMappings]=useState<Mapping[]>([]);const[recon,setRecon]=useState<Recon|null>(null);const[lines,setLines]=useState<DraftLine[]>([blank()]);const[feedback,setFeedback]=useState<{tone:"success"|"error"|"info";title:string;message?:string}|null>(null);const[busy,setBusy]=useState(false);
 const load=useCallback(async()=>{try{const[i,l,r,b,m,x]=await Promise.all([api<Item[]>("/items"),api<Location[]>("/locations"),api<Recipe[]>("/recipes"),api<Batch[]>("/production-batches"),api<Mapping[]>("/pos-mappings"),api<Recon>("/integrations/reconciliation")]);setItems(i);setLocations(l);setRecipes(r);setBatches(b);setMappings(m);setRecon(x)}catch(error){setFeedback({tone:"error",title:"Production workspace unavailable",message:(error as Error).message})}},[]);useEffect(()=>{void load()},[load]);
 const item=(id:string)=>items.find(x=>x.id===id)?.sku||id;const loc=(id:string)=>locations.find(x=>x.id===id)?.code||id;const recipe=(id:string)=>recipes.find(x=>x.id===id)?.code||id;
 const updateLine=(index:number,key:keyof DraftLine,value:string|boolean)=>setLines(rows=>rows.map((row,i)=>i===index?{...row,[key]:value}:row));
 async function run(action:()=>Promise<unknown>,title:string){setBusy(true);try{await action();setFeedback({tone:"success",title});await load()}catch(error){setFeedback({tone:"error",title:"Action could not be completed",message:(error as Error).message})}finally{setBusy(false)}}
 async function createRecipe(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget,d=new FormData(form);const valid=lines.filter(x=>x.ingredient_item_id&&Number(x.quantity)>0);await run(()=>api("/recipes",{method:"POST",body:JSON.stringify({code:d.get("code"),name:d.get("name"),output_item_id:d.get("output_item"),yield_quantity:Number(d.get("yield")),notes:d.get("notes")||null,lines:valid.map(line=>({...line,quantity:Number(line.quantity),waste_factor:Number(line.waste_factor)}))})}),"Recipe created as draft");form.reset();setLines([blank()])}
 async function createBatch(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget,d=new FormData(form);await run(()=>api("/production-batches",{method:"POST",body:JSON.stringify({recipe_id:d.get("recipe"),location_id:d.get("location"),planned_quantity:Number(d.get("quantity")),notes:d.get("notes")||null})}),"Production batch planned");form.reset()}
 async function completeBatch(id:string,planned:string){const actual=window.prompt("Actual output quantity",planned);if(!actual)return;await run(()=>api(`/production-batches/${id}/complete`,{method:"POST",body:JSON.stringify({actual_quantity:Number(actual)})}),"Production batch completed")}
 async function createMapping(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget,d=new FormData(form);await run(()=>api("/pos-mappings",{method:"POST",body:JSON.stringify({pos_system:d.get("pos_system"),external_product_id:d.get("external_product_id"),recipe_id:d.get("recipe"),location_id:d.get("location")})}),"POS product mapped");form.reset()}
 return <AppShell title="Recipes & Production" description="Create governed recipes, review location-aware cost rollups, plan production, and connect approved formulas to POS consumption.">
  {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}
  <section className="grid"><div className="card"><h2>Approved recipes</h2><strong>{recipes.filter(x=>x.status==="approved").length}</strong></div><div className="card"><h2>Open batches</h2><strong>{batches.filter(x=>x.status==="planned").length}</strong></div><div className="card"><h2>Integration exceptions</h2><strong>{(recon?.failed_events||0)+(recon?.dead_letter_events||0)+(recon?.unprocessed_pos_events||0)}</strong></div></section>
  <Can permission="inventory.*">
   <section className="card section-gap">
    <h2>New recipe</h2>
    <p className="section-copy">Recipes begin as drafts. Approval should occur only after ingredient quantities, yield, waste factors, and costing have been reviewed.</p>
    <form onSubmit={createRecipe}>
     <div className="inline-form"><input name="code" placeholder="Recipe code" required/><input name="name" placeholder="Recipe name" required/><select name="output_item" required><option value="">Output item</option>{items.map(x=><option key={x.id} value={x.id}>{x.sku} — {x.name}</option>)}</select><input name="yield" type="number" min="0.0001" step="0.0001" placeholder="Yield quantity" required/><input name="notes" placeholder="Notes"/></div>
     {lines.map((line,index)=><div className="inline-form" key={index}>
      <select value={line.ingredient_item_id} onChange={event=>updateLine(index,"ingredient_item_id",event.target.value)} required><option value="">Ingredient</option>{items.map(x=><option key={x.id} value={x.id}>{x.sku} — {x.name}</option>)}</select>
      <input value={line.quantity} onChange={event=>updateLine(index,"quantity",event.target.value)} type="number" min="0.000001" step="0.000001" placeholder="Quantity" required/>
      <input value={line.waste_factor} onChange={event=>updateLine(index,"waste_factor",event.target.value)} type="number" min="0" max="1" step="0.0001" placeholder="Waste factor"/>
      <label className="check-control compact-check"><input type="checkbox" checked={line.optional} onChange={event=>updateLine(index,"optional",event.target.checked)}/><span>Optional</span></label>
      <button type="button" className="secondary" onClick={()=>setLines(rows=>rows.length===1?[blank()]:rows.filter((_,rowIndex)=>rowIndex!==index))}>Remove</button>
     </div>)}
     <div className="inline-form"><button type="button" className="secondary" onClick={()=>setLines(rows=>[...rows,blank()])}>Add ingredient</button><button className="primary compact" disabled={busy}>Create recipe</button></div>
    </form>
   </section>
  </Can>
  <section className="card section-gap"><div className="topline"><div><h2>Recipe catalogue</h2><p>Open a recipe for ingredient cost rollup, stock capacity, margin analysis, approval, retirement, and version governance.</p></div></div><DataTable columns={["Code","Name","Version","Output","Yield","Ingredients","Status","Costing"]} rows={recipes.map(x=>[<Link className="recipe-catalogue-link" href={`/production/recipes/${x.id}`} key={x.id}>{x.code}</Link>,x.name,x.version,item(x.output_item_id),formatQuantity(x.yield_quantity),x.lines.map(line=>`${item(line.ingredient_item_id)} × ${formatQuantity(line.quantity)}`).join(", "),<StatusBadge key={`${x.id}-status`} status={x.status}/>,<Link className="secondary compact" href={`/production/recipes/${x.id}`} key={`${x.id}-cost`}>Open costing</Link>])} rowIds={recipes.map(x=>x.id)} searchPlaceholder="Search recipes, output, ingredients, version, or status" exportFileName="hidden-oasis-recipes" emptyTitle="No recipes" emptyMessage="Create the first governed recipe."/></section>
  <Can permission="inventory.*"><section className="card section-gap"><h2>Plan production</h2><form className="inline-form" onSubmit={createBatch}><select name="recipe" required><option value="">Approved recipe</option>{recipes.filter(x=>x.status==="approved").map(x=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select><select name="location" required><option value="">Location</option>{locations.map(x=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select><input name="quantity" type="number" min="0.0001" step="0.0001" placeholder="Planned output" required/><input name="notes" placeholder="Notes"/><button className="primary compact" disabled={busy}>Plan batch</button></form><DataTable columns={["Batch","Recipe","Location","Planned","Actual","Status","Document","Action"]} rows={batches.map(x=>[x.batch_number,recipe(x.recipe_id),loc(x.location_id),formatQuantity(x.planned_quantity),x.actual_quantity?formatQuantity(x.actual_quantity):"—",<StatusBadge key={`${x.id}-status`} status={x.status}/>,x.stock_document_id?<Link href={`/stock/documents/${x.stock_document_id}`} key={`${x.id}-doc`}>Open</Link>:"—",x.status==="planned"?<button className="secondary compact" disabled={busy} onClick={()=>completeBatch(x.id,x.planned_quantity)}>Complete</button>:"—"])} rowIds={batches.map(x=>x.id)} searchPlaceholder="Search production batches" exportFileName="hidden-oasis-production-batches" emptyTitle="No production batches" emptyMessage="Plan a batch from an approved recipe."/></section></Can>
  <Can permission="integrations.*"><section className="card section-gap"><h2>POS product mapping</h2><form className="inline-form" onSubmit={createMapping}><input name="pos_system" defaultValue="hidden-oasis-pos" required/><input name="external_product_id" placeholder="POS product ID" required/><select name="recipe" required><option value="">Recipe</option>{recipes.filter(x=>x.status==="approved").map(x=><option key={x.id} value={x.id}>{x.code}</option>)}</select><select name="location" required><option value="">Consumption location</option>{locations.map(x=><option key={x.id} value={x.id}>{x.code}</option>)}</select><button className="primary compact" disabled={busy}>Map product</button></form><DataTable columns={["POS","Product ID","Recipe","Location"]} rows={mappings.map(x=>[x.pos_system,x.external_product_id,recipe(x.recipe_id),loc(x.location_id)])} rowIds={mappings.map(x=>x.id)} searchPlaceholder="Search POS mappings" exportFileName="hidden-oasis-pos-mappings" emptyTitle="No POS mappings" emptyMessage="Map approved recipes to POS products."/></section></Can>
 </AppShell>;
}
