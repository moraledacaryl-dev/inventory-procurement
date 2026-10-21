"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Can, useSession } from "../../components/SessionContext";
import { DataTable } from "../../components/DataTable";
import { ErrorState, LoadingState } from "../../components/AsyncState";
import { FeedbackBanner } from "../../components/FeedbackBanner";
import { FormField, FormSection } from "../../components/FormField";
import { InventoryControlPanel } from "../../components/InventoryControlPanel";
import { StatusBadge } from "../../components/StatusBadge";
import { api } from "../../lib/api";
import { formatDate, formatMoney, formatQuantity } from "../../lib/formatters";

type Item={id:string;sku:string;name:string};
type Location={id:string;code:string;name:string;is_active:boolean};
type Supplier={id:string;code:string;name:string};
type Lot={id:string;item_id:string;lot_number:string;expiry_date:string|null;status:string};
type Availability={item_id:string;location_id:string;physical_quantity:string;reserved_quantity:string;available_quantity:string};
type Expiry={lot_id:string;item_id:string;lot_number:string;location_id:string;quantity:string;expiry_date:string;days_to_expiry:number;status:string};
type Valuation={item_id:string;location_id:string;quantity:string;average_cost:string;inventory_value:string};
type Feedback={tone:"success"|"error"|"warning"|"info";title:string;message?:string}|null;

export default function Page(){
  return <><InventoryOperationsContent/></AppShell>;
}

function InventoryOperationsContent(){
  const {can,loading:sessionLoading}=useSession();
  const[items,setItems]=useState<Item[]>([]);
  const[locations,setLocations]=useState<Location[]>([]);
  const[suppliers,setSuppliers]=useState<Supplier[]>([]);
  const[lots,setLots]=useState<Lot[]>([]);
  const[availability,setAvailability]=useState<Availability[]>([]);
  const[expiry,setExpiry]=useState<Expiry[]>([]);
  const[valuation,setValuation]=useState<Valuation[]>([]);
  const[loading,setLoading]=useState(true);
  const[error,setError]=useState("");
  const[busy,setBusy]=useState(false);
  const[feedback,setFeedback]=useState<Feedback>(null);
  const[optionalFailures,setOptionalFailures]=useState<string[]>([]);
  const[expiryAvailable,setExpiryAvailable]=useState(false);
  const[valuationAvailable,setValuationAvailable]=useState(false);

  const load=useCallback(async()=>{
    if(sessionLoading)return;
    setLoading(true);setError("");setOptionalFailures([]);
    try{
      // Core stock data must load; role-restricted supplements are independent.
      const[i,l,lot,a]=await Promise.all([
        api<Item[]>("/items"),api<Location[]>("/locations"),
        api<Lot[]>("/lots"),api<Availability[]>("/availability"),
      ]);
      setItems(i);setLocations(l.filter(row=>row.is_active));setLots(lot);setAvailability(a);
      const[s,e,v]=await Promise.allSettled([
        can("suppliers.read")?api<Supplier[]>("/suppliers"):Promise.resolve([] as Supplier[]),
        can("reports.read")?api<Expiry[]>("/reports/expiry?days=60"):Promise.resolve([] as Expiry[]),
        can("reports.read")?api<Valuation[]>("/reports/valuation"):Promise.resolve([] as Valuation[]),
      ]);
      setSuppliers(s.status==="fulfilled"?s.value:[]);
      setExpiry(e.status==="fulfilled"?e.value:[]);
      setValuation(v.status==="fulfilled"?v.value:[]);
      setExpiryAvailable(can("reports.read")&&e.status==="fulfilled");
      setValuationAvailable(can("reports.read")&&v.status==="fulfilled");
      setOptionalFailures([
        ...(s.status==="rejected"?["Suppliers"]:[]),
        ...(e.status==="rejected"?["Expiry report"]:[]),
        ...(v.status==="rejected"?["Valuation report"]:[]),
      ]);
    }catch(exception){setError((exception as Error).message)}
    finally{setLoading(false)}
  },[can,sessionLoading]);
  useEffect(()=>{void load()},[load]);

  const itemName=(id:string)=>items.find(row=>row.id===id)?.sku||id;
  const locationName=(id:string)=>locations.find(row=>row.id===id)?.code||id;

  async function run(action:()=>Promise<unknown>,title:string,message?:string){setBusy(true);setFeedback(null);try{await action();setFeedback({tone:"success",title,message});await load()}catch(exception){setFeedback({tone:"error",title:"Action could not be completed",message:(exception as Error).message})}finally{setBusy(false)}}
  async function createLot(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget,data=new FormData(form);await run(()=>api("/lots",{method:"POST",body:JSON.stringify({item_id:data.get("item"),lot_number:data.get("lot_number"),manufactured_date:data.get("manufactured_date")||null,expiry_date:data.get("expiry_date")||null,supplier_id:data.get("supplier")||null})}),"Lot created","The lot is available for traceable stock transactions.");form.reset()}
  async function postLotTransaction(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget,data=new FormData(form);await run(()=>api("/lot-transactions",{method:"POST",body:JSON.stringify({lot_id:data.get("lot"),location_id:data.get("location"),quantity:Number(data.get("quantity")),unit_cost:Number(data.get("unit_cost")||0),transaction_type:data.get("type"),reason:data.get("reason")||null,idempotency_key:crypto.randomUUID()})}),"Lot transaction posted","The lot balance and stock ledger were updated together.");form.reset()}
  async function reserve(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget,data=new FormData(form);await run(()=>api("/reservations",{method:"POST",body:JSON.stringify({item_id:data.get("item"),location_id:data.get("location"),quantity:Number(data.get("quantity")),reference_type:data.get("reference_type"),reference_id:data.get("reference_id")})}),"Stock reserved","Available quantity now excludes the reservation.");form.reset()}

  if(error)return <ErrorState title="Inventory operations unavailable" message={error} onRetry={()=>void load()}/>;
  if((loading||sessionLoading)&&!items.length)return <LoadingState title="Loading inventory controls" rows={6}/>;

  const availableTotal=availability.reduce((sum,row)=>sum+Number(row.available_quantity),0);
  const reservedTotal=availability.reduce((sum,row)=>sum+Number(row.reserved_quantity),0);
  const inventoryValue=valuation.reduce((sum,row)=>sum+Number(row.inventory_value),0);

  return <AppShell title="Inventory Operations" description="Transfers, adjustments, waste, and expiry.">
    <section className="operations-metrics"><div><span>Available stock</span><strong>{formatQuantity(availableTotal)}</strong><small>Physical less active reservations</small></div><div><span>Reserved stock</span><strong>{formatQuantity(reservedTotal)}</strong><small>Committed to active references</small></div><div><span>Near expiry</span><strong>{expiryAvailable?expiry.length:"—"}</strong><small>{expiryAvailable?"Lots expiring within 60 days":"Reporting unavailable"}</small></div><div><span>Inventory value</span><strong>{valuationAvailable?formatMoney(inventoryValue):"—"}</strong><small>{valuationAvailable?"Weighted-average valuation":"Reporting unavailable"}</small></div></section>

    {optionalFailures.length?<FeedbackBanner tone="warning" title="Supplementary information unavailable" message={optionalFailures.join(", ")}/>:null}
    {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}

    <InventoryControlPanel items={items} locations={locations} lots={lots} onChanged={load}/>

    <section className="traceability-grid section-gap">
      <Can permission="inventory.*"><details className="card workflow-disclosure"><summary><div><h2>Create traceable lot</h2><p className="section-copy">Track an item by batch and expiry date.</p></div><span className="disclosure-mark" aria-hidden="true">+</span></summary><div className="workflow-disclosure-body"><form onSubmit={createLot}><FormSection title="Lot identity"><FormField label="Item" name="lot-item" required><select name="item" required defaultValue=""><option value="">Select item</option>{items.map(row=><option key={row.id} value={row.id}>{row.sku} — {row.name}</option>)}</select></FormField><FormField label="Lot number" name="lot-number" required><input name="lot_number" required/></FormField><FormField label="Manufactured date" name="lot-manufactured" optional><input name="manufactured_date" type="date"/></FormField><FormField label="Expiry date" name="lot-expiry" optional><input name="expiry_date" type="date"/></FormField><FormField label="Supplier" name="lot-supplier" optional><select name="supplier" defaultValue=""><option value="">No supplier</option>{suppliers.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></FormField></FormSection><div className="form-actions"><button className="primary" disabled={busy}>Create lot</button></div></form></div></details></Can>

      <Can permission="inventory.*"><details className="card workflow-disclosure"><summary><div><h2>Post lot receipt or issue</h2><p className="section-copy">Receive or issue a tracked lot. Use Waste and spoilage for write-offs.</p></div><span className="disclosure-mark" aria-hidden="true">+</span></summary><div className="workflow-disclosure-body"><form onSubmit={postLotTransaction}><FormSection title="Lot transaction"><FormField label="Lot" name="lot-transaction-lot" required><select name="lot" required defaultValue=""><option value="">Select lot</option>{lots.filter(row=>["active","quarantine"].includes(row.status)).map(row=><option key={row.id} value={row.id}>{itemName(row.item_id)} — {row.lot_number}</option>)}</select></FormField><FormField label="Location" name="lot-transaction-location" required><select name="location" required defaultValue=""><option value="">Select location</option>{locations.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></FormField><FormField label="Type" name="lot-transaction-type" required><select name="type" defaultValue="receipt"><option value="receipt">Receipt</option><option value="issue">Issue</option></select></FormField><FormField label="Quantity" name="lot-transaction-quantity" required><input name="quantity" type="number" min="0.0001" step="0.0001" required/></FormField><FormField label="Unit cost" name="lot-transaction-cost" optional><input name="unit_cost" type="number" min="0" step="0.0001"/></FormField><FormField label="Reason" name="lot-transaction-reason" optional><input name="reason"/></FormField></FormSection><div className="form-actions"><button className="primary" disabled={busy}>Post lot transaction</button></div></form></div></details></Can>

      <Can permission="inventory.*"><details className="card workflow-disclosure"><summary><div><h2>Reserve stock</h2><p className="section-copy">Set stock aside for a production batch, event, or request.</p></div><span className="disclosure-mark" aria-hidden="true">+</span></summary><div className="workflow-disclosure-body"><form onSubmit={reserve}><FormSection title="Reservation details"><FormField label="Item" name="reservation-item" required><select name="item" required defaultValue=""><option value="">Select item</option>{items.map(row=><option key={row.id} value={row.id}>{row.sku} — {row.name}</option>)}</select></FormField><FormField label="Location" name="reservation-location" required><select name="location" required defaultValue=""><option value="">Select location</option>{locations.map(row=><option key={row.id} value={row.id}>{row.code} — {row.name}</option>)}</select></FormField><FormField label="Quantity" name="reservation-quantity" required><input name="quantity" type="number" min="0.0001" step="0.0001" required/></FormField><FormField label="Reference type" name="reservation-reference-type" required><input name="reference_type" placeholder="Production batch, event, request" required/></FormField><FormField label="Reference ID" name="reservation-reference-id" required><input name="reference_id" required/></FormField></FormSection><div className="form-actions"><button className="primary" disabled={busy}>Reserve stock</button></div></form></div></details></Can>
    </section>

    <section className="card section-gap"><div className="topline"><div><h2>Availability</h2><p>Physical quantity less active reservations by item and location.</p></div></div><DataTable columns={["Item","Location","Physical","Reserved","Available"]} rows={availability.map(row=>[itemName(row.item_id),locationName(row.location_id),formatQuantity(row.physical_quantity),formatQuantity(row.reserved_quantity),<span className={Number(row.available_quantity)<0?"negative":""} key={`${row.item_id}:${row.location_id}`}>{formatQuantity(row.available_quantity)}</span>])} rowIds={availability.map(row=>`${row.item_id}:${row.location_id}`)} searchPlaceholder="Search availability" exportFileName="hidden-oasis-availability" emptyTitle="No availability records" emptyMessage="Stock balances will appear after the first posted transaction."/></section>

    {can("reports.read")?<section className="card section-gap"><div className="topline"><div><h2>Expiry queue</h2><p>Positive lot balances expiring within 60 days.</p></div></div><DataTable columns={["Lot","Item","Location","Quantity","Expiry","Days","Status"]} rows={expiry.map(row=>[row.lot_number,itemName(row.item_id),locationName(row.location_id),formatQuantity(row.quantity),formatDate(row.expiry_date),row.days_to_expiry,<StatusBadge key={`${row.lot_id}-status`} status={row.status}/>])} rowIds={expiry.map(row=>`${row.lot_id}:${row.location_id}`)} searchPlaceholder="Search expiry queue" exportFileName="hidden-oasis-expiry-queue" emptyTitle="No near-expiry stock" emptyMessage="No positive lot balances expire within the next 60 days."/></section>:null}
  </>;
}
