import type {TrainingLesson} from "./inventory-training";
import {trainingAttempt} from "./training-session";

export function trainingDraftKey(storageKey:string) {
  let attempt="unstarted";
  attempt=trainingAttempt()||attempt;
  return `inventory-training:draft:${attempt}:${storageKey}`;
}

export function restoreCatalogueCheckpoint(lesson:TrainingLesson,checkpoint:number) {
  const storageKey=lesson.id==="create-item"?"inventory:item-draft:v2":lesson.id==="create-supplier"?"inventory:supplier-draft":null;
  if(!storageKey)return checkpoint;
  const fields:Record<string,string>={"#item-workspace":"workspace","#item-type":"itemType","#item-sku":"sku","#item-name":"name","#item-category":"category","#item-unit":"unit","#item-location":"defaultLocation","#item-minimum":"minimum","#item-cost":"cost","#supplier-code":"code","#supplier-name":"name","#supplier-contact":"contact","#supplier-email":"email","#supplier-terms":"terms"};
  try {
    const saved=localStorage.getItem(trainingDraftKey(storageKey));
    if(!saved)return 0;
    const draft=JSON.parse(saved) as Record<string,string>;
    const identity=lesson.id==="create-item"?["workspace","itemType","sku","name"]:["code","name","contact","email"];
    if(!identity.some(field=>String(draft[field]||"").trim()))return 0;
    // Field changes may reach local storage before an in-flight checkpoint
    // request survives navigation. Recover the contiguous, exact saved inputs;
    // the backend still requires the actual business transaction to pass.
    for(let index=1;index<lesson.steps.length;index++) {
      const step=lesson.steps[index],field=fields[step.target];
      if(!field)return index;
      if(field&&String(draft[field])!==String(step.value))return index;
    }
    return checkpoint;
  } catch { return 0; }
}
