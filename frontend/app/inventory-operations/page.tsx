"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { DataTable } from "../../components/DataTable";
import { api } from "../../lib/api";

type Item={id:string;sku:string;name:string};
type Location={id:string;code:string;name:string};
type Supplier={id:string;code:string;name:string};
type Lot={id:string;item_id:string;lot_number:string;expiry_date:string|null;status:string};
type Availability={item_id:string;location_id:string;physical_quantity:string;reserved_quantity:string;available_quantity:string};
type Transfer={id:string;transfer_number:string;source_location_id:string;destination_location_id:string;status:string;lines:{item_id:string;quantity:string}[]};
type Expiry={lot_id:string;item_id:string;lot_number:string;location_id:string;quantity:string;expiry_date:string;days_to_expiry:number;status:string};
type Valuation={item_id:string;location_id:string;quantity:string;average_cost:string;inventory_value:string};

export default function Page(){
  const[items,setItems]=useState<Item[]>([]);
  const[locations,setLocations]=useState<Location[]>([]);
  const[suppliers,setSuppliers]=useState<Supplier[]>([]);
  const[lots,setLots]=useState<Lot[]>([]);
  const[availability,setAvailability]=useState<Availability[]>([]);
  const[transfers,setTransfers]=useState<Transfer[]>([]);
  const[expiry,setExpiry]=useState<Expiry[]>([]);
  const[valuation,setValuation]=useState<Valuation[]>([]);
  const[msg,setMsg]=useState("");

  const load=useCallback(async()=>{
    try{
      const[i,l,s,lot,a,t,e,v]=await Promise.all([
        api<Item[]>("/items"),api<Location[]>("/locations"),api<Supplier[]>("/suppliers"),api<Lot[]>("/lots"),api<Availability[]>("/availability"),api<Transfer[]>("/transfer-orders"),api<Expiry[]>("/reports/expiry?days=60"),api<Valuation[]>("/reports/valuation")
      ]);
      setItems(i);setLocations(l);setSuppliers(s);setLots(lot);setAvailability(a);setTransfers(t);setExpiry(e);setValuation(v);
    }catch(error){setMsg((error as Error).message)}
  },[]);
  useEffect(()=>{void load()},[load]);

  const itemName=(id:string)=>items.find(x=>x.id===id)?.sku||id;
  const locationName=(id:string)=>locations.find(x=>x.id===id)?.code||id;

  async function createLot(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget,data=new FormData(form);try{await api("/lots",{method:"POST",body:JSON.stringify({item_id:data.get("item"),lot_number:data.get("lot_number"),manufactured_date:data.get("manufactured_date")||null,expiry_date:data.get("expiry_date")||null,supplier_id:data.get("supplier")||null})});form.reset();setMsg("Lot created.");await load()}catch(error){setMsg((error as Error).message)}}
  async function postLotTransaction(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget,data=new FormData(form);try{await api("/lot-transactions",{method:"POST",body:JSON.stringify({lot_id:data.get("lot"),location_id:data.get("location"),quantity:data.get("quantity"),unit_cost:data.get("unit_cost")||0,transaction_type:data.get("type"),reason:data.get("reason")||null})});form.reset();setMsg("Lot transaction posted.");await load()}catch(error){setMsg((error as Error).message)}}
  async function reserve(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget,data=new FormData(form);try{await api("/reservations",{method:"POST",body:JSON.stringify({item_id:data.get("item"),location_id:data.get("location"),quantity:data.get("quantity"),reference_type:data.get("reference_type"),reference_id:data.get("reference_id")})});form.reset();setMsg("Stock reserved.");await load()}catch(error){setMsg((error as Error).message)}}
  async function createTransfer(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget,data=new FormData(form);try{await api("/transfer-orders",{method:"POST",body:JSON.stringify({source_location_id:data.get("source"),destination_location_id:data.get("destination"),notes:data.get("notes")||null,lines:[{item_id:data.get("item"),quantity:data.get("quantity")}]})});form.reset();setMsg("Transfer order created.");await load()}catch(error){setMsg((error as Error).message)}}
  async function transitionTransfer(id:string,action:"dispatch"|"receive"){try{await api(`/transfer-orders/${id}/${action}`,{method:"POST"});setMsg(`Transfer ${action} completed.`);await load()}catch(error){setMsg((error as Error).message)}}

  return <AppShell title="Inventory Operations">
    <section className="grid">
      <div className="card"><h2>Available stock</h2><p>Physical less active reservations.</p><strong>{availability.reduce((sum,x)=>sum+Number(x.available_quantity),0).toFixed(2)}</strong></div>
      <div className="card"><h2>Near expiry</h2><p>Lots expiring within 60 days.</p><strong>{expiry.length}</strong></div>
      <div className="card"><h2>Inventory value</h2><p>Weighted-average valuation.</p><strong>₱{valuation.reduce((sum,x)=>sum+Number(x.inventory_value),0).toFixed(2)}</strong></div>
    </section>

    <section className="card section-gap"><h2>Create lot</h2><form className="inline-form" onSubmit={createLot}><select name="item" required><option value="">Item</option>{items.map(x=><option key={x.id} value={x.id}>{x.sku} — {x.name}</option>)}</select><input name="lot_number" placeholder="Lot number" required/><input name="manufactured_date" type="date"/><input name="expiry_date" type="date"/><select name="supplier"><option value="">Supplier</option>{suppliers.map(x=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select><button className="primary compact">Create lot</button></form></section>

    <section className="card section-gap"><h2>Post lot transaction</h2><form className="inline-form" onSubmit={postLotTransaction}><select name="lot" required><option value="">Lot</option>{lots.map(x=><option key={x.id} value={x.id}>{itemName(x.item_id)} — {x.lot_number}</option>)}</select><select name="location" required><option value="">Location</option>{locations.map(x=><option key={x.id} value={x.id}>{x.code}</option>)}</select><select name="type"><option value="receipt">Receipt</option><option value="issue">Issue</option><option value="waste">Waste</option><option value="damage">Damage</option></select><input name="quantity" type="number" min="0.0001" step="0.0001" placeholder="Quantity" required/><input name="unit_cost" type="number" min="0" step="0.0001" placeholder="Unit cost"/><input name="reason" placeholder="Reason"/><button className="primary compact">Post transaction</button></form></section>

    <section className="card section-gap"><h2>Reserve stock</h2><form className="inline-form" onSubmit={reserve}><select name="item" required><option value="">Item</option>{items.map(x=><option key={x.id} value={x.id}>{x.sku}</option>)}</select><select name="location" required><option value="">Location</option>{locations.map(x=><option key={x.id} value={x.id}>{x.code}</option>)}</select><input name="quantity" type="number" min="0.0001" step="0.0001" placeholder="Quantity" required/><input name="reference_type" placeholder="Reference type" required/><input name="reference_id" placeholder="Reference ID" required/><button className="primary compact">Reserve</button></form></section>

    <section className="card section-gap"><h2>Create transfer order</h2><form className="inline-form" onSubmit={createTransfer}><select name="source" required><option value="">Source</option>{locations.map(x=><option key={x.id} value={x.id}>{x.code}</option>)}</select><select name="destination" required><option value="">Destination</option>{locations.map(x=><option key={x.id} value={x.id}>{x.code}</option>)}</select><select name="item" required><option value="">Item</option>{items.map(x=><option key={x.id} value={x.id}>{x.sku}</option>)}</select><input name="quantity" type="number" min="0.0001" step="0.0001" placeholder="Quantity" required/><input name="notes" placeholder="Notes"/><button className="primary compact">Create transfer</button></form><div className="table-wrap"><table><thead><tr><th>Transfer</th><th>Route</th><th>Status</th><th>Lines</th><th>Action</th></tr></thead><tbody>{transfers.map(x=><tr key={x.id}><td>{x.transfer_number}</td><td>{locationName(x.source_location_id)} → {locationName(x.destination_location_id)}</td><td>{x.status}</td><td>{x.lines.map(line=>`${itemName(line.item_id)} × ${line.quantity}`).join(", ")}</td><td>{x.status==="draft"?<button className="secondary" onClick={()=>transitionTransfer(x.id,"dispatch")}>Dispatch</button>:x.status==="dispatched"?<button className="secondary" onClick={()=>transitionTransfer(x.id,"receive")}>Receive</button>:"Completed"}</td></tr>)}</tbody></table></div></section>

    <section className="card section-gap"><h2>Availability</h2><DataTable columns={["Item","Location","Physical","Reserved","Available"]} rows={availability.map(x=>[itemName(x.item_id),locationName(x.location_id),x.physical_quantity,x.reserved_quantity,x.available_quantity])}/></section>
    <section className="card section-gap"><h2>Expiry queue</h2><DataTable columns={["Lot","Item","Location","Quantity","Expiry","Days","Status"]} rows={expiry.map(x=>[x.lot_number,itemName(x.item_id),locationName(x.location_id),x.quantity,x.expiry_date,x.days_to_expiry,x.status])}/></section>
    {msg&&<p className="status">{msg}</p>}
  </AppShell>
}
