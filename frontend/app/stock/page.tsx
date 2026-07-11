"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "../../components/AppShell";
import { Can } from "../../components/SessionContext";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DataTable } from "../../components/DataTable";
import { FeedbackBanner } from "../../components/FeedbackBanner";
import { FormField, FormSection } from "../../components/FormField";
import { StatusBadge } from "../../components/StatusBadge";
import { StockLedgerPanel } from "../../components/StockLedgerPanel";
import { api } from "../../lib/api";
import { formatDateTime, formatMoney, formatQuantity } from "../../lib/formatters";

type Item={id:string;sku:string;name:string;allow_negative_stock:boolean;track_stock:boolean};
type Location={id:string;code:string;name:string;is_active:boolean};
type Balance={item_id:string;location_id:string;quantity:string;average_cost:string;updated_at:string};
type Movement={id:string;item_id:string;location_id:string;quantity:string;unit_cost:string;reason:string|null;created_at:string};
type PendingTransaction={path:string;body:Record<string,unknown>;summary:string}|null;

export default function Page(){
  const searchParams=useSearchParams();
  const[items,setItems]=useState<Item[]>([]);
  const[locations,setLocations]=useState<Location[]>([]);
  const[balances,setBalances]=useState<Balance[]>([]);
  const[moves,setMoves]=useState<Movement[]>([]);
  const[kind,setKind]=useState("receipt");
  const[locationFilter,setLocationFilter]=useState(searchParams.get("location_id")||"");
  const[itemFilter,setItemFilter]=useState(searchParams.get("item_id")||"");
  const[loading,setLoading]=useState(true);
  const[posting,setPosting]=useState(false);
  const[feedback,setFeedback]=useState<{tone:"success"|"error"|"warning";title:string;message?:string}|null>(null);
  const[pending,setPending]=useState<PendingTransaction>(null);

  const load=useCallback(async()=>{
    setLoading(true);
    try{
      const query=new URLSearchParams();if(locationFilter)query.set("location_id",locationFilter);if(itemFilter)query.set("item_id",itemFilter);
      const suffix=query.toString()?`?${query.toString()}`:"";
      const movementQuery=new URLSearchParams(query);movementQuery.set("limit","100");
      const[i,l,b,m]=await Promise.all([api<Item[]>("/items"),api<Location[]>("/locations"),api<Balance[]>(`/stock/balances${suffix}`),api<Movement[]>(`/stock/movements?${movementQuery.toString()}`)]);
      setItems(i);setLocations(l.filter(row=>row.is_active));setBalances(b);setMoves(m);
    }catch(error){setFeedback({tone:"error",title:"Stock data unavailable",message:(error as Error).message})}
    finally{setLoading(false)}
  },[itemFilter,locationFilter]);
  useEffect(()=>{void load()},[load]);

  const itemName=(id:string)=>items.find(row=>row.id===id);
  const locationName=(id:string)=>locations.find(row=>row.id===id);
  const currentBalance=useMemo(()=>new Map(balances.map(row=>[`${row.item_id}:${row.location_id}`,Number(row.quantity)])),[balances]);

  function prepare(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setFeedback(null);const form=new FormData(event.currentTarget);
    const itemId=String(form.get("item")),quantity=Number(form.get("quantity")),unitCost=Number(form.get("cost")||0),locationId=String(form.get("location")),destinationId=String(form.get("destination")||""),reason=String(form.get("reason")||"").trim();
    if(!Number.isFinite(quantity)||quantity===0){setFeedback({tone:"error",title:"Enter a valid non-zero quantity"});return}
    if(kind!=="adjustment"&&quantity<0){setFeedback({tone:"error",title:"Quantity must be positive",message:"Use Adjustment for signed quantity changes."});return}
    if(kind==="transfer"&&locationId===destinationId){setFeedback({tone:"error",title:"Source and destination must differ"});return}
    const item=itemName(itemId);const available=currentBalance.get(`${itemId}:${locationId}`)||0;
    if((kind==="issue"||kind==="transfer")&&available<quantity&&!item?.allow_negative_stock){setFeedback({tone:"error",title:"Insufficient stock",message:`Available quantity is ${formatQuantity(available)}. This item does not allow negative stock.`});return}
    let path="/stock/receipts";let body:Record<string,unknown>={location_id:locationId,reference:String(form.get("reference")||"")||null,notes:reason||null,idempotency_key:crypto.randomUUID(),lines:[{item_id:itemId,quantity,unit_cost:unitCost,reason:reason||null}]};
    if(kind==="issue")path="/stock/issues";
    if(kind==="adjustment"){path="/stock/adjustments";body={location_id:locationId,reference:String(form.get("reference")||"")||null,notes:reason||null,idempotency_key:crypto.randomUUID(),lines:[{item_id:itemId,quantity_delta:quantity,unit_cost:unitCost,reason:reason||"manual adjustment"}]}}
    if(kind==="transfer"){path="/stock/transfers";body={source_location_id:locationId,destination_location_id:destinationId,reference:String(form.get("reference")||"")||null,notes:reason||null,idempotency_key:crypto.randomUUID(),lines:[{item_id:itemId,quantity,unit_cost:unitCost,reason:reason||null}]}}
    setPending({path,body,summary:`${kind} ${formatQuantity(quantity)} ${item?.sku||"item"} at ${locationName(locationId)?.code||"location"}${kind==="transfer"?` to ${locationName(destinationId)?.code||"destination"}`:""}`});
  }

  async function post(){if(!pending)return;setPosting(true);try{await api(pending.path,{method:"POST",body:JSON.stringify(pending.body)});setFeedback({tone:"success",title:"Stock transaction posted",message:pending.summary});setPending(null);await load()}catch(error){setFeedback({tone:"error",title:"Transaction could not be posted",message:(error as Error).message});setPending(null)}finally{setPosting(false)}}

  return <AppShell title="Stock" description="Post controlled stock transactions and review balances, documents, and immutable ledger history.">
    <Can permission="inventory.*"><section className="card"><div className="topline"><div><h2>Post stock transaction</h2><p>Transactions are confirmed before posting and use idempotency protection against duplicate submissions.</p></div><StatusBadge status={kind}/></div>
      <form onSubmit={prepare}><FormSection title="Transaction details"><FormField label="Transaction type" name="stock-kind" required><select value={kind} onChange={event=>setKind(event.target.value)}><option value="receipt">Receipt</option><option value="issue">Issue</option><option value="transfer">Transfer</option><option value="adjustment">Adjustment</option></select></FormField><FormField label={kind==="transfer"?"Source location":"Location"} name="stock-location" required><select name="location" required defaultValue={locationFilter}><option value="">Select location</option>{locations.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></FormField>{kind==="transfer"?<FormField label="Destination location" name="stock-destination" required><select name="destination" required><option value="">Select destination</option>{locations.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></FormField>:<span/>}<FormField label="Item" name="stock-item" required><select name="item" required defaultValue={itemFilter}><option value="">Select item</option>{items.filter(row=>row.track_stock).map(row=><option key={row.id} value={row.id}>{row.sku} — {row.name}{row.allow_negative_stock?" · negative allowed":""}</option>)}</select></FormField><FormField label={kind==="adjustment"?"Quantity delta":"Quantity"} name="stock-quantity" required hint={kind==="adjustment"?"Use a positive or negative signed adjustment.":"Enter a positive transaction quantity."}><input name="quantity" type="number" step="0.0001" required/></FormField><FormField label="Unit cost" name="stock-cost" optional><input name="cost" type="number" step="0.0001" min="0"/></FormField><FormField label="Reference" name="stock-reference" optional><input name="reference" placeholder="Invoice, memo, or external reference"/></FormField><FormField label="Reason or notes" name="stock-reason" required={kind==="adjustment"}><input name="reason" required={kind==="adjustment"}/></FormField></FormSection><div className="form-actions"><button className="primary">Review transaction</button></div></form>{feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}</section></Can>

    <section className="card section-gap"><div className="topline"><div><h2>Current balances</h2><p>Filter the workspace by item or location. Negative balances are visibly flagged.</p></div><div className="stock-filters"><select value={locationFilter} onChange={event=>setLocationFilter(event.target.value)}><option value="">All locations</option>{locations.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select><select value={itemFilter} onChange={event=>setItemFilter(event.target.value)}><option value="">All items</option>{items.map(row=><option key={row.id} value={row.id}>{row.sku} — {row.name}</option>)}</select></div></div>
      <DataTable columns={["Item","Location","Quantity","Average cost","Inventory value","Negative policy"]} rows={balances.map(row=>{const item=itemName(row.item_id),location=locationName(row.location_id);return [<Link className="catalogue-link" href={`/items/${row.item_id}`} key={row.item_id}>{item?.sku||row.item_id} — {item?.name||""}</Link>,<Link className="catalogue-link" href={`/locations/${row.location_id}`} key={row.location_id}>{location?.code||row.location_id}</Link>,<span className={Number(row.quantity)<0?"negative":""} key="qty">{formatQuantity(row.quantity)}</span>,formatMoney(row.average_cost),formatMoney(Number(row.quantity)*Number(row.average_cost)),item?.allow_negative_stock?"Allowed":"Blocked"]})} rowIds={balances.map(row=>`${row.item_id}:${row.location_id}`)} loading={loading} searchPlaceholder="Search balances" exportFileName="hidden-oasis-stock-balances" emptyTitle="No balances found" emptyMessage="No stock balances match the selected filters."/>
    </section>

    <StockLedgerPanel items={items} locations={locations} initialItemId={itemFilter} initialLocationId={locationFilter}/>

    <section className="card section-gap"><h2>Recent movements</h2><DataTable columns={["Date","Item","Location","Quantity","Cost","Reason"]} rows={moves.map(row=>[formatDateTime(row.created_at),itemName(row.item_id)?.sku||row.item_id,locationName(row.location_id)?.code||row.location_id,<span className={Number(row.quantity)<0?"negative":"positive"} key="movement-qty">{Number(row.quantity)>0?"+":""}{formatQuantity(row.quantity)}</span>,formatMoney(row.unit_cost),row.reason||"—"])} rowIds={moves.map(row=>row.id)} loading={loading} searchPlaceholder="Search movement history" exportFileName="hidden-oasis-stock-movements" emptyTitle="No movements found" emptyMessage="No stock movements match the selected filters."/></section>

    <ConfirmDialog open={Boolean(pending)} title="Post this stock transaction?" description={pending?.summary} confirmLabel="Post transaction" busy={posting} onConfirm={()=>void post()} onCancel={()=>setPending(null)}/>
  </AppShell>
}
