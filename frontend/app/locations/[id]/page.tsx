"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "../../../components/AppShell";
import { Can } from "../../../components/SessionContext";
import { ConfirmDialog } from "../../../components/ConfirmDialog";
import { ErrorState, LoadingState } from "../../../components/AsyncState";
import { FeedbackBanner } from "../../../components/FeedbackBanner";
import { FormField, FormSection } from "../../../components/FormField";
import { StatusBadge } from "../../../components/StatusBadge";
import { api } from "../../../lib/api";
import { formatDateTime, formatMoney, formatQuantity } from "../../../lib/formatters";

type LocationRef={id:string;code:string;name:string;location_type?:string;is_active?:boolean};
type Detail={location:{id:string;code:string;name:string;location_type:string;parent_id:string|null;is_active:boolean};parent:LocationRef|null;children:LocationRef[];metrics:{item_count:number;total_quantity:string;inventory_value:string;negative_balances:number;low_stock_items:number;policy_count:number;inbound_transfers:number;outbound_transfers:number;lot_quantity:string};balances:{item_id:string;sku:string;item_name:string;quantity:string;average_cost:string;inventory_value:string;allow_negative_stock:boolean;updated_at:string}[];policies:{id:string;item_id:string;sku:string;item_name:string;minimum_stock:string;reorder_quantity:string;maximum_stock:string|null;cycle_count_days:number;is_active:boolean}[];recent_movements:{id:string;item_id:string;sku:string;item_name:string;quantity:string;unit_cost:string;reason:string|null;created_at:string}[]};
type Edit={name:string;location_type:string;parent_id:string};

export default function LocationDetailPage(){
  const{id}=useParams<{id:string}>();
  const[detail,setDetail]=useState<Detail|null>(null);
  const[allLocations,setAllLocations]=useState<LocationRef[]>([]);
  const[edit,setEdit]=useState<Edit|null>(null);
  const[loading,setLoading]=useState(true);
  const[saving,setSaving]=useState(false);
  const[error,setError]=useState("");
  const[feedback,setFeedback]=useState<{tone:"success"|"error"|"info";title:string;message?:string}|null>(null);
  const[confirmStatus,setConfirmStatus]=useState(false);

  const load=useCallback(async()=>{setLoading(true);setError("");try{const[d,l]=await Promise.all([api<Detail>(`/locations/${id}`),api<LocationRef[]>("/locations")]);setDetail(d);setAllLocations(l);setEdit({name:d.location.name,location_type:d.location.location_type,parent_id:d.location.parent_id||""})}catch(exception){setError((exception as Error).message)}finally{setLoading(false)}},[id]);
  useEffect(()=>{void load()},[load]);

  const dirty=useMemo(()=>detail&&edit?JSON.stringify(edit)!==JSON.stringify({name:detail.location.name,location_type:detail.location.location_type,parent_id:detail.location.parent_id||""}):false,[detail,edit]);
  const parentOptions=allLocations.filter(row=>row.id!==id&&row.is_active!==false);

  async function save(event:FormEvent){event.preventDefault();if(!edit)return;setSaving(true);setFeedback(null);try{await api(`/locations/${id}`,{method:"PATCH",body:JSON.stringify({...edit,parent_id:edit.parent_id||null})});setFeedback({tone:"success",title:"Location updated",message:"Hierarchy and location controls were saved."});await load()}catch(exception){setFeedback({tone:"error",title:"Location could not be updated",message:(exception as Error).message})}finally{setSaving(false)}}
  async function toggleStatus(){if(!detail)return;setSaving(true);try{await api(`/locations/${id}`,{method:"PATCH",body:JSON.stringify({is_active:!detail.location.is_active})});setFeedback({tone:"success",title:detail.location.is_active?"Location deactivated":"Location reactivated"});setConfirmStatus(false);await load()}catch(exception){setFeedback({tone:"error",title:"Status could not be changed",message:(exception as Error).message});setConfirmStatus(false)}finally{setSaving(false)}}

  if(error)return <AppShell title="Location"><ErrorState title="Location unavailable" message={error} onRetry={()=>void load()}/></AppShell>;
  if(loading||!detail||!edit)return <AppShell title="Location"><LoadingState title="Loading location workspace" rows={6}/></AppShell>;

  return <AppShell title={`${detail.location.code} — ${detail.location.name}`} description="Review hierarchy, stock exposure, replenishment controls, transfers, and location lifecycle.">
    <div className="item-detail-header"><div><Link href="/locations" className="back-link">← Location master</Link><div className="item-detail-title"><h2>{detail.location.name}</h2><StatusBadge status={detail.location.is_active?"active":"inactive"}/></div><p>{detail.parent?`Child of ${detail.parent.code} — ${detail.parent.name}`:"Top-level operational location"}</p></div><Can permission="locations.*"><button className="secondary" onClick={()=>setConfirmStatus(true)}>{detail.location.is_active?"Deactivate location":"Reactivate location"}</button></Can></div>

    <section className="item-detail-metrics"><div><span>Items with balances</span><strong>{detail.metrics.item_count}</strong></div><div><span>Inventory value</span><strong>{formatMoney(detail.metrics.inventory_value)}</strong></div><div><span>Low-stock items</span><strong>{detail.metrics.low_stock_items}</strong></div><div><span>Negative balances</span><strong>{detail.metrics.negative_balances}</strong></div><div><span>Open transfers</span><strong>{detail.metrics.inbound_transfers+detail.metrics.outbound_transfers}</strong></div></section>

    <section className="location-control-grid">
      <article className="card"><h2>Location controls</h2><form onSubmit={save}><FormSection title="Identity and hierarchy"><FormField label="Code" name="location-detail-code" hint="Canonical and intentionally immutable."><input value={detail.location.code} disabled/></FormField><FormField label="Name" name="location-detail-name" required><input value={edit.name} onChange={event=>setEdit({...edit,name:event.target.value})}/></FormField><FormField label="Type" name="location-detail-type" required><select value={edit.location_type} onChange={event=>setEdit({...edit,location_type:event.target.value})}><option value="site">Site</option><option value="warehouse">Warehouse</option><option value="storeroom">Storeroom</option><option value="department">Department</option><option value="production">Production area</option><option value="transit">Transit area</option></select></FormField><FormField label="Parent location" name="location-detail-parent" optional><select value={edit.parent_id} onChange={event=>setEdit({...edit,parent_id:event.target.value})}><option value="">Top level</option>{parentOptions.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></FormField></FormSection><Can permission="locations.*"><div className="form-actions"><button className="primary" disabled={!dirty||saving}>{saving?"Saving…":"Save changes"}</button></div></Can></form>{feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}</article>

      <article className="card"><h2>Hierarchy</h2><div className="location-hierarchy"><div className="location-node location-node--current"><strong>{detail.location.code}</strong><span>{detail.location.name}</span></div>{detail.children.length?<div className="location-children">{detail.children.map(child=><Link href={`/locations/${child.id}`} className="location-node" key={child.id}><strong>{child.code}</strong><span>{child.name}</span><StatusBadge status={child.is_active?"active":"inactive"}/></Link>)}</div>:<p className="config-empty">No child locations.</p>}</div><div className="location-control-note"><strong>Deactivation rules</strong><span>A location cannot be deactivated while it has non-zero stock, active children, or open transfers.</span></div></article>
    </section>

    <section className="card section-gap"><div className="topline"><div><h2>Stock exposure</h2><p>Current balances, policy overrides, and negative-stock authorization.</p></div><Link className="secondary" href={`/stock?location_id=${id}`}>Open filtered stock</Link></div><div className="table-wrap"><table><thead><tr><th>Item</th><th>Quantity</th><th>Average cost</th><th>Value</th><th>Negative policy</th><th>Updated</th></tr></thead><tbody>{detail.balances.length?detail.balances.map(row=><tr key={row.item_id}><td><Link href={`/items/${row.item_id}`}>{row.sku} — {row.item_name}</Link></td><td className={Number(row.quantity)<0?"negative":""}>{formatQuantity(row.quantity)}</td><td>{formatMoney(row.average_cost)}</td><td>{formatMoney(row.inventory_value)}</td><td>{row.allow_negative_stock?"Allowed":"Blocked"}</td><td>{formatDateTime(row.updated_at)}</td></tr>):<tr><td colSpan={6}>No stock balances exist at this location.</td></tr>}</tbody></table></div></section>

    <section className="location-control-grid section-gap"><article className="card"><h2>Location-specific item policies</h2><div className="table-wrap"><table><thead><tr><th>Item</th><th>Minimum</th><th>Reorder</th><th>Maximum</th><th>Count cycle</th><th>Status</th></tr></thead><tbody>{detail.policies.length?detail.policies.map(row=><tr key={row.id}><td><Link href={`/items/${row.item_id}`}>{row.sku} — {row.item_name}</Link></td><td>{formatQuantity(row.minimum_stock)}</td><td>{formatQuantity(row.reorder_quantity)}</td><td>{row.maximum_stock?formatQuantity(row.maximum_stock):"—"}</td><td>{row.cycle_count_days} days</td><td><StatusBadge status={row.is_active?"active":"inactive"}/></td></tr>):<tr><td colSpan={6}>No location-specific policies are configured.</td></tr>}</tbody></table></div></article>
    <article className="card"><h2>Recent movements</h2><div className="activity-list">{detail.recent_movements.length?detail.recent_movements.map(row=><Link href={`/items/${row.item_id}`} className="activity-item" key={row.id}><div className="list-copy"><strong>{row.sku} — {row.item_name}</strong><span>{formatDateTime(row.created_at)} · {row.reason||"Stock movement"}</span></div><div className={Number(row.quantity)<0?"negative":"positive"}>{Number(row.quantity)>0?"+":""}{formatQuantity(row.quantity)}</div></Link>):<div className="config-empty">No movement history exists.</div>}</div></article></section>

    <ConfirmDialog open={confirmStatus} title={detail.location.is_active?"Deactivate this location?":"Reactivate this location?"} description={detail.location.is_active?"Deactivation is blocked while stock, active child locations, or open transfers remain.":"The location will become available for new stock transactions."} confirmLabel={detail.location.is_active?"Deactivate":"Reactivate"} tone={detail.location.is_active?"danger":"default"} busy={saving} onConfirm={()=>void toggleStatus()} onCancel={()=>setConfirmStatus(false)}/>
  </AppShell>
}
