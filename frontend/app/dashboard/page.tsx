"use client";

import Link from "next/link";
import { ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { ErrorState, LoadingState } from "../../components/AsyncState";
import { RoleWorkspace } from "../../components/RoleWorkspace";
import { StatusBadge } from "../../components/StatusBadge";
import { useSession } from "../../components/SessionContext";
import { api } from "../../lib/api";
import { formatDate, formatDateTime, formatMoney, formatQuantity } from "../../lib/formatters";

type Location={id:string;code:string;name:string};
type DashboardSummary={
  as_of:string;
  metrics:{total_products:number;active_products:number;inactive_products:number;inventory_value:string;pending_purchase_orders:number;overdue_purchase_orders:number;low_stock_items:number;out_of_stock_items:number;active_suppliers:number;movement_count:number};
  comparisons:{movement_count_change_percent:number|null;purchase_order_count_change_percent:number|null;current_purchase_order_count:number;previous_purchase_order_count:number};
  stock_status:{in_stock:number;low_stock:number;out_of_stock:number;inactive:number};
  low_stock:{id:string;sku:string;name:string;quantity:string;minimum_stock:string;shortfall:string}[];
  recent_purchase_orders:{id:string;purchase_order_number:string;supplier_name:string;status:string;created_at:string;expected_delivery_date:string|null;total:string}[];
  recent_movements:{id:string;item_id:string;sku:string;item_name:string;location_name:string;quantity:string;reason:string|null;created_at:string}[];
};
type ValuationHistory={as_of:string;current_value:string;points:{date:string;value:string}[]};

const StrokeIcon=({children}:{children:ReactNode})=><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>;

function UserGreeting(){
  const {user}=useSession();
  return <>Welcome back{user?.full_name?`, ${user.full_name.split(" ")[0]}`:""}</>;
}

function comparisonText(value:number|null,label:string){
  if(value===null)return `No prior ${label} baseline`;
  if(value===0)return `No change from prior period`;
  return `${value>0?"+":""}${value}% vs prior period`;
}

function buildChart(points:{date:string;value:string}[]){
  if(!points.length)return {line:"",area:"",max:0,min:0};
  const values=points.map(point=>Number(point.value));
  const max=Math.max(...values,1),min=Math.min(...values,0),span=Math.max(max-min,1);
  const coords=values.map((value,index)=>{
    const x=points.length===1?350:index/(points.length-1)*700;
    const y=190-(value-min)/span*160;
    return [x,y] as const;
  });
  const line=coords.map(([x,y],index)=>`${index?"L":"M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  return {line,area:`${line} L700 210 L0 210 Z`,max,min};
}

export default function Dashboard(){
  const[locations,setLocations]=useState<Location[]>([]);
  const[locationId,setLocationId]=useState("");
  const[days,setDays]=useState(30);
  const[summary,setSummary]=useState<DashboardSummary|null>(null);
  const[history,setHistory]=useState<ValuationHistory|null>(null);
  const[summaryLoading,setSummaryLoading]=useState(true);
  const[historyLoading,setHistoryLoading]=useState(true);
  const[summaryError,setSummaryError]=useState("");
  const[historyError,setHistoryError]=useState("");

  useEffect(()=>{void api<Location[]>("/locations").then(setLocations).catch(()=>undefined)},[]);

  const query=useMemo(()=>{
    const params=new URLSearchParams({days:String(days)});
    if(locationId)params.set("location_id",locationId);
    return params.toString();
  },[days,locationId]);

  const loadSummary=useCallback(async()=>{
    setSummaryLoading(true);setSummaryError("");
    try{setSummary(await api<DashboardSummary>(`/dashboard/summary?${query}`))}
    catch(error){setSummaryError((error as Error).message)}
    finally{setSummaryLoading(false)}
  },[query]);

  const loadHistory=useCallback(async()=>{
    setHistoryLoading(true);setHistoryError("");
    try{setHistory(await api<ValuationHistory>(`/dashboard/valuation-history?${query}`))}
    catch(error){setHistoryError((error as Error).message)}
    finally{setHistoryLoading(false)}
  },[query]);

  useEffect(()=>{void loadSummary();void loadHistory()},[loadSummary,loadHistory]);

  const metrics=summary?[
    {label:"Total Products",value:String(summary.metrics.total_products),note:`${summary.metrics.active_products} active`,href:"/items",tone:"blue",icon:<StrokeIcon><path d="m21 8-9 5-9-5"/><path d="m3 8 9-5 9 5v8l-9 5-9-5Z"/><path d="M12 13v8"/></StrokeIcon>},
    {label:"Inventory Value",value:formatMoney(summary.metrics.inventory_value),note:`As of ${formatDateTime(summary.as_of)}`,href:"/reports",tone:"green",icon:<StrokeIcon><path d="M4 19V5h16v14Z"/><path d="M8 9h8M8 13h5"/></StrokeIcon>},
    {label:"Pending POs",value:String(summary.metrics.pending_purchase_orders),note:summary.metrics.overdue_purchase_orders?`${summary.metrics.overdue_purchase_orders} overdue`:comparisonText(summary.comparisons.purchase_order_count_change_percent,"PO"),href:"/purchasing?status=open",tone:"amber",icon:<StrokeIcon><circle cx="9" cy="20" r="1"/><circle cx="19" cy="20" r="1"/><path d="M3 4h2l2.5 11h11l2-7H7"/></StrokeIcon>},
    {label:"Low Stock Items",value:String(summary.metrics.low_stock_items+summary.metrics.out_of_stock_items),note:`${summary.metrics.out_of_stock_items} out of stock`,href:"/purchasing?view=low-stock",tone:"violet",icon:<StrokeIcon><path d="M6 3h12v18H6Z"/><path d="M9 8h6M9 12h6M9 16h3"/></StrokeIcon>},
    {label:"Stock Movements",value:String(summary.metrics.movement_count),note:comparisonText(summary.comparisons.movement_count_change_percent,"movement"),href:`/stock?days=${days}${locationId?`&location_id=${locationId}`:""}`,tone:"cyan",icon:<StrokeIcon><path d="M4 12h16M14 6l6 6-6 6"/></StrokeIcon>},
  ]:[];

  const chart=useMemo(()=>buildChart(history?.points||[]),[history]);
  const totalStatus=summary?Math.max(Object.values(summary.stock_status).reduce((sum,value)=>sum+value,0),1):1;
  const stops=summary?[summary.stock_status.in_stock/totalStatus*100,(summary.stock_status.in_stock+summary.stock_status.low_stock)/totalStatus*100,(summary.stock_status.in_stock+summary.stock_status.low_stock+summary.stock_status.out_of_stock)/totalStatus*100]:[0,0,0];
  const donutStyle={background:summary?`conic-gradient(#42bd73 0 ${stops[0]}%,#f7b928 ${stops[0]}% ${stops[1]}%,#ef5555 ${stops[1]}% ${stops[2]}%,#aeb9c5 ${stops[2]}% 100%)`:"conic-gradient(#e5eaf0 0 100%)"};

  return <AppShell title="Dashboard" description="Monitor inventory, procurement, receiving, and production from one workspace."><div className="dashboard-overview">
    <section className="dashboard-welcome"><div><h2><UserGreeting/></h2><p>{summary?`Operational snapshot updated ${formatDateTime(summary.as_of)}.`:"Loading the current operating picture."}</p></div><div className="dashboard-filters"><label><span>Location</span><select value={locationId} onChange={event=>setLocationId(event.target.value)}><option value="">All locations</option>{locations.map(location=><option key={location.id} value={location.id}>{location.code} — {location.name}</option>)}</select></label><label><span>Period</span><select value={days} onChange={event=>setDays(Number(event.target.value))}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option><option value={365}>365 days</option></select></label></div></section>

    <RoleWorkspace locationId={locationId} />

    {summaryError?<ErrorState title="Dashboard summary unavailable" message={summaryError} onRetry={()=>void loadSummary()}/>:summaryLoading?<LoadingState title="Loading dashboard summary" rows={3}/>:<section className="metric-grid" aria-label="Inventory summary">{metrics.map(metric=><Link className="metric-card metric-card-link" key={metric.label} href={metric.href}><div className={`metric-icon ${metric.tone}`}>{metric.icon}</div><div className="metric-copy"><div className="metric-label">{metric.label}</div><div className="metric-value">{metric.value}</div><div className="metric-note">{metric.note}</div></div></Link>)}</section>}

    <section className="dashboard-primary-grid">
      <article className="dashboard-panel"><div className="panel-header"><div><h3>Inventory Value History</h3><p>Actual value reconstructed from current balances and dated stock movements.</p></div><Link className="panel-link" href="/reports">Open reports</Link></div>{historyError?<ErrorState title="Valuation history unavailable" message={historyError} onRetry={()=>void loadHistory()}/>:historyLoading?<LoadingState title="Loading valuation history" rows={4}/>:<div className="chart-stage"><div className="chart-axis"><span>{formatMoney(chart.max)}</span><span>{formatMoney((chart.max+chart.min)*.75)}</span><span>{formatMoney((chart.max+chart.min)*.5)}</span><span>{formatMoney((chart.max+chart.min)*.25)}</span><span>{formatMoney(chart.min)}</span></div><div className="chart-gridlines"><span/><span/><span/><span/></div><svg className="chart-svg" viewBox="0 0 700 210" preserveAspectRatio="none" role="img" aria-label={`Inventory valuation over ${days} days`}><defs><linearGradient id="dashboardArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2f6fed" stopOpacity=".18"/><stop offset="1" stopColor="#2f6fed" stopOpacity="0"/></linearGradient></defs>{chart.area?<path d={chart.area} fill="url(#dashboardArea)"/>:null}{chart.line?<path d={chart.line} fill="none" stroke="#2f6fed" strokeWidth="3"/>:null}</svg><div className="chart-empty-note"><strong>{formatMoney(history?.current_value||0)}</strong><span>{history?.points.length?`${history.points.length} daily valuation points through ${formatDate(history.as_of)}.`:"No valuation history is available."}</span></div><div className="chart-labels"><span>{history?.points[0]?formatDate(history.points[0].date):"Start"}</span><span>{days} day period</span><span>{history?.points.at(-1)?formatDate(history.points.at(-1)!.date):"Current"}</span></div></div>}</article>
      <article className="dashboard-panel"><div className="panel-header"><div><h3>Stock Status</h3><p>Availability across the filtered active catalogue.</p></div><Link className="panel-link" href="/stock">View stock</Link></div>{summary?<div className="stock-panel-body"><div className="donut" style={donutStyle}><div className="donut-copy"><strong>{summary.metrics.total_products}</strong><span>Total items</span></div></div><div className="legend"><div className="legend-row"><span className="legend-dot" style={{background:"#42bd73"}}/><span>In stock</span><strong>{summary.stock_status.in_stock}</strong></div><div className="legend-row"><span className="legend-dot" style={{background:"#f7b928"}}/><span>Low stock</span><strong>{summary.stock_status.low_stock}</strong></div><div className="legend-row"><span className="legend-dot" style={{background:"#ef5555"}}/><span>Out of stock</span><strong>{summary.stock_status.out_of_stock}</strong></div><div className="legend-row"><span className="legend-dot" style={{background:"#aeb9c5"}}/><span>Inactive</span><strong>{summary.stock_status.inactive}</strong></div></div></div>:<LoadingState title="Loading stock status" rows={3}/>}</article>
    </section>

    <section className="dashboard-secondary-grid">
      <article className="dashboard-panel"><div className="panel-header"><div><h3>Recent Purchase Orders</h3><p>Latest procurement documents in the selected scope.</p></div><Link className="panel-link" href="/purchasing">View all</Link></div><table className="compact-table"><thead><tr><th>PO Number</th><th>Supplier</th><th>Status</th><th>Total</th></tr></thead><tbody>{summary?.recent_purchase_orders.length?summary.recent_purchase_orders.map(po=><tr key={po.id}><td><Link href={`/purchasing?purchase_order=${po.id}`}>{po.purchase_order_number}</Link></td><td>{po.supplier_name}</td><td><StatusBadge status={po.status}/></td><td>{formatMoney(po.total)}</td></tr>):<tr className="empty-row"><td colSpan={4}>No purchase orders in this scope.</td></tr>}</tbody></table></article>
      <article className="dashboard-panel"><div className="panel-header"><div><h3>Low Stock Alerts</h3><p>Largest shortages against configured minimums.</p></div><Link className="panel-link" href="/purchasing?view=low-stock">View all</Link></div>{summary?.low_stock.length?<div className="alert-list">{summary.low_stock.map(item=><Link className="alert-item" href={`/items?item=${item.id}`} key={item.id}><div className="small-icon"><StrokeIcon><path d="M12 3 2 21h20Z"/><path d="M12 9v5M12 18h.01"/></StrokeIcon></div><div className="list-copy"><strong>{item.sku} — {item.name}</strong><span>Minimum {formatQuantity(item.minimum_stock)} · short {formatQuantity(item.shortfall)}</span></div><div className="list-value">{formatQuantity(item.quantity)}</div></Link>)}</div>:<div className="empty-list"><div><strong>No low-stock alerts</strong><span>All configured items are above their reorder levels.</span></div></div>}</article>
      <article className="dashboard-panel"><div className="panel-header"><div><h3>Recent Activity</h3><p>Latest stock movements in the selected scope.</p></div><Link className="panel-link" href="/stock">View all</Link></div>{summary?.recent_movements.length?<div className="activity-list">{summary.recent_movements.map(movement=><Link className="activity-item" href={`/stock?movement=${movement.id}`} key={movement.id}><div className="small-icon"><StrokeIcon><path d="M4 12h16M14 6l6 6-6 6"/></StrokeIcon></div><div className="list-copy"><strong>{movement.sku} {Number(movement.quantity)>0?"received":"issued"}</strong><span>{formatDateTime(movement.created_at)} · {movement.location_name} · {movement.reason||"Stock movement"}</span></div><div className="list-value">{Number(movement.quantity)>0?"+":""}{formatQuantity(movement.quantity)}</div></Link>)}</div>:<div className="empty-list"><div><strong>No recent activity</strong><span>Completed stock transactions will appear here.</span></div></div>}</article>
    </section>

    <section className="quick-actions-row" aria-label="Quick actions"><Link className="quick-action-button primary-action" href="/receiving">Receive delivery</Link><Link className="quick-action-button" href="/purchasing">Create purchase order</Link><Link className="quick-action-button" href="/counts">Start stock count</Link><Link className="quick-action-button" href="/items">Add product</Link></section>
  </div></AppShell>;
}
