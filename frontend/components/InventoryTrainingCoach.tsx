"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { trainingEnabled, trainingOutcomeMatches, type TrainingLesson, type TrainingProfile } from "../lib/inventory-training";
import { readTrainingReceiptDraft } from "../lib/training-receiving-draft";
import { restoreCatalogueCheckpoint } from "../lib/training-form-draft";
import {rememberTrainingAttempt,trainingAttempt} from "../lib/training-session";
import "./inventory-training-coach.css";

type Box = { top: number; left: number; width: number; height: number };

export function InventoryTrainingCoach() {
  const pathname = usePathname();
  const [profile,setProfile] = useState<TrainingProfile|null>(null);
  const [step,setStep] = useState(0);
  const [rect,setRect] = useState<Box|null>(null);
  const [panel,setPanel] = useState<Box|null>(null);
  const [error,setError] = useState("");
  const [answer,setAnswer] = useState("");
  const [observation,setObservation] = useState("");
  const [feedback,setFeedback] = useState("");
  const [passed,setPassed] = useState(false);
  const [busy,setBusy] = useState(false);
  const [showHint,setShowHint] = useState(false);
  const [expanded,setExpanded] = useState(true);
  const [missing,setMissing] = useState(false);
  const [inputMessage,setInputMessage] = useState("");
  const [inspected,setInspected] = useState(false);
  const readPaths = useRef(new Set<string>());
  const coachRef = useRef<HTMLElement>(null);
  const guideRef = useRef<TrainingLesson|null>(null);
  const visible = trainingEnabled && !pathname.startsWith("/training");

  const load = useCallback(async()=>{
    if (!visible) return;
    try {
      const result = await api<TrainingProfile>("/training/me");
      const bound=trainingAttempt();
      if(bound&&result.attempt&&bound!==result.attempt.id)throw new Error("This practice changed in another tab. Return to Training to continue the current task.");
      setProfile(result);
      let checkpoint=result.attempt?.checkpoint||0;
      if(result.lesson&&result.attempt?.status!=="passed"&&checkpoint<result.lesson.steps.length)checkpoint=restoreCatalogueCheckpoint(result.lesson,checkpoint);
      if(result.lesson?.workflow==="receiving"&&checkpoint<result.lesson.steps.length){
        const draft=readTrainingReceiptDraft(),steps=result.lesson.steps;
        const index=(target:string)=>Math.max(0,steps.findIndex(row=>row.target===target));
        if(!draft)checkpoint=0;
        else if(draft.step===1)checkpoint=index('[data-training="receive-next"]');
        else if(draft.step===3)checkpoint=index('[data-training="receive-confirm"]');
        else{
          const line=draft.lines[0];
          checkpoint=index('[data-training="receive-review"]');
          if(!line||Number(line.received)!==result.lesson.quantity)checkpoint=index('[aria-label="Arrived today for Chicken (kg)"]');
          else if(Number(line.rejected)!==result.lesson.rejected)checkpoint=index('[aria-label="Rejected quantity for Chicken (kg)"]');
          else if(result.lesson.rejected&&!line.reason.trim())checkpoint=index('[aria-label="Reason for rejecting Chicken (kg)"]');
          else if(draft.reference!==result.lesson.reference)checkpoint=index('[aria-label="Delivery reference"]');
        }
      }
      setStep(checkpoint);
      setPassed(result.attempt?.status==="passed");
      setInspected(result.record_inspected || readPaths.current.has(result.lesson?.inspection_api_path||""));
      if(result.attempt)rememberTrainingAttempt(result.attempt.id);
      setError("");
    } catch(exception){setError((exception as Error).message)}
  },[visible]);
  useEffect(()=>{void load()},[load]);
  const lesson=profile?.lesson;
  const guided=profile?.attempt?.mode==="guided"||showHint;
  const current=guided?lesson?.steps[step]:undefined;
  const showTaskAmount=lesson&&["issue","receipt","transfer","count","approve_count","receiving","return","waste","purchase_order","approve_po","production","staff_meal","requisition"].includes(lesson.workflow);
  useEffect(()=>{coachRef.current?.scrollTo({top:0,behavior:"instant"})},[current?.instruction]);
  const targetSelector=current?.target;
  useEffect(()=>{
    if(!visible)return;
    const observe=(event:Event)=>{
      const detail=(event as CustomEvent<{path:string;method:string;status:number}>).detail;
      if(detail.method!=="GET"||detail.status!==200)return;
      const path="/api/v1"+detail.path.split("?")[0];readPaths.current.add(path);
      if(path===lesson?.inspection_api_path)setInspected(true);
    };
    window.addEventListener("inventory-training-action",observe);
    if(lesson?.inspection_api_path&&readPaths.current.has(lesson.inspection_api_path))setInspected(true);
    return()=>window.removeEventListener("inventory-training-action",observe);
  },[visible,lesson?.inspection_api_path]);

  useEffect(()=>{
    if(!visible||!targetSelector||!expanded||passed){setRect(null);setPanel(null);return}
    let marked:HTMLElement|null=null;
    let observer:ResizeObserver|null=null;
    let frame=0;
    let reposition=true;
    const missingTimer=window.setTimeout(()=>setMissing(true),5000);
    function refresh(){
      let shouldScroll=reposition;reposition=false;
      const found=Array.from(document.querySelectorAll<HTMLElement>(targetSelector!)).find(node=>{const r=node.getBoundingClientRect();return r.width>0&&r.height>0})||null;
      if(marked!==found){
        shouldScroll=true;
        marked?.removeAttribute("data-inventory-training-focus");observer?.disconnect();
        marked=found;
        if(found){
          setMissing(false);window.clearTimeout(missingTimer);
          found.setAttribute("data-inventory-training-focus","true");
          observer=new ResizeObserver(layoutSchedule);observer.observe(found);
          found.scrollIntoView({block:"center",behavior:"instant"});
        }
      }
      if(!found){setRect(null);return}
      const r=found.getBoundingClientRect();
      const box={top:r.top,left:r.left,width:r.width,height:r.height};
      setRect(previous=>JSON.stringify(previous)===JSON.stringify(box)?previous:box);
      const bannerBottom=document.querySelector(".inventory-training-banner")?.getBoundingClientRect().bottom||54;
      const h=coachRef.current?.getBoundingClientRect().height||260;
      const w=Math.min(360,window.innerWidth-24);
      let x=Math.max(12,Math.min(r.left,window.innerWidth-w-12));
      let y=r.bottom+18;
      if(window.innerWidth<760){
        x=12;y=window.innerHeight-Math.min(h,window.innerHeight*.42)-12;
        if(shouldScroll&&!found.closest('[role="alertdialog"]')&&(r.bottom>y-24||r.top<bannerBottom+3)){window.scrollBy({top:r.top-Math.max(70,(y-r.height)/2),behavior:"instant"})}
      }else if(r.right+w+34<window.innerWidth){x=r.right+22;y=Math.max(bannerBottom+12,Math.min(r.top,window.innerHeight-h-15))}
      else if(r.left-w-24>=12){x=r.left-w-22;y=Math.max(bannerBottom+12,Math.min(r.top,window.innerHeight-h-15))}
      else if(y+h>window.innerHeight-15){
        y=r.top-h-18;
        if(y<bannerBottom+8){y=window.innerHeight-h-15;if(shouldScroll&&r.bottom>y-20)window.scrollBy({top:r.top-75,behavior:"instant"})}
      }
      const pos={top:Math.max(12,y),left:x,width:w,height:h};
      setPanel(previous=>JSON.stringify(previous)===JSON.stringify(pos)?previous:pos);
    }
    function schedule(){window.cancelAnimationFrame(frame);frame=window.requestAnimationFrame(refresh)}
    function layoutSchedule(){reposition=true;schedule()}
    const mutation=new MutationObserver(layoutSchedule);mutation.observe(document.body,{childList:true,subtree:true});
    const panelResize=new ResizeObserver(layoutSchedule);if(coachRef.current)panelResize.observe(coachRef.current);
    window.addEventListener("resize",layoutSchedule);window.addEventListener("scroll",schedule,true);
    window.visualViewport?.addEventListener("resize",layoutSchedule);
    schedule();
    return()=>{window.clearTimeout(missingTimer);window.cancelAnimationFrame(frame);mutation.disconnect();observer?.disconnect();panelResize.disconnect();window.removeEventListener("resize",layoutSchedule);window.removeEventListener("scroll",schedule,true);window.visualViewport?.removeEventListener("resize",layoutSchedule);marked?.removeAttribute("data-inventory-training-focus")}
  },[visible,targetSelector,expanded,passed,pathname]);

  useEffect(()=>{
    if(!current||!profile?.attempt||!visible||passed)return;
    let advancing=false;
    function advance(){
      if(advancing)return;advancing=true;setInputMessage("");
      const next=step+1;setStep(next);
      void api("/training/checkpoint",{method:"POST",body:JSON.stringify({step:next})}).catch(()=>setError("Your guide checkpoint was not saved. Your posted practice records are safe. Use Continue practice to reconnect."));
    }
    function businessOutcome(event:Event){
      const detail=(event as CustomEvent<{path:string;method:string;status:number}>).detail;
      const expected=current?.outcome_status;
      if(current?.outcome&&trainingOutcomeMatches(current.outcome,detail.path)&&detail.method!=="GET"&&(expected?detail.status===expected:detail.status>=200&&detail.status<300))advance();
    }
    function observe(event:Event){
      const target=event.target as HTMLElement;
      const node=target?.closest?.(current!.target);
      if(!node||node instanceof HTMLButtonElement&&node.disabled)return;
      const matchesValue=()=>{
        const input=node as HTMLInputElement;
        if(input instanceof HTMLInputElement&&input.type==="number")return input.value.trim()!==""&&Number.isFinite(Number(input.value))&&Number(input.value)===Number(current!.value);
        return input.value===String(current!.value);
      };
      if(event.type==="focusout"&&current!.value!==null){
        if(!matchesValue())setInputMessage(current!.instruction+" Check the value and unit or code in this task before continuing.");
        else if(!current!.outcome)advance();
        return;
      }
      if(event.type!==current!.event)return;
      if(current!.value!==null&&!matchesValue())return;
      if(!current!.outcome)advance();
    }
    document.addEventListener("click",observe,true);document.addEventListener("input",observe,true);document.addEventListener("change",observe,true);document.addEventListener("focusout",observe,true);
    window.addEventListener("inventory-training-action",businessOutcome);
    return()=>{window.removeEventListener("inventory-training-action",businessOutcome);document.removeEventListener("click",observe,true);document.removeEventListener("input",observe,true);document.removeEventListener("change",observe,true);document.removeEventListener("focusout",observe,true)}
  },[current,profile?.attempt,visible,passed,step]);

  async function hint(){setBusy(true);try{const result=await api<{lesson:TrainingLesson}>("/training/hint",{method:"POST"});guideRef.current=result.lesson;setShowHint(true);setExpanded(true)}catch(exception){setError((exception as Error).message)}finally{setBusy(false)}}
  async function check(){setBusy(true);setFeedback("");try{const result=await api<{passed:boolean;message:string}>("/training/check",{method:"POST",body:JSON.stringify({answer,observation})});setPassed(result.passed);setFeedback(result.message)}catch(exception){setError((exception as Error).message)}finally{setBusy(false)}}
  async function reset(){if(!lesson||!profile?.attempt)return;setBusy(true);try{const result=await api<{attempt_id:string;lesson:TrainingLesson}>("/training/start",{method:"POST",body:JSON.stringify({lesson_id:lesson.id,mode:profile.attempt.mode})});rememberTrainingAttempt(result.attempt_id);window.location.assign(result.lesson.route)}catch(exception){setError((exception as Error).message);setBusy(false)}}
  if(!visible)return null;
  const floating=!!current&&!!panel&&expanded&&!passed;
  return <>
    <div className="inventory-training-banner"><Link href="/training">← Training course</Link><strong>TRAINING ONLY</strong><span>Fictional records · {profile?.attempt?.role.replaceAll("_"," ")||"isolated practice"}</span><button type="button" onClick={()=>setExpanded(value=>!value)} aria-expanded={expanded}>{expanded?"Hide guide":"Show guide"}</button></div>
    {rect&&expanded&&!passed&&<div className="inventory-training-ring" aria-hidden="true" style={{top:rect.top-5,left:rect.left-5,width:rect.width+10,height:rect.height+10}}><span>↓</span></div>}
    {expanded&&<aside ref={coachRef} className={`inventory-training-coach ${floating?"is-floating":"is-docked"}`} style={floating?{top:panel!.top,left:panel!.left,width:panel!.width}:undefined} aria-label="Your training task" aria-live="polite">
      <div className="inventory-training-coach-label">{profile?.attempt?.mode||"Practice"}{current?` · Action ${step+1} of ${lesson?.steps.length}`:""}</div>
      <h2>{passed?"Task passed":lesson?.title||"Continue your training"}</h2>
      {error&&<div role="alert"><p>{error}</p><button onClick={()=>void load()}>Reconnect to practice</button></div>}
      {!lesson&&<Link href="/training">Open your training course</Link>}
      {lesson&&!passed&&<>
        {!current&&<p className="inventory-training-situation">{lesson.situation}</p>}
        {current?<><h3>Your turn</h3><p className="inventory-training-current-instruction">{current.instruction}</p>{inputMessage&&<p className="inventory-training-correction" role="alert">{inputMessage}</p>}{missing&&<div className="inventory-training-correction"><p>The next control is not visible. Return to the practice page, or revisit the previous action if a dialog was closed.</p><Link href={lesson.route}>Open the practice page</Link></div>}<details key={step} className="inventory-training-context"><summary>Review the situation</summary><p>{lesson.situation}</p></details><button className="inventory-training-text-button" disabled={busy} onClick={()=>{const previous=Math.max(0,step-1);setStep(previous);void api("/training/checkpoint",{method:"POST",body:JSON.stringify({step:previous,revisit:true})})}}>Revisit previous action</button><p className="inventory-training-help">Use the outlined control. If an entered value is already correct, review it and move to the next field. Progress saves after each action; the server checks the final result.</p></>:<>
          <p>{lesson.practical_question?"Inspect the record in the application, then enter what it shows.":"Complete the task in the application, then check your saved result below."}</p>
          {lesson.practical_question&&<><Link href={lesson.inspection_route}>Open the record to inspect →</Link><label>{lesson.practical_question}<input value={observation} onChange={event=>setObservation(event.target.value)} autoComplete="off"/></label></>}
          {!lesson.practical_question&&showTaskAmount&&<p>Task amount: {lesson.quantity}{lesson.workflow==="receiving"?` arrived; ${lesson.rejected} rejected`:""}. {lesson.workflow==="production"?"Use 3 kg of chicken; record the actual usable output.":""}{lesson.workflow==="purchase_order"?"Use Training Valley Foods, Training stockroom and PHP 200 per kg.":""}{lesson.workflow==="receiving"?`Delivery reference: ${lesson.reference}`:""}</p>}
          <label>{lesson.question}<input value={answer} onChange={event=>setAnswer(event.target.value)} autoComplete="off" placeholder="Type your answer"/></label>
          {!!lesson.practical_question&&!inspected&&<p role="status">Open the record and wait for it to finish loading before checking your answer.</p>}
          <button className="inventory-training-check" disabled={busy||!answer.trim()||!!lesson.practical_question&&(!observation.trim()||!inspected)} onClick={()=>void check()}>{busy?"Checking saved result…":"Check my work"}</button>
          {!guided&&<button disabled={busy} onClick={()=>void hint()}>{profile?.attempt?.mode==="independent"?"Use a hint (this attempt becomes practice)":"Show me a hint"}</button>}
        </>}
        {!guided&&<button type="button" onClick={()=>setExpanded(false)}>Work in the application</button>}
      </>}
      {feedback&&<p className={passed?"inventory-training-success":"inventory-training-correction"} role="status">{feedback}</p>}
      {passed?<><p>{lesson?.rule}</p><Link className="inventory-training-check" href="/training">Continue your course →</Link></>:lesson&&<div className="inventory-training-recovery"><button disabled={busy} onClick={()=>void reset()}>Reset this practice</button><Link href="/training">Save and return</Link></div>}
    </aside>}
  </>;
}
