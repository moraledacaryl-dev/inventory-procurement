"use client";

import Link from "next/link";
import { WorkspaceLink } from "../../components/WorkspaceLink";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { FeedbackBanner } from "../../components/FeedbackBanner";
import { DataTable } from "../../components/DataTable";
import { api } from "../../lib/api";

type Dimension={id:string;code:string;name:string;behavior_key?:string|null};
type Bootstrap={dimensions:Record<string,Dimension[]>};
type Item={id:string;sku:string;name:string;item_type_id?:string|null;department_id?:string|null;minimum_stock:string;is_active:boolean};

export default function Page(){
 const[items,setItems]=useState<Item[]>([]);const[dimensions,setDimensions]=useState<Record<string,Dimension[]>>({});const[error,setError]=useState("");
 const load=useCallback(async()=>{try{const structure=await api<Bootstrap>("/classification/bootstrap");setDimensions(structure.dimensions);const hotel=structure.dimensions.workspace?.find(x=>x.behavior_key==="hotel");if(!hotel)throw new Error("Hotel workspace is not configured.");setItems(await api<Item[]>(`/items?workspace_id=${hotel.id}&active=true`))}catch(e){setError((e as Error).message)}},[]);useEffect(()=>{void load()},[load]);
 const typesById=useMemo(()=>new Map((dimensions.item_type||[]).map(type=>[type.id,type])),[dimensions]);
 const amenities=items.filter(item=>typesById.get(item.item_type_id||"")?.code==="guest-amenity");
 const linen=items.filter(item=>typesById.get(item.item_type_id||"")?.code==="linen");
 const housekeeping=items.filter(item=>typesById.get(item.item_type_id||"")?.code==="housekeeping-supply");
 return <AppShell title="Hotel Operations" description="Amenities, housekeeping, and linen.">
  {error?<FeedbackBanner tone="error" title="Hotel workspace unavailable" message={error}/>:null}
  <section className="grid"><div className="card"><h2>Hotel items</h2><strong>{items.length}</strong><p>Active records assigned to the Hotel workspace.</p></div><div className="card"><h2>Guest amenities</h2><strong>{amenities.length}</strong><p>Consumables intended for rooms and guest service.</p></div><div className="card"><h2>Linen records</h2><strong>{linen.length}</strong><p>Linen items in the catalogue.</p></div></section>
  <section className="workspace-launch-grid section-gap">
   <WorkspaceLink href="/items" label="Amenities & supplies" description="Item details, costs, and stock policies."/>
   <WorkspaceLink href="/stock" label="Hotel stock" description="Balances and movement history."/>
   <WorkspaceLink href="/counts" label="Hotel counts" description="Stock counts and variance reviews."/>
   <WorkspaceLink href="/inventory-operations" label="Issues & transfers" description="Issues, transfers, and adjustments."/>
   <WorkspaceLink href="/purchasing" label="Hotel purchasing" description="Replenishment and purchase orders."/>
   <WorkspaceLink href="/receiving" label="Receiving" description="Deliveries and supplier returns."/>
  </section>
  <section className="card section-gap"><div className="topline"><div><h2>Hotel catalogue snapshot</h2><p>Items assigned to the Hotel workspace.</p></div><Link className="secondary compact" href="/items">Open catalogue</Link></div><DataTable columns={["SKU","Item","Type","Department","Minimum"]} rows={items.slice(0,20).map(x=>[x.sku,x.name,typesById.get(x.item_type_id||"")?.name||"Unclassified",dimensions.department?.find(department=>department.id===x.department_id)?.name||"—",x.minimum_stock])} rowIds={items.slice(0,20).map(x=>x.id)} searchPlaceholder="Search hotel items" exportFileName="hidden-oasis-hotel-items" emptyTitle="No hotel items" emptyMessage="Classify existing hotel records in Operating Structure."/></section>
  {housekeeping.length===0&&items.length>0?<FeedbackBanner tone="info" title="Housekeeping classification still needs review" message="No active item is currently classified as a housekeeping supply. Use Operating Structure to complete migration."/>:null}
 </AppShell>
}
