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
    for(let index=1;index<Math.min(checkpoint,lesson.steps.length);index++) {
      const step=lesson.steps[index],field=fields[step.target];
      if(field&&String(draft[field])!==String(step.value))return index;
    }
    return checkpoint;
  } catch { return 0; }
}
