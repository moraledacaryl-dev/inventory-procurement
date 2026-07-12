"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { FeedbackBanner } from "../../components/FeedbackBanner";
import { DataTable } from "../../components/DataTable";
import { api } from "../../lib/api";

type Dimension={id:string;behavior_key?:string|null};
type Item={id:string;sku:string;name:string;item_type_name?:string|null;department_name?:string|null;minimum_stock:string;is_active:boolean};

export default function Page(){
 const[items,setItems]=useState<Item[]>([]);const[error,setError]=useState("");
 const load=useCallback(async()=>{try{const workspaces=await api<Dimension[]>("/classification/dimensions?dimension_type=workspace&active=true");const hotel=workspaces.find(x=>x.behavior_key==="hotel");if(!hotel)throw new Error("Hotel workspace is not configured.");setItems(await api<Item[]>(`/items?workspace_id=${hotel.id}&active=true`))}catch(e){setError((e as Error).message)}},[]);useEffect(()=>{void load()},[load]);
 const amenities=useMemo(()=>items.filter(x=>x.item_type_name?.toLowerCase().includes("amenity")),[items]);const linen=useMemo(()=>items.filter(x=>x.item_type_name?.toLowerCase().includes("linen")),[items]);const housekeeping=useMemo(()=>items.filter(x=>x.item_type_name?.toLowerCase().includes("housekeeping")),[items]);
 return <AppShell title="Hotel Operations" description="Guest amenities, housekeeping supplies, linen, reusable property, counts, purchasing, and receiving without F&B production clutter.">
  {error?<FeedbackBanner tone="error" title="Hotel workspace unavailable" message={error}/>:null}
  <section className="grid"><div className="card"><h2>Hotel items</h2><strong>{items.length}</strong><p>Active records assigned to the Hotel workspace.</p></div><div className="card"><h2>Guest amenities</h2><strong>{amenities.length}</strong><p>Consumables intended for rooms and guest service.</p></div><div className="card"><h2>Linen records</h2><strong>{linen.length}</strong><p>Reusable hotel property prepared for Pass 3 circulation controls.</p></div></section>
  <section className="workspace-launch-grid section-gap">
   <Link className="card workspace-launch" href="/items"><span className="page-kicker">Catalogue</span><h2>Amenities & supplies</h2><p>Maintain hotel consumables, housekeeping supplies, linen, and property classifications.</p></Link>
   <Link className="card workspace-launch" href="/stock"><span className="page-kicker">Availability</span><h2>Hotel stock</h2><p>Review balances, movement history, aging, and location availability.</p></Link>
   <Link className="card workspace-launch" href="/counts"><span className="page-kicker">Control</span><h2>Hotel counts</h2><p>Run guided counts for storerooms, housekeeping areas, and linen locations.</p></Link>
   <Link className="card workspace-launch" href="/inventory-operations"><span className="page-kicker">Movement</span><h2>Issues & transfers</h2><p>Issue supplies and control adjustments, damage, waste, and transfers.</p></Link>
   <Link className="card workspace-launch" href="/purchasing"><span className="page-kicker">Supply</span><h2>Hotel purchasing</h2><p>Manage replenishment, requisitions, quotations, and purchase commitments.</p></Link>
   <Link className="card workspace-launch" href="/receiving"><span className="page-kicker">Inbound</span><h2>Receiving</h2><p>Receive hotel supplies with accepted, rejected, and returned quantities.</p></Link>
  </section>
  <section className="card section-gap"><div className="topline"><div><h2>Hotel catalogue snapshot</h2><p>Hotel-only records are shown automatically from their workspace assignment.</p></div><Link className="secondary compact" href="/items">Open catalogue</Link></div><DataTable columns={["SKU","Item","Type","Department","Minimum"]} rows={items.slice(0,20).map(x=>[x.sku,x.name,x.item_type_name||"Unclassified",x.department_name||"—",x.minimum_stock])} rowIds={items.slice(0,20).map(x=>x.id)} searchPlaceholder="Search hotel items" exportFileName="hidden-oasis-hotel-items" emptyTitle="No hotel items" emptyMessage="Classify existing hotel records in Operating Structure."/></section>
  {housekeeping.length===0&&items.length>0?<FeedbackBanner tone="info" title="Housekeeping classification still needs review" message="No active item is currently classified as a housekeeping supply. Use Operating Structure to complete migration."/>:null}
 </AppShell>
}
