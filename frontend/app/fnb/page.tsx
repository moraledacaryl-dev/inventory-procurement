"use client";

import Link from "next/link";
import { WorkspaceLink } from "../../components/WorkspaceLink";
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
 return <AppShell title="F&B Operations" description="Menu, ingredients, and kitchen operations.">
  {error?<FeedbackBanner tone="error" title="F&B workspace unavailable" message={error}/>:null}
  <section className="grid"><div className="card"><h2>Active F&B items</h2><strong>{items.length}</strong><p>Ingredients, prep items, packaging, and finished products.</p></div><div className="card"><h2>Approved recipes</h2><strong>{recipes.filter(x=>x.status==="approved").length}</strong><p>Approved formulas available for production and POS use.</p></div><div className="card"><h2>Open batches</h2><strong>{batches.filter(x=>["planned","in_progress"].includes(x.status)).length}</strong><p>Production requiring execution or completion.</p></div></section>
  <section className="workspace-launch-grid section-gap">
   <WorkspaceLink href="/fnb/menu" label="Menu & products" description="Products, variants, and prices."/><WorkspaceLink href="/items" label="Ingredients & inventory items" description="Item details, costs, and stock policies."/>
   <WorkspaceLink href="/production" label="Recipes & production" description="Recipes, costing, and batches."/>
   <WorkspaceLink href="/fnb/staff-meals" label="Staff meals" description="Ingredients used and cost per serving."/>
   <WorkspaceLink href="/inventory-operations" label="Waste & adjustments" description="Issues, transfers, and adjustments."/>
   <WorkspaceLink href="/purchasing" label="F&B purchasing" description="Replenishment and purchase orders."/>
   <WorkspaceLink href="/receiving" label="Receiving" description="Deliveries and supplier returns."/>
   <WorkspaceLink href="/integrations/pos" label="POS consumption" description="Sales, mappings, and consumption."/>
  </section>
  <section className="card section-gap"><div className="topline"><div><h2>Recipe status</h2><p>Recent governed formulas in the F&B workspace.</p></div><Link className="secondary compact" href="/production">Open all</Link></div><div className="workspace-record-list">{recipes.slice(0,8).map(row=><Link href={`/production/recipes/${row.id}`} key={row.id}><span><strong>{row.code}</strong><small>{row.name}</small></span><StatusBadge status={row.status}/></Link>)}{recipes.length===0?<p className="muted">No recipes have been created.</p>:null}</div></section>
 </AppShell>
}
