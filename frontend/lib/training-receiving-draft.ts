import type { DraftIdempotencyState } from "./draftIdempotency";

export type TrainingReceivingDraft = {
  poId: string; step: 1|2|3; reference: string; notes: string;
  lines: {line_id:string;received:string;rejected:string;reason:string;lot_number:string;manufactured_date:string;expiry_date:string}[];
  request: DraftIdempotencyState | null;
};
function key(){
  if(process.env.NEXT_PUBLIC_INVENTORY_TRAINING!=="1"||typeof window==="undefined")return null;
  const attempt=localStorage.getItem("inventory-training-attempt");
  return attempt&&/^[a-f0-9-]{36}$/.test(attempt)?`inventory-training-receiving:${attempt}`:null;
}
export function readTrainingReceiptDraft():TrainingReceivingDraft|null{
  const name=key();if(!name)return null;
  try{
    const raw=JSON.parse(localStorage.getItem(name)||"null") as TrainingReceivingDraft|null;
    if(!raw||typeof raw.poId!=="string"||![1,2,3].includes(raw.step)||typeof raw.reference!=="string"||typeof raw.notes!=="string"||!Array.isArray(raw.lines)||!raw.lines.every(line=>[line.line_id,line.received,line.rejected,line.reason,line.lot_number,line.manufactured_date,line.expiry_date].every(value=>typeof value==="string")))return null;
    return raw;
  }catch{return null}
}
export function writeTrainingReceiptDraft(draft:TrainingReceivingDraft){
  const name=key();if(!name)return;
  try{if(draft.poId)localStorage.setItem(name,JSON.stringify(draft));else localStorage.removeItem(name)}catch{/* The server still preserves posted records and can recover their checkpoint. */}
}
