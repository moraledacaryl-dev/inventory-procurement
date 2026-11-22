"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { stableDraftIdempotency, type DraftIdempotencyState } from "../../lib/draftIdempotency";
import { formatDateTime, formatMoney, formatQuantity } from "../../lib/formatters";

type Item={id:string;sku:string;name:string;allow_negative_stock:boolean;track_stock:boolean};
type Location={id:string;code:string;name:string;is_active:boolean};
type Balance={item_id:string;location_id:string;quantity:string;average_cost:string;updated_at:string};
type Availability={item_id:string;location_id:string;physical_quantity:string;reserved_quantity:string;available_quantity:string};
type Movement={id:string;item_id:string;location_id:string;quantity:string;unit_cost:string;reason:string|null;created_at:string};
type PendingTransaction={path:string;body:Record<string,unknown>;summary:string}|null;

export default function Page(){
  const searchParams=useSearchParams();
  const[items,setItems]=useState<Item[]>([]);
  const[locations,setLocations]=useState<Location[]>([]);
  const[balances,setBalances]=useState<Balance[]>([]);
  const[availability,setAvailability]=useState<Availability[]>([]);
  const[draftSource,setDraftSource]=useState(searchParams.get("location_id")||"");
  const[draftItem,setDraftItem]=useState(searchParams.get("item_id")||"");
  const[moves,setMoves]=useState<Movement[]>([]);
  const[kind,setKind]=useState("receipt");
  const[locationFilter,setLocationFilter]=useState(searchParams.get("location_id")||"");
  const[itemFilter,setItemFilter]=useState(searchParams.get("item_id")||"");
  const[loading,setLoading]=useState(true);
  const[posting,setPosting]=useState(false);
  const[feedback,setFeedback]=useState<{tone:"success"|"error"|"warning";title:string;message?:string}|null>(null);
  const[pending,setPending]=useState<PendingTransaction>(null);
  const latestLoad=useRef(0);
  const transactionRequest=useRef<DraftIdempotencyState|null>(null);

  const load=useCallback(async()=>{
    const request=++latestLoad.current;
    setLoading(true);
    try{
      const query=new URLSearchParams();if(locationFilter)query.set("location_id",locationFilter);if(itemFilter)query.set("item_id",itemFilter);
      const suffix=query.toString()?`?${query.toString()}`:"";
      const movementQuery=new URLSearchParams(query);movementQuery.set("limit","100");
      const[i,l,b,m,a]=await Promise.all([api<Item[]>("/items"),api<Location[]>("/locations"),api<Balance[]>(`/stock/balances${suffix}`),api<Movement[]>(`/stock/movements?${movementQuery.toString()}`),api<Availability[]>(`/availability${suffix}`)]);
      if(request===latestLoad.current){setItems(i);setLocations(l.filter(row=>row.is_active));setBalances(b);setMoves(m);setAvailability(a);}
    }catch(error){if(request===latestLoad.current)setFeedback({tone:"error",title:"Stock data unavailable",message:(error as Error).message})}
    finally{if(request===latestLoad.current)setLoading(false)}
  },[itemFilter,locationFilter]);
  useEffect(()=>{void load()},[load]);

  const itemName=(id:string)=>items.find(row=>row.id===id);
  const locationName=(id:string)=>locations.find(row=>row.id===id);
  const currentBalance=useMemo(()=>new Map(balances.map(row=>[`${row.item_id}:${row.location_id}`,Number(row.quantity)])),[balances]);
  const availableStock=useMemo(()=>new Map(availability.map(row=>[`${row.item_id}:${row.location_id}`,{available:Number(row.available_quantity),reserved:Number(row.reserved_quantity),physical:Number(row.physical_quantity)}])),[availability]);
  const selectedAvailability=availableStock.get(`${draftItem}:${draftSource}`);

  function prepare(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setFeedback(null);const form=new FormData(event.currentTarget);
    const itemId=String(form.get("item")),quantity=Number(form.get("quantity")),unitCost=Number(form.get("cost")||0),locationId=String(form.get("location")),destinationId=String(form.get("destination")||""),reason=String(form.get("reason")||"").trim();
    if(!Number.isFinite(quantity)||quantity===0){setFeedback({tone:"error",title:"Enter a valid non-zero quantity"});return}
    if(kind!=="adjustment"&&quantity<0){setFeedback({tone:"error",title:"Quantity must be positive",message:"Use Adjustment for signed quantity changes."});return}
    if(!Number.isFinite(unitCost)||unitCost<0){setFeedback({tone:"error",title:"Unit cost cannot be negative"});return}
    if(kind==="transfer"&&locationId===destinationId){setFeedback({tone:"error",title:"Source and destination must differ"});return}
    const item=itemName(itemId);const physical=currentBalance.get(`${itemId}:${locationId}`)||0;
    const stock=availableStock.get(`${itemId}:${locationId}`);
    const available=stock?.available??physical;
    const reserved=stock?.reserved??0;
    if((kind==="issue"||kind==="transfer")&&available<quantity&&(!item?.allow_negative_stock||reserved>0)){
      setFeedback({tone:"error",title:"Not enough free stock",message:`Free to use: ${formatQuantity(available)}. Reserved stock cannot be issued or transferred.`});return
    }
    let path="/stock/receipts";let body:Record<string,unknown>={location_id:locationId,reference:String(form.get("reference")||"")||null,notes:reason||null,lines:[{item_id:itemId,quantity,unit_cost:unitCost,reason:reason||null}]};
    if(kind==="issue")path="/stock/issues";
    if(kind==="adjustment"){path="/stock/adjustments";body={location_id:locationId,reference:String(form.get("reference")||"")||null,notes:reason||null,lines:[{item_id:itemId,quantity_delta:quantity,unit_cost:unitCost,reason:reason||"manual adjustment"}]}}
    if(kind==="transfer"){path="/stock/transfers";body={source_location_id:locationId,destination_location_id:destinationId,reference:String(form.get("reference")||"")||null,notes:reason||null,lines:[{item_id:itemId,quantity,unit_cost:unitCost,reason:reason||null}]}}
    const request=stableDraftIdempotency({path,body},transactionRequest.current);
    transactionRequest.current=request;
    setPending({path,body:{...body,idempotency_key:request.key},summary:`${kind} ${formatQuantity(quantity)} ${item?.sku||"item"} at ${locationName(locationId)?.code||"location"}${kind==="transfer"?` to ${locationName(destinationId)?.code||"destination"}`:""}`});
  }

  async function post(){if(!pending)return;setPosting(true);try{await api(pending.path,{method:"POST",body:JSON.stringify(pending.body)});setFeedback({tone:"success",title:"Stock transaction posted",message:pending.summary});transactionRequest.current=null;setPending(null);await load()}catch(error){setFeedback({tone:"error",title:"Transaction not confirmed",message:`${(error as Error).message} Check the stock ledger or retry this confirmation. Retrying reuses the same transaction key.`})}finally{setPosting(false)}}

  return <AppShell title="Stock" description="Check stock at each location or record what happened to an item.">

    <Can permission="inventory.*"><details className="card workflow-disclosure stock-guided-action"><summary><div className="topline"><div><h2>Record a stock movement</h2><p>Use this when stock was used, moved, received without a purchase order, or corrected.</p></div><StatusBadge status={kind}/></div><span className="disclosure-mark" aria-hidden="true">+</span></summary>
    <div className="workflow-disclosure-body">
      <ol className="workflow-steps" aria-label="Stock movement steps"><li className="active">1. Choose action</li><li>2. Enter details</li><li>3. Review &amp; post</li></ol>
      <form onSubmit={prepare}>
        <FormSection title="What happened to the stock?">
          <FormField label="Stock action" name="stock-kind" required>
            <select value={kind} onChange={event=>setKind(event.target.value)}>
              <option value="receipt">Received stock (no PO)</option>
              <option value="issue">Used or issued stock</option>
              <option value="transfer">Moved between locations</option>
              <option value="adjustment">Correct the stock balance</option>
            </select>
          </FormField>
        </FormSection>
        <p className="workflow-hint stock-action-help" role="status">
          {kind==="receipt"?<>A delivery linked to a purchase order must be recorded in <Link href="/receiving">Receiving</Link>. Use this only for stock received without a PO.</>:
            kind==="issue"?"Choose this when an item was taken from stock for use. This decreases the available stock.":
            kind==="transfer"?"Choose the storage area the item came from and where it was moved. This does not create new stock.":
            "Use only when correcting a wrong recorded balance. Enter a positive number to add or a negative number to remove. Write the reason."}
        </p>
        <FormSection title="Item, location and quantity">
          <FormField label={kind==="transfer"?"Moved from":"Storage location"} name="stock-location" required>
            <select name="location" required value={draftSource} onChange={event=>setDraftSource(event.target.value)}><option value="">Choose storage area</option>{locations.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select>
          </FormField>
          {kind==="transfer"?<FormField label="Moved to" name="stock-destination" required>
            <select name="destination" required><option value="">Choose destination</option>{locations.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select>
          </FormField>:<span/>}
          <FormField label="Item" name="stock-item" required>
            <select name="item" required value={draftItem} onChange={event=>setDraftItem(event.target.value)}><option value="">Choose item</option>{items.filter(row=>row.track_stock).map(row=><option key={row.id} value={row.id}>{row.sku} — {row.name}</option>)}</select>
          </FormField>
          <FormField label={kind==="adjustment"?"Change amount (+ or −)":"Quantity"} name="stock-quantity" required hint={kind==="adjustment"?"Positive adds stock; negative removes stock.":"Enter a positive quantity."}>
            <input name="quantity" type="number" step="0.0001" inputMode="decimal" min={kind==="adjustment"?undefined:"0.0001"} required placeholder="Enter quantity"/>
          </FormField>
          {(kind==="receipt"||kind==="adjustment")?<FormField label="Unit cost" name="stock-cost" optional>
            <input name="cost" type="number" step="0.0001" min="0" inputMode="decimal" placeholder="Cost per item"/>
          </FormField>:null}
          <FormField label="Reference (optional)" name="stock-reference" optional>
            <input name="reference" placeholder="Invoice or document number"/>
          </FormField>
          <FormField label={kind==="adjustment"?"Why is this balance wrong?":"Reason or notes"} name="stock-reason" required={kind==="adjustment"}>
            <input name="reason" required={kind==="adjustment"} placeholder={kind==="adjustment"?"Explain what was counted or corrected":"What happened?"}/>
          </FormField>
        </FormSection>
        {selectedAvailability?<p className="workflow-note" role="status"><strong>Available: {formatQuantity(selectedAvailability.available)}</strong><span>In stock: {formatQuantity(selectedAvailability.physical)} · Set aside for other work: {formatQuantity(selectedAvailability.reserved)}. Do not issue items that are reserved.</span></p>:null}
        <div className="form-actions"><button className="primary" disabled={posting}>Check before posting</button></div>
      </form>
      {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}
    </div></details></Can>

    <section className="card section-gap"><div className="topline"><div><h2>What is in stock?</h2><p>Find an item or storage area below. “Quantity” is the recorded stock on hand. Check available stock before issuing or transferring.</p></div><div className="stock-filters"><select value={locationFilter} onChange={event=>setLocationFilter(event.target.value)}><option value="">All locations</option>{locations.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select><select value={itemFilter} onChange={event=>setItemFilter(event.target.value)}><option value="">All items</option>{items.map(row=><option key={row.id} value={row.id}>{row.sku} — {row.name}</option>)}</select></div></div>
      <DataTable columns={["Item","Location","Quantity","Average cost","Inventory value","Negative policy"]} rows={balances.map(row=>{const item=itemName(row.item_id),location=locationName(row.location_id);return [<Link className="catalogue-link" href={`/items/${row.item_id}`} key={row.item_id}>{item?.sku||row.item_id} — {item?.name||""}</Link>,<Link className="catalogue-link" href={`/locations/${row.location_id}`} key={row.location_id}>{location?.code||row.location_id}</Link>,<span className={Number(row.quantity)<0?"negative":""} key="qty">{formatQuantity(row.quantity)}</span>,formatMoney(row.average_cost),formatMoney(Number(row.quantity)*Number(row.average_cost)),item?.allow_negative_stock?"Allowed":"Blocked"]})} rowIds={balances.map(row=>`${row.item_id}:${row.location_id}`)} loading={loading} searchPlaceholder="Search balances" exportFileName="hidden-oasis-stock-balances" emptyTitle="No balances found" emptyMessage="No stock balances match the selected filters."/>
    </section>

    <StockLedgerPanel items={items} locations={locations} initialItemId={itemFilter} initialLocationId={locationFilter}/>

    <section className="card section-gap"><h2>Recent movements</h2><DataTable columns={["Date","Item","Location","Quantity","Cost","Reason"]} rows={moves.map(row=>[formatDateTime(row.created_at),itemName(row.item_id)?.sku||row.item_id,locationName(row.location_id)?.code||row.location_id,<span className={Number(row.quantity)<0?"negative":"positive"} key="movement-qty">{Number(row.quantity)>0?"+":""}{formatQuantity(row.quantity)}</span>,formatMoney(row.unit_cost),row.reason||"—"])} rowIds={moves.map(row=>row.id)} loading={loading} searchPlaceholder="Search movement history" exportFileName="hidden-oasis-stock-movements" emptyTitle="No movements found" emptyMessage="No stock movements match the selected filters."/></section>

    <ConfirmDialog open={Boolean(pending)} title="Post this stock transaction?" description={pending?.summary} confirmLabel="Post transaction" busy={posting} onConfirm={()=>void post()} onCancel={()=>setPending(null)}>{pending&&feedback?.tone==="error"?<p role="alert" className="field-error">{feedback.message||feedback.title}</p>:null}</ConfirmDialog>
  </AppShell>
}
