"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Can } from "../../components/SessionContext";
import { api } from "../../lib/api";

type Item={id:string;sku:string;name:string};
type Supplier={id:string;code:string;name:string};
type Location={id:string;code:string;name:string};
type PRLine={item_id:string;quantity:string;estimated_unit_cost:string};
type PR={id:string;requisition_number:string;department:string;status:string;created_at:string;lines:PRLine[]};
type POLine={item_id:string;ordered_quantity:string;received_quantity:string;unit_price:string};
type PO={id:string;purchase_order_number:string;supplier_id:string;status:string;created_at:string;lines:POLine[]};
type Suggestion={item_id:string;sku:string;item_name:string;location_id:string|null;location_name:string|null;current_quantity:string;minimum_stock:string;on_order_quantity:string;suggested_quantity:string;preferred_supplier_name:string|null;lead_time_days:number|null};
type DraftLine={item_id:string;quantity:string;price:string};

const blankLine=():DraftLine=>({item_id:"",quantity:"",price:""});

export default function Page(){
  const[items,setItems]=useState<Item[]>([]);
  const[suppliers,setSuppliers]=useState<Supplier[]>([]);
  const[locations,setLocations]=useState<Location[]>([]);
  const[prs,setPrs]=useState<PR[]>([]);
  const[pos,setPos]=useState<PO[]>([]);
  const[suggestions,setSuggestions]=useState<Suggestion[]>([]);
  const[prLines,setPrLines]=useState<DraftLine[]>([blankLine()]);
  const[poLines,setPoLines]=useState<DraftLine[]>([blankLine()]);
  const[selectedLocation,setSelectedLocation]=useState("");
  const[msg,setMsg]=useState("");

  const load=useCallback(async()=>{
    try{
      const[i,s,l,r,p]=await Promise.all([api<Item[]>("/items"),api<Supplier[]>("/suppliers"),api<Location[]>("/locations"),api<PR[]>("/requisitions"),api<PO[]>("/purchase-orders")]);
      setItems(i);setSuppliers(s);setLocations(l);setPrs(r);setPos(p);
      const location=selectedLocation||l[0]?.id||"";
      if(!selectedLocation&&location)setSelectedLocation(location);
      setSuggestions(location?await api<Suggestion[]>(`/reorder-suggestions?location_id=${location}`):[]);
    }catch(error){setMsg((error as Error).message)}
  },[selectedLocation]);

  useEffect(()=>{void load()},[load]);

  const sku=(id:string)=>items.find(x=>x.id===id)?.sku||id;
  const updateLine=(setter:React.Dispatch<React.SetStateAction<DraftLine[]>>,index:number,key:keyof DraftLine,value:string)=>setter(lines=>lines.map((line,i)=>i===index?{...line,[key]:value}:line));
  const removeLine=(setter:React.Dispatch<React.SetStateAction<DraftLine[]>>,index:number)=>setter(lines=>lines.length===1?[blankLine()]:lines.filter((_,i)=>i!==index));

  async function createPR(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget;const data=new FormData(form);const lines=prLines.filter(x=>x.item_id&&Number(x.quantity)>0).map(x=>({item_id:x.item_id,quantity:x.quantity,estimated_unit_cost:x.price||0}));if(!lines.length){setMsg("Add at least one valid requisition line.");return}try{await api("/requisitions",{method:"POST",body:JSON.stringify({department:data.get("department"),needed_by:data.get("needed_by")||null,justification:data.get("justification")||null,lines})});form.reset();setPrLines([blankLine()]);setMsg("Purchase requisition submitted.");await load()}catch(error){setMsg((error as Error).message)}}
  async function createReorderPR(){if(!suggestions.length){setMsg("There are no low-stock items requiring a requisition.");return}try{await api("/reorder-suggestions/requisition",{method:"POST",body:JSON.stringify({department:"Operations",location_id:selectedLocation,item_ids:suggestions.map(x=>x.item_id)})});setMsg("Low-stock requisition generated.");await load()}catch(error){setMsg((error as Error).message)}}
  async function approvePR(id:string){try{await api(`/requisitions/${id}/approve`,{method:"POST"});setMsg("Requisition approved.");await load()}catch(error){setMsg((error as Error).message)}}
  async function createPO(event:FormEvent<HTMLFormElement>){event.preventDefault();const form=event.currentTarget;const data=new FormData(form);const lines=poLines.filter(x=>x.item_id&&Number(x.quantity)>0&&Number(x.price)>0).map(x=>({item_id:x.item_id,ordered_quantity:x.quantity,unit_price:x.price}));if(!lines.length){setMsg("Add at least one valid purchase-order line.");return}try{await api("/purchase-orders",{method:"POST",body:JSON.stringify({supplier_id:data.get("supplier"),requisition_id:data.get("requisition")||null,delivery_location_id:data.get("location"),expected_delivery_date:data.get("expected_delivery_date")||null,notes:data.get("notes")||null,lines})});form.reset();setPoLines([blankLine()]);setMsg("Purchase order created as draft.");await load()}catch(error){setMsg((error as Error).message)}}
  async function approvePO(id:string){try{await api(`/purchase-orders/${id}/approve`,{method:"POST"});setMsg("Purchase order approved.");await load()}catch(error){setMsg((error as Error).message)}}

  return <AppShell title="Purchasing">
    <section className="card"><div className="topline"><div><h2>Low-stock action queue</h2><p>Open purchase orders are deducted before a reorder quantity is suggested.</p></div><select value={selectedLocation} onChange={e=>setSelectedLocation(e.target.value)}>{locations.map(x=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select></div><div className="table-wrap"><table><thead><tr><th>Item</th><th>Current</th><th>Minimum</th><th>On order</th><th>Suggested</th><th>Preferred supplier</th></tr></thead><tbody>{suggestions.map(x=><tr key={x.item_id}><td>{x.sku} — {x.item_name}</td><td>{x.current_quantity}</td><td>{x.minimum_stock}</td><td>{x.on_order_quantity}</td><td>{x.suggested_quantity}</td><td>{x.preferred_supplier_name||"Not assigned"}</td></tr>)}</tbody></table></div><Can permission="procurement.*"><button className="primary compact" disabled={!suggestions.length} onClick={createReorderPR}>Generate requisition for all</button></Can></section>

    <Can permission="procurement.*"><section className="card section-gap"><h2>New multi-line purchase requisition</h2><form onSubmit={createPR}><div className="inline-form"><input name="department" placeholder="Department" required/><input name="needed_by" type="date"/><input name="justification" placeholder="Justification"/></div>{prLines.map((line,index)=><div className="inline-form" key={index}><select value={line.item_id} onChange={e=>updateLine(setPrLines,index,"item_id",e.target.value)} required><option value="">Item</option>{items.map(x=><option key={x.id} value={x.id}>{x.sku} — {x.name}</option>)}</select><input value={line.quantity} onChange={e=>updateLine(setPrLines,index,"quantity",e.target.value)} type="number" step="0.0001" min="0.0001" placeholder="Quantity" required/><input value={line.price} onChange={e=>updateLine(setPrLines,index,"price",e.target.value)} type="number" step="0.0001" min="0" placeholder="Estimated unit cost"/><button type="button" className="secondary" onClick={()=>removeLine(setPrLines,index)}>Remove</button></div>)}<div className="inline-form"><button type="button" className="secondary" onClick={()=>setPrLines(lines=>[...lines,blankLine()])}>Add line</button><button className="primary compact">Submit PR</button></div></form></section></Can>

    <section className="card section-gap"><h2>Requisitions</h2><div className="table-wrap"><table><thead><tr><th>Number</th><th>Department</th><th>Status</th><th>Lines</th><th>Estimated value</th><th>Action</th></tr></thead><tbody>{prs.map(r=><tr key={r.id}><td>{r.requisition_number}</td><td>{r.department}</td><td>{r.status}</td><td>{r.lines.map(x=>`${sku(x.item_id)} × ${x.quantity}`).join(", ")}</td><td>{r.lines.reduce((sum,x)=>sum+Number(x.quantity)*Number(x.estimated_unit_cost),0).toFixed(2)}</td><td>{r.status==="submitted"?<Can permission="procurement.*"><button className="secondary" onClick={()=>approvePR(r.id)}>Approve</button></Can>:""}</td></tr>)}</tbody></table></div></section>

    <Can permission="procurement.*"><section className="card section-gap"><h2>Create multi-line purchase order</h2><form onSubmit={createPO}><div className="inline-form"><select name="supplier" required><option value="">Supplier</option>{suppliers.map(x=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select><select name="requisition"><option value="">Approved PR (optional)</option>{prs.filter(x=>x.status==="approved").map(x=><option key={x.id} value={x.id}>{x.requisition_number}</option>)}</select><select name="location" required><option value="">Delivery location</option>{locations.map(x=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select><input name="expected_delivery_date" type="date"/><input name="notes" placeholder="Notes"/></div>{poLines.map((line,index)=><div className="inline-form" key={index}><select value={line.item_id} onChange={e=>updateLine(setPoLines,index,"item_id",e.target.value)} required><option value="">Item</option>{items.map(x=><option key={x.id} value={x.id}>{x.sku} — {x.name}</option>)}</select><input value={line.quantity} onChange={e=>updateLine(setPoLines,index,"quantity",e.target.value)} type="number" step="0.0001" min="0.0001" placeholder="Quantity" required/><input value={line.price} onChange={e=>updateLine(setPoLines,index,"price",e.target.value)} type="number" step="0.0001" min="0.0001" placeholder="Unit price" required/><button type="button" className="secondary" onClick={()=>removeLine(setPoLines,index)}>Remove</button></div>)}<div className="inline-form"><button type="button" className="secondary" onClick={()=>setPoLines(lines=>[...lines,blankLine()])}>Add line</button><button className="primary compact">Create PO</button></div></form></section></Can>

    <section className="card section-gap"><h2>Purchase orders</h2><div className="table-wrap"><table><thead><tr><th>PO</th><th>Supplier</th><th>Status</th><th>Lines</th><th>Total</th><th>Action</th></tr></thead><tbody>{pos.map(p=><tr key={p.id}><td>{p.purchase_order_number}</td><td>{suppliers.find(x=>x.id===p.supplier_id)?.code||p.supplier_id}</td><td>{p.status}</td><td>{p.lines.map(x=>`${sku(x.item_id)} ${x.received_quantity}/${x.ordered_quantity}`).join(", ")}</td><td>{p.lines.reduce((sum,x)=>sum+Number(x.ordered_quantity)*Number(x.unit_price),0).toFixed(2)}</td><td>{p.status==="draft"?<Can permission="procurement.*"><button className="secondary" onClick={()=>approvePO(p.id)}>Approve</button></Can>:""}</td></tr>)}</tbody></table></div></section>
    {msg&&<p className="status">{msg}</p>}
  </AppShell>
}
