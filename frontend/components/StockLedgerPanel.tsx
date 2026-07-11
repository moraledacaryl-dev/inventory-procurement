"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { DataTable } from "./DataTable";
import { ErrorState, LoadingState } from "./AsyncState";
import { StatusBadge } from "./StatusBadge";
import { api } from "../lib/api";
import { formatDateTime, formatMoney, formatQuantity } from "../lib/formatters";

type Item={id:string;sku:string;name:string};
type Location={id:string;code:string;name:string};
type LedgerRow={id:string;document_id:string;document_number:string;document_type:string;document_status:string;reference:string|null;item_id:string;sku:string;item_name:string;location_id:string;location_code:string;location_name:string;quantity:string;unit_cost:string;line_value:string;running_quantity:string;reason:string|null;created_at:string;posted_at:string};
type LedgerResponse={summary:{movement_count:number;net_quantity:string;net_value:string;document_count:number};rows:LedgerRow[]};

export function StockLedgerPanel({items,locations,initialItemId="",initialLocationId=""}:{items:Item[];locations:Location[];initialItemId?:string;initialLocationId?:string}){
  const[itemId,setItemId]=useState(initialItemId);
  const[locationId,setLocationId]=useState(initialLocationId);
  const[documentType,setDocumentType]=useState("");
  const[dateFrom,setDateFrom]=useState("");
  const[dateTo,setDateTo]=useState("");
  const[data,setData]=useState<LedgerResponse|null>(null);
  const[loading,setLoading]=useState(true);
  const[error,setError]=useState("");

  const query=useMemo(()=>{const params=new URLSearchParams({limit:"500"});if(itemId)params.set("item_id",itemId);if(locationId)params.set("location_id",locationId);if(documentType)params.set("document_type",documentType);if(dateFrom)params.set("date_from",`${dateFrom}T00:00:00Z`);if(dateTo)params.set("date_to",`${dateTo}T23:59:59Z`);return params.toString()},[itemId,locationId,documentType,dateFrom,dateTo]);
  const load=useCallback(async()=>{setLoading(true);setError("");try{setData(await api<LedgerResponse>(`/stock/ledger?${query}`))}catch(exception){setError((exception as Error).message)}finally{setLoading(false)}},[query]);
  useEffect(()=>{void load()},[load]);

  return <section className="card section-gap">
    <div className="topline"><div><h2>Stock ledger</h2><p>Immutable movement lines with document, reference, signed value, and running quantity within the selected scope.</p></div></div>
    <div className="ledger-filters"><label><span>Item</span><select value={itemId} onChange={event=>setItemId(event.target.value)}><option value="">All items</option>{items.map(row=><option key={row.id} value={row.id}>{row.sku} — {row.name}</option>)}</select></label><label><span>Location</span><select value={locationId} onChange={event=>setLocationId(event.target.value)}><option value="">All locations</option>{locations.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></label><label><span>Document type</span><select value={documentType} onChange={event=>setDocumentType(event.target.value)}><option value="">All types</option><option value="receipt">Receipt</option><option value="issue">Issue</option><option value="transfer">Transfer</option><option value="adjustment">Adjustment</option><option value="count_adjustment">Count adjustment</option><option value="goods_receipt">Goods receipt</option><option value="production">Production</option></select></label><label><span>From</span><input type="date" value={dateFrom} onChange={event=>setDateFrom(event.target.value)}/></label><label><span>To</span><input type="date" value={dateTo} onChange={event=>setDateTo(event.target.value)}/></label></div>
    {error?<ErrorState title="Ledger unavailable" message={error} onRetry={()=>void load()}/>:loading&&!data?<LoadingState title="Loading stock ledger" rows={5}/>:<><div className="ledger-summary"><div><span>Movements</span><strong>{data?.summary.movement_count||0}</strong></div><div><span>Documents</span><strong>{data?.summary.document_count||0}</strong></div><div><span>Net quantity</span><strong>{formatQuantity(data?.summary.net_quantity||0)}</strong></div><div><span>Net value</span><strong>{formatMoney(data?.summary.net_value||0)}</strong></div></div><DataTable columns={["Date","Document","Type","Reference","Item","Location","Quantity","Running qty","Unit cost","Line value","Reason"]} rows={(data?.rows||[]).map(row=>[formatDateTime(row.created_at),<Link className="catalogue-link" href={`/stock/documents/${row.document_id}`} key={row.document_id}>{row.document_number}</Link>,<StatusBadge key={`${row.id}-type`} status={row.document_type}/>,row.reference||"—",<Link className="catalogue-link" href={`/items/${row.item_id}`} key={row.item_id}>{row.sku} — {row.item_name}</Link>,<Link className="catalogue-link" href={`/locations/${row.location_id}`} key={row.location_id}>{row.location_code}</Link>,<span className={Number(row.quantity)<0?"negative":"positive"} key={`${row.id}-qty`}>{Number(row.quantity)>0?"+":""}{formatQuantity(row.quantity)}</span>,formatQuantity(row.running_quantity),formatMoney(row.unit_cost),formatMoney(row.line_value),row.reason||"—"])} rowIds={(data?.rows||[]).map(row=>row.id)} loading={loading} searchPlaceholder="Search document, item, location, reference, or reason" exportFileName="hidden-oasis-stock-ledger" emptyTitle="No ledger rows found" emptyMessage="No stock movements match the selected filters."/></>}
  </section>;
}
