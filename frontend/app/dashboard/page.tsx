"use client";

import Link from "next/link";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { api } from "../../lib/api";

type Item={id:string;sku:string;name:string;minimum_stock:string;standard_cost:string;is_active:boolean};
type Supplier={id:string;code:string;name:string;is_active?:boolean};
type Balance={item_id:string;location_id:string;quantity:string;average_cost:string};
type Movement={id:string;item_id:string;location_id:string;quantity:string;unit_cost:string;reason:string|null;created_at:string};
type POLine={item_id:string;ordered_quantity:string;received_quantity:string;unit_price:string};
type PO={id:string;purchase_order_number:string;supplier_id:string;status:string;created_at:string;lines:POLine[]};

const StrokeIcon=({children}:{children:ReactNode})=><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>;
const money=(value:number)=>new Intl.NumberFormat("en-PH",{style:"currency",currency:"PHP",maximumFractionDigits:2}).format(value);
const statusClass=(status:string)=>status==="approved"||status==="received"||status==="closed"?"ready":"pending";

export default function Dashboard(){
  const[items,setItems]=useState<Item[]>([]),[suppliers,setSuppliers]=useState<Supplier[]>([]),[balances,setBalances]=useState<Balance[]>([]),[movements,setMovements]=useState<Movement[]>([]),[pos,setPos]=useState<PO[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState("");
  useEffect(()=>{void(async()=>{try{const[i,s,b,m,p]=await Promise.all([api<Item[]>("/items"),api<Supplier[]>("/suppliers"),api<Balance[]>("/stock/balances"),api<Movement[]>("/stock/movements?limit=20"),api<PO[]>("/purchase-orders")]);setItems(i);setSuppliers(s);setBalances(b);setMovements(m);setPos(p)}catch(e){setError((e as Error).message)}finally{setLoading(false)}})()},[]);

  const summary=useMemo(()=>{
    const quantityByItem=new Map<string,number>();
    balances.forEach(x=>quantityByItem.set(x.item_id,(quantityByItem.get(x.item_id)||0)+Number(x.quantity)));
    const active=items.filter(x=>x.is_active),inactive=items.length-active.length;
    let inventoryValue=0,inStock=0,low=0,out=0;
    active.forEach(item=>{const quantity=quantityByItem.get(item.id)||0;const related=balances.filter(x=>x.item_id===item.id);const avg=related.length?related.reduce((s,x)=>s+Number(x.average_cost)*Number(x.quantity),0)/(related.reduce((s,x)=>s+Number(x.quantity),0)||1):Number(item.standard_cost||0);inventoryValue+=quantity*avg;if(quantity<=0)out++;else if(quantity<Number(item.minimum_stock||0))low++;else inStock++});
    const pending=pos.filter(x=>!["received","closed","cancelled"].includes(x.status)).length;
    return{inventoryValue,inStock,low,out,inactive,pending,total:items.length,quantityByItem};
  },[items,balances,pos]);

  const lowItems=useMemo(()=>items.filter(x=>x.is_active&&(summary.quantityByItem.get(x.id)||0)<Number(x.minimum_stock||0)).sort((a,b)=>(summary.quantityByItem.get(a.id)||0)-(summary.quantityByItem.get(b.id)||0)).slice(0,4),[items,summary]);
  const recentPOs=[...pos].sort((a,b)=>Date.parse(b.created_at)-Date.parse(a.created_at)).slice(0,5);
  const recentMoves=[...movements].sort((a,b)=>Date.parse(b.created_at)-Date.parse(a.created_at)).slice(0,5);
  const date=new Intl.DateTimeFormat("en-PH",{weekday:"long",month:"long",day:"numeric",year:"numeric",timeZone:"Asia/Manila"}).format(new Date());
  const totalStatus=Math.max(summary.total,1),stockStops=[summary.inStock/totalStatus*100,(summary.inStock+summary.low)/totalStatus*100,(summary.inStock+summary.low+summary.out)/totalStatus*100];
  const donutStyle={background:summary.total?`conic-gradient(#42bd73 0 ${stockStops[0]}%,#f7b928 ${stockStops[0]}% ${stockStops[1]}%,#ef5555 ${stockStops[1]}% ${stockStops[2]}%,#aeb9c5 ${stockStops[2]}% 100%)`:"conic-gradient(#e5eaf0 0 100%)"};
  const metrics=[
    {label:"Total Products",value:loading?"…":String(summary.total),note:"Catalogue records",tone:"blue",icon:<StrokeIcon><path d="m21 8-9 5-9-5"/><path d="m3 8 9-5 9 5v8l-9 5-9-5Z"/><path d="M12 13v8"/></StrokeIcon>},
    {label:"Inventory Value",value:loading?"…":money(summary.inventoryValue),note:"Current valuation",tone:"green",icon:<StrokeIcon><path d="M4 19V5h16v14Z"/><path d="M8 9h8M8 13h5"/></StrokeIcon>},
    {label:"Pending POs",value:loading?"…":String(summary.pending),note:"Awaiting completion",tone:"amber",icon:<StrokeIcon><circle cx="9" cy="20" r="1"/><circle cx="19" cy="20" r="1"/><path d="M3 4h2l2.5 11h11l2-7H7"/></StrokeIcon>},
    {label:"Low Stock Items",value:loading?"…":String(summary.low+summary.out),note:"Require attention",tone:"violet",icon:<StrokeIcon><path d="M6 3h12v18H6Z"/><path d="M9 8h6M9 12h6M9 16h3"/></StrokeIcon>},
    {label:"Total Suppliers",value:loading?"…":String(suppliers.filter(x=>x.is_active!==false).length),note:"Active suppliers",tone:"cyan",icon:<StrokeIcon><circle cx="9" cy="8" r="4"/><path d="M2 21c0-4 3-7 7-7s7 3 7 7M16 5c3 0 5 2 5 5M17 14c3 1 5 3 5 7"/></StrokeIcon>},
  ];

  return <AppShell title="Dashboard" description="Monitor inventory, procurement, receiving, and production from one workspace."><div className="dashboard-overview">
    <section className="dashboard-welcome"><div><h2>Welcome back, Administrator</h2><p>{error?`Dashboard data could not be loaded: ${error}`:"Here is the current operating picture for Hidden Oasis inventory."}</p></div><div className="date-chip"><StrokeIcon><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></StrokeIcon>{date}</div></section>
    <section className="metric-grid" aria-label="Inventory summary">{metrics.map(x=><article className="metric-card" key={x.label}><div className={`metric-icon ${x.tone}`}>{x.icon}</div><div className="metric-copy"><div className="metric-label">{x.label}</div><div className="metric-value">{x.value}</div><div className="metric-note">{x.note}</div></div></article>)}</section>
    <section className="dashboard-primary-grid">
      <article className="dashboard-panel"><div className="panel-header"><div><h3>Inventory Value Overview</h3><p>Current stock value based on quantities and average cost.</p></div><Link className="panel-link" href="/reports">Open reports</Link></div><div className="chart-stage"><div className="chart-axis"><span>{money(summary.inventoryValue)}</span><span>{money(summary.inventoryValue*.75)}</span><span>{money(summary.inventoryValue*.5)}</span><span>{money(summary.inventoryValue*.25)}</span><span>₱0</span></div><div className="chart-gridlines"><span/><span/><span/><span/></div><svg className="chart-svg" viewBox="0 0 700 210" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="dashboardArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2f6fed" stopOpacity=".18"/><stop offset="1" stopColor="#2f6fed" stopOpacity="0"/></linearGradient></defs><path d="M0 190 C180 165 310 120 430 128 C540 134 610 82 700 70 L700 210 L0 210 Z" fill="url(#dashboardArea)"/><path d="M0 190 C180 165 310 120 430 128 C540 134 610 82 700 70" fill="none" stroke="#2f6fed" strokeWidth="3"/></svg><div className="chart-empty-note"><strong>{loading?"Loading valuation…":money(summary.inventoryValue)}</strong><span>{summary.total?`${summary.total} catalogue items included in the current snapshot.`:"Add items and stock transactions to begin valuation."}</span></div><div className="chart-labels"><span>Catalogue</span><span>Receipts</span><span>Movements</span><span>Current</span></div></div></article>
      <article className="dashboard-panel"><div className="panel-header"><div><h3>Stock Status</h3><p>Availability across active catalogue items.</p></div><Link className="panel-link" href="/stock">View stock</Link></div><div className="stock-panel-body"><div className={`donut ${summary.total?"":"empty"}`} style={donutStyle}><div className="donut-copy"><strong>{summary.total}</strong><span>Total items</span></div></div><div className="legend"><div className="legend-row"><span className="legend-dot" style={{background:"#42bd73"}}/><span>In stock</span><strong>{summary.inStock}</strong></div><div className="legend-row"><span className="legend-dot" style={{background:"#f7b928"}}/><span>Low stock</span><strong>{summary.low}</strong></div><div className="legend-row"><span className="legend-dot" style={{background:"#ef5555"}}/><span>Out of stock</span><strong>{summary.out}</strong></div><div className="legend-row"><span className="legend-dot" style={{background:"#aeb9c5"}}/><span>Inactive</span><strong>{summary.inactive}</strong></div></div></div></article>
    </section>
    <section className="dashboard-secondary-grid">
      <article className="dashboard-panel"><div className="panel-header"><div><h3>Recent Purchase Orders</h3><p>Latest procurement documents and approval states.</p></div><Link className="panel-link" href="/purchasing">View all</Link></div><table className="compact-table"><thead><tr><th>PO Number</th><th>Supplier</th><th>Status</th><th>Total</th></tr></thead><tbody>{recentPOs.length?recentPOs.map(p=><tr key={p.id}><td>{p.purchase_order_number}</td><td>{suppliers.find(s=>s.id===p.supplier_id)?.name||"Unknown"}</td><td><span className={`status-pill ${statusClass(p.status)}`}>{p.status}</span></td><td>{money(p.lines.reduce((sum,x)=>sum+Number(x.ordered_quantity)*Number(x.unit_price),0))}</td></tr>):<tr className="empty-row"><td colSpan={4}>No purchase orders have been created yet.</td></tr>}</tbody></table></article>
      <article className="dashboard-panel"><div className="panel-header"><div><h3>Low Stock Alerts</h3><p>Items below configured reorder levels.</p></div><Link className="panel-link" href="/purchasing">View all</Link></div>{lowItems.length?<div className="alert-list">{lowItems.map(item=><div className="alert-item" key={item.id}><div className="small-icon"><StrokeIcon><path d="M12 3 2 21h20Z"/><path d="M12 9v5M12 18h.01"/></StrokeIcon></div><div className="list-copy"><strong>{item.sku} — {item.name}</strong><span>Minimum {item.minimum_stock}</span></div><div className="list-value">{summary.quantityByItem.get(item.id)||0}</div></div>)}</div>:<div className="empty-list"><div><strong>No low-stock alerts</strong><span>All configured items are currently above their reorder levels.</span></div></div>}</article>
      <article className="dashboard-panel"><div className="panel-header"><div><h3>Recent Activity</h3><p>Latest inventory movements.</p></div><Link className="panel-link" href="/stock">View all</Link></div>{recentMoves.length?<div className="activity-list">{recentMoves.map(m=><div className="activity-item" key={m.id}><div className="small-icon"><StrokeIcon><path d="M4 12h16M14 6l6 6-6 6"/></StrokeIcon></div><div className="list-copy"><strong>{items.find(x=>x.id===m.item_id)?.sku||"Item"} {Number(m.quantity)>0?"received":"issued"}</strong><span>{new Date(m.created_at).toLocaleString("en-PH")} · {m.reason||"Stock movement"}</span></div><div className="list-value">{Number(m.quantity)>0?"+":""}{m.quantity}</div></div>)}</div>:<div className="empty-list"><div><strong>No recent activity</strong><span>Completed stock transactions will be listed here.</span></div></div>}</article>
    </section>
    <section className="quick-actions-row" aria-label="Quick actions"><Link className="quick-action-button primary-action" href="/receiving">Receive delivery</Link><Link className="quick-action-button" href="/purchasing">Create purchase order</Link><Link className="quick-action-button" href="/counts">Start stock count</Link><Link className="quick-action-button" href="/items">Add product</Link></section>
  </div></AppShell>;
}
