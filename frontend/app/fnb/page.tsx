"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { FeedbackBanner } from "../../components/FeedbackBanner";
import { StatusBadge } from "../../components/StatusBadge";
import { api } from "../../lib/api";

type Dimension={id:string;behavior_key?:string|null};
type Item={id:string;sku:string;name:string;item_type_name?:string|null;is_active:boolean};
type Recipe={id:string;code:string;name:string;status:string};
type Batch={id:string;batch_number:string;status:string};

export default function Page(){
 const[items,setItems]=useState<Item[]>([]);const[recipes,setRecipes]=useState<Recipe[]>([]);const[batches,setBatches]=useState<Batch[]>([]);const[error,setError]=useState("");
 const load=useCallback(async()=>{try{const workspaces=await api<Dimension[]>("/classification/dimensions?dimension_type=workspace&active=true");const fnb=workspaces.find(x=>x.behavior_key==="fnb");if(!fnb)throw new Error("F&B workspace is not configured.");const[i,r,b]=await Promise.all([api<Item[]>(`/items?workspace_id=${fnb.id}&active=true`),api<Recipe[]>("/recipes"),api<Batch[]>("/production-batches")]);setItems(i);setRecipes(r);setBatches(b)}catch(e){setError((e as Error).message)}},[]);useEffect(()=>{void load()},[load]);
 return <AppShell title="F&B Operations" description="Ingredients, recipes, outlet stock, production, food waste, purchasing, receiving, and POS-linked consumption in one focused workspace.">
  {error?<FeedbackBanner tone="error" title="F&B workspace unavailable" message={error}/>:null}
  <section className="grid"><div className="card"><h2>Active F&B items</h2><strong>{items.length}</strong><p>Ingredients, prep items, packaging, and finished products.</p></div><div className="card"><h2>Approved recipes</h2><strong>{recipes.filter(x=>x.status==="approved").length}</strong><p>Approved formulas available for production and POS use.</p></div><div className="card"><h2>Open batches</h2><strong>{batches.filter(x=>["planned","in_progress"].includes(x.status)).length}</strong><p>Production requiring execution or completion.</p></div></section>
  <section className="workspace-launch-grid section-gap">
   <Link className="card workspace-launch" href="/items"><span className="page-kicker">Catalogue</span><h2>Ingredients & products</h2><p>Maintain F&B item classifications, costs, stock policies, and suppliers.</p></Link>
   <Link className="card workspace-launch" href="/production"><span className="page-kicker">Recipes</span><h2>Recipes & production</h2><p>Create formulas, review costing, plan batches, and record actual output.</p></Link>
   <Link className="card workspace-launch" href="/inventory-operations"><span className="page-kicker">Control</span><h2>Waste & adjustments</h2><p>Record controlled food waste, damage, corrections, and transfers.</p></Link>
   <Link className="card workspace-launch" href="/purchasing"><span className="page-kicker">Supply</span><h2>F&B purchasing</h2><p>Plan replenishment, requisitions, quotations, and purchase orders.</p></Link>
   <Link className="card workspace-launch" href="/receiving"><span className="page-kicker">Inbound</span><h2>Receiving</h2><p>Receive ingredients and supplies with discrepancy and return controls.</p></Link>
   <Link className="card workspace-launch" href="/integrations/pos"><span className="page-kicker">Sales</span><h2>POS consumption</h2><p>Review product mappings, sale consumption, reversals, and reconciliation.</p></Link>
  </section>
  <section className="card section-gap"><div className="topline"><div><h2>Recipe status</h2><p>Recent governed formulas in the F&B workspace.</p></div><Link className="secondary compact" href="/production">Open all</Link></div><div className="workspace-record-list">{recipes.slice(0,8).map(row=><Link href={`/production/recipes/${row.id}`} key={row.id}><span><strong>{row.code}</strong><small>{row.name}</small></span><StatusBadge status={row.status}/></Link>)}{recipes.length===0?<p className="muted">No recipes have been created.</p>:null}</div></section>
 </AppShell>
}
