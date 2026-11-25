"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { Can } from "../../components/SessionContext";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { FeedbackBanner } from "../../components/FeedbackBanner";
import { StatusBadge } from "../../components/StatusBadge";
import { api } from "../../lib/api";
import { stableDraftIdempotency, type DraftIdempotencyState } from "../../lib/draftIdempotency";
import { formatDateTime, formatMoney, formatQuantity } from "../../lib/formatters";

type POLine={id:string;item_id:string;sku:string;item_name:string;ordered_quantity:string;received_quantity:string;returned_quantity:string;outstanding_quantity:string;returnable_quantity:string;unit_price:string};
type PO={id:string;purchase_order_number:string;supplier_id:string;supplier_code:string;supplier_name:string;delivery_location_id:string;delivery_location_code:string;delivery_location_name:string;expected_delivery_date:string|null;status:string;ordered_quantity:string;received_quantity:string;outstanding_quantity:string;lines:POLine[]};
type Receipt={id:string;goods_receipt_number:string;purchase_order_id:string;purchase_order_number:string;supplier_id:string|null;supplier_code:string|null;supplier_name:string|null;delivery_location_id:string|null;delivery_location_code:string|null;delivery_location_name:string|null;stock_document_id:string;delivery_reference:string|null;notes:string|null;received_at:string;received_value:string;accepted_value:string;rejected_value:string;has_discrepancy:boolean;lines:{id:string;purchase_order_line_id:string;item_id:string;sku:string;item_name:string;received_quantity:string;accepted_quantity:string;rejected_quantity:string;unit_cost:string}[]};
type ReturnRow={id:string;return_number:string;purchase_order_id:string;purchase_order_number:string;supplier_id:string|null;supplier_code:string|null;supplier_name:string|null;stock_document_id:string;reason:string;created_at:string};
type HistoryPage={page:number;page_size:number;total:number;has_previous:boolean;has_next:boolean};
type Workspace={pagination?:{purchase_orders?:{returned:number;total:number;has_more:boolean};receipts:HistoryPage;returns:HistoryPage};summary:{receivable_orders:number;partial_orders:number;receipts:number;discrepant_receipts:number;accepted_value:string;rejected_value:string;returns:number};purchase_orders:PO[];receipts:Receipt[];returns:ReturnRow[]};
type ReceiveLine={line_id:string;received:string;rejected:string;reason:string;lot_number:string;manufactured_date:string;expiry_date:string};
type ReturnLine={line_id:string;quantity:string};

export default function ReceivingPage(){
 const[data,setData]=useState<Workspace|null>(null);
 const[selectedPoId,setSelectedPoId]=useState("");
 const[receiptPoCache,setReceiptPoCache]=useState<PO|null>(null);
 const[returnPoCache,setReturnPoCache]=useState<PO|null>(null);
 const[poSearchDraft,setPoSearchDraft]=useState("");
 const[poSearch,setPoSearch]=useState("");
 const[receiveLines,setReceiveLines]=useState<ReceiveLine[]>([]);
 const[returnPoId,setReturnPoId]=useState("");
 const[returnLines,setReturnLines]=useState<ReturnLine[]>([]);
 const[deliveryReference,setDeliveryReference]=useState("");
 const[receiptNotes,setReceiptNotes]=useState("");
 const[returnReason,setReturnReason]=useState("");
 const[returnReference,setReturnReference]=useState("");
 const[returnNotes,setReturnNotes]=useState("");
 const[loading,setLoading]=useState(true);
 const[busy,setBusy]=useState(false);
 const[feedback,setFeedback]=useState<{tone:"success"|"error"|"warning"|"info";title:string;message?:string}|null>(null);
 const[pending,setPending]=useState<"receive"|"return"|null>(null);
 const[receiptStep,setReceiptStep]=useState<1|2|3>(1);
 const[receiptsPage,setReceiptsPage]=useState(1);
 const[returnsPage,setReturnsPage]=useState(1);
 const[historyPageSize]=useState(25);
 const latestLoad=useRef(0);
 const receiptRequest=useRef<DraftIdempotencyState|null>(null);
 const returnRequest=useRef<DraftIdempotencyState|null>(null);

 const load=useCallback(async()=>{
   const request=++latestLoad.current;
   setLoading(true);
   try{
     const query=new URLSearchParams({
       receipts_page:String(receiptsPage),returns_page:String(returnsPage),page_size:String(historyPageSize),
       po_limit:"60",po_search:poSearch,
     });
     const workspace=await api<Workspace>(`/receiving/workspace?${query.toString()}`);
     if(request===latestLoad.current)setData(workspace);
   }catch(error){
     if(request===latestLoad.current)setFeedback({tone:"error",title:"Receiving workspace unavailable",message:(error as Error).message});
   }finally{if(request===latestLoad.current)setLoading(false)}
 },[receiptsPage,returnsPage,historyPageSize,poSearch]);
 useEffect(()=>{void load()},[load]);
 const selectedPo=useMemo(()=>data?.purchase_orders.find(row=>row.id===selectedPoId)
   ||(receiptPoCache?.id===selectedPoId?receiptPoCache:null),[data,selectedPoId,receiptPoCache]);
 // The draft is initialized only when the user selects an order. Reloading
 // history/pages may replace the PO object but must NOT erase entered numbers.
 const selectedReturnPo=useMemo(()=>data?.purchase_orders.find(row=>row.id===returnPoId)
   ||(returnPoCache?.id===returnPoId?returnPoCache:null),[data,returnPoId,returnPoCache]);
 function selectReceiptPo(poId:string){
   const po=data?.purchase_orders.find(row=>row.id===poId);
   setSelectedPoId(poId);
   setReceiptPoCache(po||null);
   setReceiveLines(po?.lines.filter(line=>Number(line.outstanding_quantity)>0).map(line=>({
     line_id:line.id,received:"",rejected:"0",reason:"",lot_number:"",manufactured_date:"",expiry_date:""
   }))||[]);
   setDeliveryReference("");setReceiptNotes("");setReceiptStep(1);
   receiptRequest.current=null;
 }
 function selectReturnPo(poId:string){
   const po=data?.purchase_orders.find(row=>row.id===poId);
   setReturnPoId(poId);
   setReturnPoCache(po||null);
   setReturnLines(po?.lines.filter(line=>Number(line.returnable_quantity)>0).map(line=>({line_id:line.id,quantity:"0"}))||[]);
   returnRequest.current=null;
 }

 const receiptPayload=useMemo(()=>receiveLines.filter(row=>Number(row.received)>0).map(row=>{const received=Number(row.received),rejected=Number(row.rejected||0);return {purchase_order_line_id:row.line_id,received_quantity:received,accepted_quantity:received-rejected,rejected_quantity:rejected,discrepancy_reason:rejected>0?row.reason||null:null,lot_number:row.lot_number||null,manufactured_date:row.manufactured_date||null,expiry_date:row.expiry_date||null}}),[receiveLines]);
 const returnPayload=useMemo(()=>returnLines.filter(row=>Number(row.quantity)>0).map(row=>({purchase_order_line_id:row.line_id,quantity:Number(row.quantity)})),[returnLines]);
 const receiptValid=Boolean(
   selectedPo && deliveryReference.trim() && receiptPayload.length &&
   receiveLines.every(row => {
     const arrived = row.received.trim() ? Number(row.received) : 0;
     const rejected = row.rejected.trim() ? Number(row.rejected) : 0;
     return Number.isFinite(arrived) && Number.isFinite(rejected) &&
       arrived >= 0 && rejected >= 0 && rejected <= arrived &&
       arrived <= Number(selectedPo.lines.find(line=>line.id===row.line_id)?.outstanding_quantity??0);
   }) &&
   receiptPayload.every(line=>{
     const original=selectedPo.lines.find(row=>row.id===line.purchase_order_line_id);
     const originalInput=receiveLines.find(row=>row.line_id===line.purchase_order_line_id);
     return Boolean(original && originalInput &&
       Number.isFinite(line.received_quantity) && line.received_quantity>0 &&
       line.received_quantity<=Number(original.outstanding_quantity) &&
       Number.isFinite(line.rejected_quantity) && line.rejected_quantity>=0 &&
       line.rejected_quantity<=line.received_quantity &&
       (!line.rejected_quantity || Boolean(line.discrepancy_reason?.trim())) &&
       (!originalInput.expiry_date || !originalInput.manufactured_date ||
         originalInput.expiry_date>=originalInput.manufactured_date));
   })
 );
 const returnValid=Boolean(selectedReturnPo && returnReason.trim() && returnPayload.length &&
   returnPayload.every(line=>{
     const original=selectedReturnPo.lines.find(row=>row.id===line.purchase_order_line_id);
     return Boolean(original && Number.isFinite(line.quantity) && line.quantity>0 &&
       line.quantity<=Number(original.returnable_quantity));
   })
 );

 async function postReceipt(){
   if(!selectedPo||!receiptValid||busy)return;
   const payload={delivery_reference:deliveryReference.trim(),notes:receiptNotes||null,lines:receiptPayload};
   // Keep the same key for a retry of the same document, even after a timeout.
   const request=stableDraftIdempotency({kind:"receipt",po_id:selectedPo.id,...payload},receiptRequest.current);
   receiptRequest.current=request;
   setBusy(true);
   try{
     const result=await api<Receipt>(`/receiving/purchase-orders/${selectedPo.id}`,{
       method:"POST",body:JSON.stringify({...payload,idempotency_key:request.key})
     });
     receiptRequest.current=null;
     setFeedback({tone:result.has_discrepancy?"warning":"success",title:"Goods receipt posted",message:result.has_discrepancy?
       `${result.goods_receipt_number} includes rejected quantities requiring follow-up.`:
       `${result.goods_receipt_number} posted accepted stock to ${result.delivery_location_code}.`});
     setPending(null);setReceiptStep(1);setSelectedPoId("");setReceiptPoCache(null);setReceiveLines([]);setDeliveryReference("");setReceiptNotes("");
     await load();
   }catch(error){
     setFeedback({tone:"error",title:"Receipt not confirmed",message:
       `${(error as Error).message} If the connection failed, check the receipt list or retry this confirmation. The same transaction key will be reused.`});
   }finally{setBusy(false)}
 }
 async function postReturn(){
   if(!selectedReturnPo||!returnValid||busy)return;
   const payload={reason:returnReason.trim(),supplier_reference:returnReference||null,notes:returnNotes||null,lines:returnPayload};
   const request=stableDraftIdempotency({kind:"supplier-return",po_id:selectedReturnPo.id,...payload},returnRequest.current);
   returnRequest.current=request;
   setBusy(true);
   try{
     const result=await api<ReturnRow>(`/receiving/purchase-orders/${selectedReturnPo.id}/returns`,{
       method:"POST",body:JSON.stringify({...payload,idempotency_key:request.key})
     });
     returnRequest.current=null;
     setFeedback({tone:"success",title:"Supplier return posted",
       message:`${result.return_number} removed the selected quantity from stock and sent the event to Accounting.`});
     setPending(null);setReturnPoId("");setReturnPoCache(null);setReturnLines([]);setReturnReason("");setReturnReference("");setReturnNotes("");
     await load();
   }catch(error){
     setFeedback({tone:"error",title:"Return not confirmed",message:
       `${(error as Error).message} If the connection failed, check the return list or retry this confirmation using the same transaction key.`});
   }finally{setBusy(false)}
 }

 return <AppShell title="Receiving" description="Deliveries, discrepancies, and supplier returns.">
  {feedback?<FeedbackBanner tone={feedback.tone} title={feedback.title} message={feedback.message}/>:null}
  <section className="receiving-metrics"><div><span>Receivable POs</span><strong>{data?.summary.receivable_orders||0}</strong></div><div><span>Partial POs</span><strong>{data?.summary.partial_orders||0}</strong></div><div><span>Goods receipts</span><strong>{data?.summary.receipts||0}</strong></div><div><span>Discrepant receipts</span><strong>{data?.summary.discrepant_receipts||0}</strong></div><div><span>Accepted value</span><strong>{formatMoney(data?.summary.accepted_value||0)}</strong></div><div><span>Rejected value</span><strong>{formatMoney(data?.summary.rejected_value||0)}</strong></div><div><span>Supplier returns</span><strong>{data?.summary.returns||0}</strong></div></section>


  <form className="count-search-form receiving-po-search" role="search" onSubmit={event=>{event.preventDefault();setPoSearch(poSearchDraft.trim())}}>
     <label><span>Find an order by number or supplier</span><input aria-label="Find purchase orders" value={poSearchDraft} onChange={event=>setPoSearchDraft(event.target.value)} placeholder="PO number or supplier" maxLength={120}/></label>
     <button type="submit" className="secondary" disabled={loading}>Find orders</button>
     {poSearch?<button type="button" className="text-button" onClick={()=>{setPoSearchDraft("");setPoSearch("")}}>Show recent orders</button>:null}
     <span role="status">{data?.pagination?.purchase_orders?.has_more?"Showing the most recent 60 matching orders. Search to find older ones.":""}</span>
   </form>
   <Can permission="receiving.*"><section className="card guided-receiving" aria-label="Receive a delivery">
    <div className="topline"><div><h2>Record a delivery</h2><p>Choose the order, count what arrived, then check everything before posting.</p></div></div>
    <ol className="workflow-steps" aria-label="Delivery steps">
      <li aria-current={receiptStep===1?"step":undefined} className={receiptStep===1?"active":receiptStep>1?"done":""}>1. Choose order</li>
      <li aria-current={receiptStep===2?"step":undefined} className={receiptStep===2?"active":receiptStep>2?"done":""}>2. Count delivery</li>
      <li aria-current={receiptStep===3?"step":undefined} className={receiptStep===3?"active":""}>3. Check &amp; post</li>
    </ol>

    {receiptStep===1?<div className="workflow-stage" data-testid="receiving-choose">
      <h3>Step 1: Which order arrived?</h3>
      <p className="workflow-hint">Use the purchase order (PO) number printed on the order. Only orders that can still receive stock appear here.</p>
      <label className="workflow-select"><span>Purchase order</span>
        <select aria-label="Purchase order" value={selectedPoId} onChange={event=>selectReceiptPo(event.target.value)}>
          <option value="">Choose a purchase order</option>
          {selectedPo&&!data?.purchase_orders.some(row=>row.id===selectedPo.id)?<option value={selectedPo.id}>{selectedPo.purchase_order_number} — selected draft</option>:null}
          {data?.purchase_orders.filter(row=>["approved","partially_received"].includes(row.status)).map(row=>
            <option key={row.id} value={row.id}>{row.purchase_order_number} — {row.supplier_name} — {row.delivery_location_name}</option>)}
        </select>
      </label>
      {selectedPo?<div className="workflow-note"><strong>{selectedPo.supplier_name}</strong><span>Deliver to {selectedPo.delivery_location_name} · {formatQuantity(selectedPo.outstanding_quantity)} units still expected</span></div>:null}
      <div className="form-actions"><button data-training="receive-next" type="button" className="primary" disabled={!selectedPo||busy} onClick={()=>setReceiptStep(2)}>Next: count the delivery</button></div>
    </div>:null}

    {receiptStep===2&&selectedPo?<div className="workflow-stage" data-testid="receiving-count">
      <h3>Step 2: What actually arrived?</h3>
      <p className="workflow-hint">For each item, enter the quantity delivered today. If anything is damaged, enter how many you rejected and why. Enter 0 for items not delivered.</p>
      <div className="receiving-po-summary">
        <div><span>Order</span><strong>{selectedPo.purchase_order_number}</strong></div>
        <div><span>Supplier</span><strong>{selectedPo.supplier_name}</strong></div>
        <div><span>Deliver to</span><strong>{selectedPo.delivery_location_name}</strong></div>
        <div><span>Still expected</span><strong>{formatQuantity(selectedPo.outstanding_quantity)}</strong></div>
      </div>
      <div className="table-wrap guided-line-table"><table>
        <thead><tr><th>Item</th><th>Still expected</th><th>Arrived today</th><th>Rejected</th><th>Accepted</th><th>Reason / optional details</th></tr></thead>
        <tbody>{selectedPo.lines.filter(line=>Number(line.outstanding_quantity)>0).map(line=>{
          const entry=receiveLines.find(row=>row.line_id===line.id);
          const arrived=Number(entry?.received||0), rejected=Number(entry?.rejected||0), accepted=arrived-rejected;
          const invalid=Boolean(entry && (arrived<0||!Number.isFinite(arrived)||arrived>Number(line.outstanding_quantity)||rejected<0||rejected>arrived||!Number.isFinite(rejected)||(rejected>0&&!entry.reason.trim())||(entry.expiry_date&&entry.manufactured_date&&entry.expiry_date<entry.manufactured_date)));
          const errorMessage=arrived>Number(line.outstanding_quantity)?"More than the remaining order":rejected>arrived?"Rejected cannot be more than arrived":rejected>0&&!entry?.reason.trim()?"Enter why these items were rejected":"Check the entered quantities and dates";
          return <tr key={line.id} className={invalid?"invalid-line":""}>
            <td data-label="Item"><Link href={`/items/${line.item_id}`}>{line.item_name}</Link><small className="workflow-item-meta">{line.sku} · Ordered {formatQuantity(line.ordered_quantity)} · Earlier deliveries {formatQuantity(line.received_quantity)}</small></td>
            <td data-label="Still expected">{formatQuantity(line.outstanding_quantity)}</td>
            <td data-label="Arrived today"><input aria-label={`Arrived today for ${line.item_name}`} aria-invalid={arrived<0||arrived>Number(line.outstanding_quantity)||!Number.isFinite(arrived)} type="number" min="0" max={line.outstanding_quantity} step="0.0001" inputMode="decimal" disabled={!entry} value={entry?.received||""} placeholder="0" onChange={event=>setReceiveLines(rows=>rows.map(row=>row.line_id===line.id?{...row,received:event.target.value}:row))}/></td>
            <td data-label="Rejected"><input aria-label={`Rejected quantity for ${line.item_name}`} aria-invalid={rejected<0||rejected>arrived||!Number.isFinite(rejected)} type="number" min="0" max={entry?.received||0} step="0.0001" inputMode="decimal" disabled={!entry} value={entry?.rejected||"0"} onChange={event=>setReceiveLines(rows=>rows.map(row=>row.line_id===line.id?{...row,rejected:event.target.value}:row))}/></td>
            <td data-label="Accepted">{formatQuantity(Math.max(0,accepted))}</td>
            <td data-label="Details"><div className="workflow-line-extra"><label><span>Why rejected? {rejected>0?"(required)":""}</span><input aria-label={`Reason for rejecting ${line.item_name}`} aria-invalid={rejected>0&&!entry?.reason.trim()} disabled={!entry||rejected<=0} required={rejected>0} value={entry?.reason||""} placeholder={rejected>0?"Example: damaged packaging":"No rejected items"} onChange={event=>setReceiveLines(rows=>rows.map(row=>row.line_id===line.id?{...row,reason:event.target.value}:row))}/></label>
              <details className="workflow-optional"><summary>Lot and expiry (if shown on package)</summary>
                <label><span>Lot / batch number</span><input aria-label={`Lot number for ${line.item_name}`} value={entry?.lot_number||""} onChange={event=>setReceiveLines(rows=>rows.map(row=>row.line_id===line.id?{...row,lot_number:event.target.value}:row))}/></label>
                <label><span>Manufactured on</span><input aria-label={`Manufactured date for ${line.item_name}`} type="date" value={entry?.manufactured_date||""} onChange={event=>setReceiveLines(rows=>rows.map(row=>row.line_id===line.id?{...row,manufactured_date:event.target.value}:row))}/></label>
                <label><span>Expires on</span><input aria-label={`Expiry date for ${line.item_name}`} type="date" value={entry?.expiry_date||""} onChange={event=>setReceiveLines(rows=>rows.map(row=>row.line_id===line.id?{...row,expiry_date:event.target.value}:row))}/></label>
              </details>
              {invalid?<p className="field-error" role="alert">{errorMessage}</p>:null}
            </div></td>
          </tr>
        })}</tbody>
      </table></div>
      <div className="receiving-header-form workflow-last-fields">
        <label><span>Supplier delivery receipt (DR) number — required</span><input aria-label="Delivery reference" required value={deliveryReference} onChange={event=>setDeliveryReference(event.target.value)} placeholder="Find this on the supplier's DR or invoice"/></label>
        <label><span>Extra notes (optional)</span><input aria-label="Receiving notes" value={receiptNotes} onChange={event=>setReceiptNotes(event.target.value)} placeholder="Anything the next shift should know"/></label>
      </div>
      {!receiptValid?<p className="workflow-hint" role="status">To continue: enter the delivery reference and at least one received item. Check any red quantity or reason fields.</p>:null}
      <div className="form-actions"><button type="button" className="secondary" onClick={()=>setReceiptStep(1)}>Back to order</button><button data-training="receive-review" type="button" className="primary" disabled={!receiptValid||busy} onClick={()=>setReceiptStep(3)}>Next: check details</button></div>
    </div>:null}

    {receiptStep===3&&selectedPo?<div className="workflow-stage" data-testid="receiving-review">
      <h3>Step 3: Check before posting</h3>
      <p className="workflow-hint">Posting adds accepted items to stock. Rejected items are not added. Check the item and quantities carefully.</p>
      <dl className="workflow-review">
        <div><dt>Purchase order</dt><dd>{selectedPo.purchase_order_number}</dd></div>
        <div><dt>Supplier</dt><dd>{selectedPo.supplier_name}</dd></div>
        <div><dt>Destination</dt><dd>{selectedPo.delivery_location_name}</dd></div>
        <div><dt>Supplier DR</dt><dd>{deliveryReference}</dd></div>
        <div><dt>Quantity accepted</dt><dd>{formatQuantity(receiptPayload.reduce((sum,row)=>sum+row.accepted_quantity,0))}</dd></div>
        <div><dt>Quantity rejected</dt><dd>{formatQuantity(receiptPayload.reduce((sum,row)=>sum+row.rejected_quantity,0))}</dd></div>
      </dl>
      <ul className="workflow-review-lines">{receiptPayload.map(line=>{
        const original=selectedPo.lines.find(row=>row.id===line.purchase_order_line_id);
        return <li key={line.purchase_order_line_id}><strong>{original?.item_name||"Item"}</strong><span>Arrived {formatQuantity(line.received_quantity)} · Accepted {formatQuantity(line.accepted_quantity)} · Rejected {formatQuantity(line.rejected_quantity)}</span></li>
      })}</ul>
      <div className="form-actions"><button type="button" className="secondary" onClick={()=>setReceiptStep(2)}>Edit quantities</button><button data-training="receive-confirm" type="button" className="primary" disabled={!receiptValid||busy} onClick={()=>setPending("receive")}>Confirm this delivery</button></div>
    </div>:null}
  </section></Can>

  <Can permission="receiving.*"><details className="card section-gap workflow-disclosure guided-returns"><summary data-training="return-open"><div className="topline"><div><h2>Return accepted stock to supplier</h2><p>Return previously accepted items to the supplier.</p></div></div><span className="disclosure-mark" aria-hidden="true">+</span></summary><div className="workflow-disclosure-body"><div className="receiving-header-form"><label><span>Purchase order</span><select data-training="return-po" value={returnPoId} onChange={event=>selectReturnPo(event.target.value)}><option value="">Select PO with returnable stock</option>{selectedReturnPo&&!data?.purchase_orders.some(row=>row.id===selectedReturnPo.id)?<option value={selectedReturnPo.id}>{selectedReturnPo.purchase_order_number} — selected return</option>:null}{data?.purchase_orders.filter(row=>row.lines.some(line=>Number(line.returnable_quantity)>0)).map(row=><option key={row.id} value={row.id}>{row.purchase_order_number} — {row.supplier_code}</option>)}</select></label><label><span>Return reason</span><input data-training="return-reason" value={returnReason} onChange={event=>setReturnReason(event.target.value)} placeholder="Damage, quality issue, wrong item…"/></label><label><span>Supplier reference</span><input value={returnReference} onChange={event=>setReturnReference(event.target.value)} placeholder="RMA or supplier credit ref"/></label><label><span>Notes</span><input value={returnNotes} onChange={event=>setReturnNotes(event.target.value)}/></label></div>{selectedReturnPo?<><div className="table-wrap"><table><thead><tr><th>Item</th><th>Received</th><th>Previously returned</th><th>Returnable</th><th>Return now</th><th>Value</th></tr></thead><tbody>{selectedReturnPo.lines.map(line=>{const entry=returnLines.find(row=>row.line_id===line.id);return <tr key={line.id}><td>{line.sku} — {line.item_name}</td><td>{formatQuantity(line.received_quantity)}</td><td>{formatQuantity(line.returned_quantity)}</td><td>{formatQuantity(line.returnable_quantity)}</td><td><input aria-label={`Quantity to return for ${line.item_name}`} type="number" min="0" max={line.returnable_quantity} step="0.0001" inputMode="decimal" disabled={!entry} value={entry?.quantity||"0"} onChange={event=>setReturnLines(rows=>rows.map(row=>row.line_id===line.id?{...row,quantity:event.target.value}:row))}/></td><td>{formatMoney(Number(entry?.quantity||0)*Number(line.unit_price))}</td></tr>})}</tbody></table></div><div className="form-actions"><button data-training="return-review" className="primary" disabled={!returnValid||busy} onClick={()=>setPending("return")}>Review and post return</button></div></>:<div className="config-empty">Select a purchase order with accepted stock available to return.</div>}</div></details></Can>

  <section className="card section-gap receiving-history"><div className="topline"><div><h2>Goods receipt history</h2><p>Accepted and rejected value, delivery reference, discrepancy status, stock document, supplier, and destination.</p></div></div>
  <div className="history-pager" aria-label="Goods receipts pages">
    <span role="status" aria-live="polite">{data?.pagination?.receipts? `Showing ${data.pagination.receipts.total?((data.pagination.receipts.page-1)*data.pagination.receipts.page_size+1):0}–${Math.min(data.pagination.receipts.page*data.pagination.receipts.page_size,data.pagination.receipts.total)} of ${data.pagination.receipts.total} receipts`:"Recent receipts"}</span>
    <div><button type="button" className="secondary" disabled={loading||receiptsPage<=1} onClick={()=>setReceiptsPage(page=>Math.max(1,page-1))}>Previous receipts</button>
    <button type="button" className="secondary" disabled={loading||!data?.pagination?.receipts.has_next} onClick={()=>setReceiptsPage(page=>page+1)}>Next receipts</button></div>
  </div><div className="table-wrap"><table><thead><tr><th>GRN</th><th>PO</th><th>Supplier</th><th>Destination</th><th>Delivery ref</th><th>Accepted</th><th>Rejected</th><th>Status</th><th>Received</th></tr></thead><tbody>{data?.receipts.length?data.receipts.map(row=><tr key={row.id}><td><Link href={`/stock/documents/${row.stock_document_id}`}>{row.goods_receipt_number}</Link></td><td><Link href={`/purchasing/orders/${row.purchase_order_id}`}>{row.purchase_order_number}</Link></td><td>{row.supplier_code} — {row.supplier_name}</td><td>{row.delivery_location_code}</td><td>{row.delivery_reference||"—"}</td><td>{formatMoney(row.accepted_value)}</td><td>{formatMoney(row.rejected_value)}</td><td><StatusBadge status={row.has_discrepancy?"discrepancy":"accepted"}/></td><td>{formatDateTime(row.received_at)}</td></tr>):<tr><td colSpan={9}>{loading?"Loading receipts…":"No goods receipts recorded."}</td></tr>}</tbody></table></div></section>

  <section className="card section-gap receiving-history"><div className="topline"><div><h2>Supplier return history</h2><p>Every return links to its source purchase order and immutable stock document.</p></div></div>
  <div className="history-pager" aria-label="Supplier returns pages">
    <span role="status" aria-live="polite">{data?.pagination?.returns? `Showing ${data.pagination.returns.total?((data.pagination.returns.page-1)*data.pagination.returns.page_size+1):0}–${Math.min(data.pagination.returns.page*data.pagination.returns.page_size,data.pagination.returns.total)} of ${data.pagination.returns.total} returns`:"Recent supplier returns"}</span>
    <div><button type="button" className="secondary" disabled={loading||returnsPage<=1} onClick={()=>setReturnsPage(page=>Math.max(1,page-1))}>Previous returns</button>
    <button type="button" className="secondary" disabled={loading||!data?.pagination?.returns.has_next} onClick={()=>setReturnsPage(page=>page+1)}>Next returns</button></div>
  </div><div className="table-wrap"><table><thead><tr><th>Return</th><th>PO</th><th>Supplier</th><th>Reason</th><th>Created</th><th>Document</th></tr></thead><tbody>{data?.returns.length?data.returns.map(row=><tr key={row.id}><td>{row.return_number}</td><td><Link href={`/purchasing/orders/${row.purchase_order_id}`}>{row.purchase_order_number}</Link></td><td>{row.supplier_code} — {row.supplier_name}</td><td>{row.reason}</td><td>{formatDateTime(row.created_at)}</td><td><Link href={`/stock/documents/${row.stock_document_id}`}>Open stock document</Link></td></tr>):<tr><td colSpan={6}>No supplier returns recorded.</td></tr>}</tbody></table></div></section>

  <ConfirmDialog open={Boolean(pending)} title={pending==="receive"?"Post this goods receipt?":"Post this supplier return?"} description={pending==="receive"?`${receiptPayload.length} line(s) will be received against ${selectedPo?.purchase_order_number}. Accepted stock will be posted; rejected quantities will remain out of inventory.`:`${returnPayload.length} line(s) will be removed from stock and returned against ${selectedReturnPo?.purchase_order_number}.`} confirmLabel={pending==="receive"?"Post goods receipt":"Post supplier return"} tone={pending==="return"?"danger":"default"} busy={busy} onConfirm={()=>pending==="receive"?void postReceipt():void postReturn()} onCancel={()=>setPending(null)}>{pending&&feedback?.tone==="error"?<p role="alert" className="field-error">{feedback.message||feedback.title}</p>:null}</ConfirmDialog>
 </AppShell>;
}
