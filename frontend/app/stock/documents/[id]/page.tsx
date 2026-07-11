"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "../../../../components/AppShell";
import { ErrorState, LoadingState } from "../../../../components/AsyncState";
import { StatusBadge } from "../../../../components/StatusBadge";
import { api } from "../../../../lib/api";
import { formatDateTime, formatMoney, formatQuantity } from "../../../../lib/formatters";

type DocumentDetail={
  document:{id:string;document_number:string;document_type:string;status:string;reference:string|null;notes:string|null;posted_by_user_id:string;posted_at:string;reversed_document_id:string|null;idempotency_key:string|null};
  summary:{line_count:number;net_quantity:string;net_value:string};
  lines:{id:string;line_number:number;item_id:string;sku:string;item_name:string;location_id:string;location_code:string;location_name:string;quantity:string;unit_cost:string;line_value:string;reason:string|null;created_at:string}[];
};

export default function StockDocumentPage(){
  const{id}=useParams<{id:string}>();
  const[data,setData]=useState<DocumentDetail|null>(null);
  const[loading,setLoading]=useState(true);
  const[error,setError]=useState("");
  const load=useCallback(async()=>{setLoading(true);setError("");try{setData(await api<DocumentDetail>(`/stock/documents/${id}`))}catch(exception){setError((exception as Error).message)}finally{setLoading(false)}},[id]);
  useEffect(()=>{void load()},[load]);

  if(error)return <AppShell title="Stock document"><ErrorState title="Stock document unavailable" message={error} onRetry={()=>void load()}/></AppShell>;
  if(loading||!data)return <AppShell title="Stock document"><LoadingState title="Loading stock document" rows={5}/></AppShell>;

  return <AppShell title={data.document.document_number} description="Immutable stock document and movement-line audit detail.">
    <div className="document-detail-header"><div><Link href="/stock" className="back-link">← Stock ledger</Link><div className="item-detail-title"><h2>{data.document.document_number}</h2><StatusBadge status={data.document.document_type}/><StatusBadge status={data.document.status}/></div><p>Posted {formatDateTime(data.document.posted_at)}</p></div></div>
    <section className="document-metrics"><div><span>Lines</span><strong>{data.summary.line_count}</strong></div><div><span>Net quantity</span><strong>{formatQuantity(data.summary.net_quantity)}</strong></div><div><span>Net value</span><strong>{formatMoney(data.summary.net_value)}</strong></div></section>
    <section className="document-detail-grid"><article className="card"><h2>Document controls</h2><dl className="document-facts"><div><dt>Type</dt><dd>{data.document.document_type}</dd></div><div><dt>Status</dt><dd>{data.document.status}</dd></div><div><dt>External reference</dt><dd>{data.document.reference||"—"}</dd></div><div><dt>Notes</dt><dd>{data.document.notes||"—"}</dd></div><div><dt>Posted by user ID</dt><dd>{data.document.posted_by_user_id}</dd></div><div><dt>Idempotency key</dt><dd>{data.document.idempotency_key||"—"}</dd></div><div><dt>Reversed document</dt><dd>{data.document.reversed_document_id?<Link href={`/stock/documents/${data.document.reversed_document_id}`}>{data.document.reversed_document_id}</Link>:"—"}</dd></div></dl></article><article className="card"><h2>Audit statement</h2><div className="audit-statement"><strong>This document is posted and immutable.</strong><p>Corrections must be represented by a separate controlled reversal or adjustment document. Existing movement lines are never edited or deleted.</p></div></article></section>
    <section className="card section-gap"><div className="topline"><div><h2>Movement lines</h2><p>Every signed stock and value effect created by this document.</p></div></div><div className="table-wrap"><table><thead><tr><th>Line</th><th>Date</th><th>Item</th><th>Location</th><th>Quantity</th><th>Unit cost</th><th>Line value</th><th>Reason</th></tr></thead><tbody>{data.lines.map(row=><tr key={row.id}><td>{row.line_number}</td><td>{formatDateTime(row.created_at)}</td><td><Link href={`/items/${row.item_id}`}>{row.sku} — {row.item_name}</Link></td><td><Link href={`/locations/${row.location_id}`}>{row.location_code} — {row.location_name}</Link></td><td className={Number(row.quantity)<0?"negative":"positive"}>{Number(row.quantity)>0?"+":""}{formatQuantity(row.quantity)}</td><td>{formatMoney(row.unit_cost)}</td><td>{formatMoney(row.line_value)}</td><td>{row.reason||"—"}</td></tr>)}</tbody></table></div></section>
  </AppShell>;
}
