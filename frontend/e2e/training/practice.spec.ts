import {readFile} from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";
import type {TrainingLesson} from "../../lib/inventory-training";
import AxeBuilder from "@axe-core/playwright";

const headers={"X-Requested-With":"HiddenOasisInventory"};
async function openTrainingPage(page:Page,path:string){
  try{await page.goto(path)}catch(error){
    if(!String(error).includes("net::ERR_CONNECTION_FAILED"))throw error;
    // Hosted Windows occasionally loses a fresh browser connection while the
    // same native server remains healthy. Retry only this idempotent GET.
    const health=await page.request.get("/api/v1/health");
    expect(health.ok(),"A navigation retry requires a healthy training server").toBeTruthy();
    test.info().annotations.push({type:"navigation-recovery",description:`Retried ${path} once after a healthy sandbox check`});
    await page.goto(path);
  }
}
async function prepare(page:Page,lesson_id:string,role:string){
  expect((await page.request.post("/api/v1/training/enrol",{headers,data:{name:"Fictional browser learner",role}})).ok()).toBeTruthy();
  const response=await page.request.post("/api/v1/training/start",{headers,data:{lesson_id}});
  expect(response.ok(),await response.text()).toBeTruthy();
  const data=await response.json() as {attempt_id:string;lesson:TrainingLesson};
  await openTrainingPage(page,"/training");
  await page.evaluate(id=>{localStorage.setItem("inventory-training-attempt",id);sessionStorage.setItem("inventory-training-attempt",id)},data.attempt_id);
  await openTrainingPage(page,data.lesson.route);
  await expect(page.getByRole("complementary",{name:"Your training task"})).toBeVisible();
  return data;
}

test("a transient initial navigation preserves one prepared attempt",async({page})=>{
  let interrupted=false;
  await page.route("**/training",route=>{
    if(!interrupted&&route.request().resourceType()==="document"){interrupted=true;return route.abort("connectionfailed")}
    return route.continue();
  });
  const prepared=await prepare(page,"issue-kitchen","inventory_manager");
  expect(interrupted).toBeTruthy();
  const profile=await(await page.request.get("/api/v1/training/me")).json();
  expect(profile.history).toHaveLength(1);
  expect(profile.attempt.id).toBe(prepared.attempt_id);
  expect(test.info().annotations.some(row=>row.type==="navigation-recovery")).toBeTruthy();
});

test("the guide follows a target moved by late asset rows",async({page})=>{
  let delayed=false;
  await page.route("**/api/v1/assets",async route=>{
    const response=await route.fetch();
    const body=await response.body();
    if(!delayed){delayed=true;await new Promise(resolve=>setTimeout(resolve,400))}
    await route.fulfill({status:response.status(),headers:response.headers(),body});
  });
  const{lesson}=await prepare(page,"prepare-depreciation-run","inventory_manager");
  await expect(page.getByText("TRAIN-FAN-01",{exact:true})).toBeVisible();
  await guide(page,lesson);
  await page.getByRole("textbox",{name:lesson.question,exact:true}).fill("no");
  await page.getByRole("button",{name:"Check my work",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
  await page.unrouteAll({behavior:"wait"});
});

async function guide(page:Page,lesson:TrainingLesson,screenshotPrefix?:string,startIndex=0,endIndex=lesson.steps.length){
  for(let index=startIndex;index<endIndex;index++){
    const step=lesson.steps[index];
    await expect(page.locator(".inventory-training-coach-label")).toContainText(`Action ${index+1} of`);
    for(let opening=0;opening<3;opening++){
      await expect.poll(()=>page.evaluate(selector=>{
        const focused=document.querySelector<HTMLElement>('[data-inventory-training-focus="true"]');
        const target=document.querySelector(selector);
        return !!focused&&(focused.matches(selector)||focused.getAttribute('aria-label')==='Open navigation'||focused.tagName==='SUMMARY'&&!!target&&!!focused.parentElement?.contains(target));
      },step.target)).toBeTruthy();
      if(await page.locator(step.target).first().getAttribute('data-inventory-training-focus')==="true")break;
      const helper=page.locator('[data-inventory-training-focus="true"]');
      await expect(helper).toBeInViewport({ratio:0.95});
      const openedControl=await helper.elementHandle();
      await openedControl!.click();
      // Opening the menu/disclosure updates the target on the next frame.
      // Wait for this exact control to lose focus before resolving another;
      // a live locator could otherwise click the obscured menu button twice.
      await expect.poll(()=>openedControl!.getAttribute('data-inventory-training-focus')).not.toBe('true');
    }
    await expect(page.locator('.inventory-training-current-instruction')).toHaveText(step.instruction);
    await expect(page.locator('.inventory-training-current-instruction')).toBeInViewport({ratio:0.95});
    const target=page.locator(step.target).first();
    await expect(target).toBeVisible();
    await expect(target).toHaveAttribute("data-inventory-training-focus","true");
    await expect(target).toBeInViewport({ratio:0.95});
    // The guide must not cover its target. Compare the visible rectangles.
    await expect.poll(async()=>{
      const t=await target.boundingBox(),c=await page.locator(".inventory-training-coach").boundingBox();
      if(!t||!c)return -1;
      return Math.max(0,Math.min(t.x+t.width,c.x+c.width)-Math.max(t.x,c.x))*Math.max(0,Math.min(t.y+t.height,c.y+c.height)-Math.max(t.y,c.y));
    }).toBe(0);
    if(screenshotPrefix&&lesson.id.startsWith('cap-')&&(step.target.startsWith('.nav-link')||step.target==='[data-training="integrations-accounting"]'))await page.screenshot({path:`training-test-results/${screenshotPrefix}-handover-${index}.png`});
    if(index===0&&screenshotPrefix)await page.screenshot({path:`training-test-results/${screenshotPrefix}-start.png`});
    if(lesson.id==="award-timely-quotation"&&index===1){
      await expect(page.getByRole("alertdialog").locator(step.target)).toBeVisible();
      if(screenshotPrefix)await page.screenshot({path:`training-test-results/${screenshotPrefix}-dialog.png`});
    }
    if(screenshotPrefix&&((lesson.id==="send-used-linen-to-laundry"&&index===6)||(lesson.id==="create-governed-recipe"&&index===7)))await page.screenshot({path:`training-test-results/${screenshotPrefix}-detail.png`});
    if(step.event==="change"){
      if(await target.getAttribute("type")==="file"){
        const downloading=page.waitForEvent("download");
        await page.getByRole("button",{name:"Download practice CSV",exact:true}).click();
        const file=await downloading;expect(file.suggestedFilename()).toBe(String(step.value));
        const saved=test.info().outputPath(file.suggestedFilename());
        await file.saveAs(saved);
        await target.setInputFiles(saved);
      }else await target.selectOption(String(step.value));
    }
    else if(step.event==="input"){
      if(lesson.id==="create-menu-with-modifier"&&step.target.includes("options")){await target.fill("");await target.pressSequentially(String(step.value));await expect(target).toHaveValue(String(step.value));}
      else await target.fill(String(step.value));
    }
    else await target.click();
  }
  if(endIndex===lesson.steps.length){
    if(lesson.id==="reject-invalid-csv")await expect(page.getByText("Row 3: duplicate SKU in file",{exact:true})).toBeVisible();
    await expect(page.getByRole("button",{name:"Check my work",exact:true})).toBeVisible();
  }
}

test("a new employee starts training with a clear role and next lesson",async({page},info)=>{
  await page.goto("/");
  await expect(page).toHaveURL(/training/);
  await page.getByLabel("Your name").fill("New stockroom colleague");
  await page.getByLabel("Your training responsibilities").selectOption("stockroom");
  await page.getByRole("button",{name:"Start training",exact:true}).click();
  await expect(page.getByRole("heading",{name:/Welcome back, New stockroom/})).toBeVisible();
  await expect(page.getByText("skills demonstrated independently",{exact:true})).toBeVisible();
  await page.screenshot({path:`training-test-results/${info.project.name}-welcome.png`,fullPage:true});
});

test("signing out returns to onboarding and separates the next employee",async({page})=>{
  await prepare(page,"partial-delivery","receiver");
  const first=(await (await page.request.get("/api/v1/training/me")).json()).learner.id;
  await page.getByRole("button",{name:/Account menu for/}).click();
  await page.getByRole("menuitem",{name:"Sign out",exact:true}).click();
  await expect(page.getByLabel("Your name")).toBeVisible();
  await page.getByLabel("Your name").fill("Another employee");
  await page.getByRole("button",{name:"Start training",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Welcome back, Another employee.",exact:true})).toBeVisible();
  const second=await (await page.request.get("/api/v1/training/me")).json();
  expect(second.learner.id).not.toBe(first);
  expect(second.history).toHaveLength(0);
  await page.getByRole("button",{name:"Sign out for another employee",exact:true}).click();
  await expect(page.getByLabel("Your name")).toBeVisible();
});

test("an interrupted item draft restores its fields and acknowledged guide action",async({page})=>{
  const cpu=await page.context().newCDPSession(page);
  await cpu.send("Emulation.setCPUThrottlingRate",{rate:4});
  page.on("dialog",dialog=>dialog.accept());
  const{lesson}=await prepare(page,"create-item","inventory_manager");
  await page.route("**/api/v1/training/checkpoint",route=>{
    if(Number(route.request().postDataJSON()?.step)>=4)return route.abort();
    return route.continue();
  });
  await page.locator('[data-training="item-create-open"]').click();
  await expect(page.locator('#item-workspace')).toHaveAttribute("data-inventory-training-focus","true");
  await page.locator('#item-workspace').selectOption(String(lesson.steps[1].value));
  await expect(page.locator('#item-type')).toHaveAttribute("data-inventory-training-focus","true");
  await page.locator('#item-type').selectOption(String(lesson.steps[2].value));
  await expect(page.locator('#item-sku')).toHaveAttribute("data-inventory-training-focus","true");
  await page.locator('#item-sku').fill("TRAIN-OIL");
  await expect(page.locator('#item-name')).toHaveAttribute("data-inventory-training-focus","true");
  await page.locator('#item-name').fill("Training cooking oil");
  await expect(page.locator('#item-name')).toHaveValue("Training cooking oil");
  await expect(page.locator('.inventory-training-coach-label')).toContainText("Action 6 of");
  await expect.poll(()=>page.evaluate(()=>Object.entries(localStorage).some(([key,value])=>key.startsWith("inventory-training:draft:")&&JSON.parse(value).name==="Training cooking oil"))).toBeTruthy();
  await page.unroute("**/api/v1/training/checkpoint");
  await page.reload();
  await expect(page.locator('#item-name')).toHaveValue("Training cooking oil");
  await guide(page,lesson,undefined,5);
  await page.getByRole("textbox",{name:lesson.question,exact:true}).fill("no");
  await page.getByRole("button",{name:"Check my work",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
});

test("resetting a supplier practice cannot restore another attempt's draft",async({page})=>{
  page.on("dialog",dialog=>dialog.accept());
  const first=await prepare(page,"create-supplier","procurement_officer");
  await page.locator('[data-training="supplier-create-open"]').click();
  await page.locator('#supplier-code').fill("UNFINISHED-OLD");
  await expect.poll(()=>page.evaluate(()=>Object.values(localStorage).some(value=>value.includes("UNFINISHED-OLD")))).toBeTruthy();
  const second=await prepare(page,"create-supplier","procurement_officer");
  expect(first.attempt_id).not.toBe(second.attempt_id);
  await expect(page.locator('#supplier-code')).toHaveValue("");
  const me=await(await page.request.get("/api/v1/training/me")).json();
  expect(me.history.some((row:{id:string;status:string})=>row.id===first.attempt_id&&row.status==="reset")).toBeTruthy();
});

test("a committed catalogue item resumes at assessment after its draft clears",async({page})=>{
  const{lesson}=await prepare(page,"create-item","inventory_manager");
  await guide(page,lesson);
  await page.reload();
  await expect(page.locator('.inventory-training-current-instruction')).toHaveCount(0);
  await page.getByRole("textbox",{name:lesson.question,exact:true}).fill("no");
  await page.getByRole("button",{name:"Check my work",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
});

test("an older tab cannot post into practice started in a different tab",async({page,context})=>{
  const first=await prepare(page,"issue-kitchen","inventory_manager");
  await page.locator('[data-training="stock-open"]').click();
  await page.locator('#stock-kind').selectOption("issue");
  await page.locator('#stock-location').selectOption("training-store");
  await page.locator('#stock-item').selectOption("training-chicken");
  await page.locator('#stock-quantity').fill("5");
  await page.locator('#stock-reason').fill("Kitchen preparation");
  await page.locator('[data-training="stock-review"]').click();
  const other=await context.newPage();
  const second=await prepare(other,"issue-kitchen","inventory_manager");
  expect(second.attempt_id).not.toBe(first.attempt_id);
  const refused=page.waitForResponse(response=>response.url().endsWith('/stock/issues')&&response.status()===409);
  await page.locator('[data-training="confirm"]').click();
  expect((await(await refused).json()).detail).toContain("another tab");
  const result=await other.request.post('/api/v1/training/check',{headers:{...headers,'X-Training-Attempt':second.attempt_id},data:{answer:'issue'}});
  expect((await result.json()).passed).toBeFalsy();
  await other.close();
});

test("a newly created blind count resumes its real record and unfinished line",async({page,isMobile})=>{
  const{lesson}=await prepare(page,"start-full-count","counter");
  await page.locator('[data-training="count-create-open"]').click();
  await page.locator('#count-location').selectOption("training-store");
  await page.locator('#count-threshold').fill("1");
  await page.locator('#count-notes').fill(lesson.reference);
  await page.locator('[data-training="count-create-save"]').click();
  await expect(page).toHaveURL(/\/counts\/[a-f0-9-]{36}$/);
  const record=new URL(page.url()).pathname;
  await page.getByRole("spinbutton",{name:"Counted quantity for Chicken (kg)",exact:true}).fill(String(lesson.quantity));
  if(isMobile){
    // A partial Save is outside the next guided field. Scroll the real page,
    // as an employee does when pausing before finishing the remaining lines.
    await page.mouse.move(8,350);await page.mouse.wheel(0,400);
  }
  await Promise.all([page.waitForResponse(response=>response.url().endsWith('/entries')&&response.status()===200),page.locator('[data-training="count-save"]').click()]);
  await page.getByRole("link",{name:"← Training course",exact:true}).click();
  const resume=page.getByRole("link",{name:"Continue practice →",exact:true});
  await expect(resume).toHaveAttribute("href",record);
  await resume.click();
  await expect(page).toHaveURL(new RegExp(record+'$'));
  await expect(page.getByRole("columnheader",{name:"Snapshot",exact:true})).toHaveCount(0);
  await guide(page,lesson,undefined,6);
  await page.getByRole("textbox",{name:lesson.question,exact:true}).fill("no");
  await page.getByRole("button",{name:"Check my work",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
  await expect(page.getByRole("columnheader",{name:"Snapshot",exact:true})).toHaveCount(0);
});

test("a correctly prefilled transfer amount can be reviewed without retyping",async({page})=>{
  const{lesson}=await prepare(page,"receive-controlled-transfer","inventory_manager");
  await page.locator('[data-training="transfer-receive-training-transfer"]').click();
  const amount=page.getByRole("spinbutton",{name:"Accepted transfer quantity for Chicken (kg)",exact:true});
  await amount.focus();
  await amount.press("Tab");
  await expect(page.locator('.inventory-training-coach-label')).toContainText("Action 3 of");
  await page.locator('[data-training="transfer-receipt-save"]').click();
  await page.getByRole("textbox",{name:lesson.question,exact:true}).fill("no");
  await page.getByRole("button",{name:"Check my work",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
});

for(const[lesson,role,answer]of[
  ["cap-busy-weekend","procurement_officer","no"],
  ["cap-restaurant-service","inventory_manager","no"],
  ["cap-housekeeping","inventory_manager","no"],
  ["cap-owner-review","owner","no"],
  ["cap-monthly-count","counter","no"],
  ["cap-delivery-recovery","receiver","no"],
  ["accept-accountable-operations-work","owner","no"],
  ["reject-duplicate-operations-work","owner","no"],
  ["complete-evidenced-operations-work","owner","no"],
  ["requeue-failed-accounting-handoff","owner","no"],
  ["issue-clean-linen","inventory_manager","no"],
  ["send-used-linen-to-laundry","inventory_manager","no"],
  ["return-clean-linen","inventory_manager","no"],
  ["configure-room-par","inventory_manager","no"],
  ["register-fixed-asset","inventory_manager","no"],
  ["create-maintenance-plan","inventory_manager","no"],
  ["create-maintenance-work-order","inventory_manager","no"],
  ["start-maintenance-work","inventory_manager","no"],
  ["complete-maintenance-work","inventory_manager","no"],
  ["prepare-depreciation-run","inventory_manager","no"],
  ["post-reviewed-depreciation","inventory_manager","no"],
  ["create-governed-recipe","inventory_manager","no"],
  ["approve-colleague-recipe","inventory_manager","no"],
  ["recipe-self-approval","inventory_manager","no"],
  ["retire-obsolete-recipe","inventory_manager","no"],
  ["plan-production-batch","inventory_manager","no"],
  ["unlink-obsolete-supplier-item","procurement_officer","no"],
  ["create-authorized-storage-location","owner","no"],
  ["correct-storage-location-label","owner","no"],
  ["stock-screen-signed-correction","inventory_manager","no"],
  ["assign-menu-selling-controls","inventory_manager","no"],
  ["retry-eligible-inbound-event","owner","no"],
  ["activate-verified-pos-mapping","owner","no"],
  ["calculate-food-margin","inventory_manager","no"],

  ["assign-location-approval-scope","owner","no"],
  ["create-operating-department","owner","no"],
  ["retire-unused-classification","owner","no"],
  ["classify-legacy-ingredient","owner","no"],
  ["create-accounting-mapping","owner","no"],
  ["save-report-scope","owner","no"],
  ["acknowledge-operational-alert","inventory_manager","no"],
  ["submit-workflow-feedback","inventory_manager","no"],
  ["resolve-verified-feedback","owner","no"],
  ["resolve-verified-incident","owner","no"],
  ["record-assurance-review","owner","no"],
  ["run-isolated-acceptance","owner","no"],
  ["check-isolated-rollout","owner","no"],
  ["import-item-catalogue","owner","no"],
  ["import-supplier-catalogue","owner","no"],
  ["reject-invalid-csv","owner","no"],
  ["import-initial-balances","owner","no"],
  ["refuse-duplicate-opening-import","owner","no"],

  ["create-conditional-price-rule","inventory_manager","no"],
  ["deactivate-conditional-price-rule","inventory_manager","no"],
  ["create-reusable-add-ons","inventory_manager","no"],
  ["correct-reusable-add-on-price","inventory_manager","no"],
  ["cancel-unstarted-production","inventory_manager","no"],
  ["cancel-started-production","inventory_manager","no"],
  ["issue-cafe-case","inventory_manager","no"],
  ["issue-bar-volume","inventory_manager","no"],

  ["reverse-duplicate-staff-meal","inventory_manager","no"],
  ["create-menu-with-modifier","inventory_manager","no"],
  ["map-pos-product","owner","no"],
  ["disable-stale-pos-mapping","owner","no"],
  ["approve-purchase-request","procurement_officer","no"],
  ["reject-duplicate-request","procurement_officer","no"],
  ["request-self-approval","procurement_officer","no"],
  ["record-supplier-quotation","procurement_officer","no"],
  ["award-timely-quotation","procurement_officer","no"],
  ["purchase-approval-limit","procurement_officer","no"],
  ["amend-draft-order","procurement_officer","no"],
  ["cancel-unreceived-order","procurement_officer","no"],
  ["reserve-event-stock","inventory_manager","no"],
  ["reservation-shortage","inventory_manager","no"],
  ["create-controlled-transfer","inventory_manager","no"],
  ["dispatch-controlled-transfer","inventory_manager","no"],
  ["receive-controlled-transfer","inventory_manager","no"],
  ["transfer-receipt-variance","inventory_manager","no"],
  ["cancel-draft-transfer","inventory_manager","no"],
  ["correct-transfer-destination","inventory_manager","no"],
  ["transfer-stock-became-unavailable","inventory_manager","no"],
  ["transfer-transit-scope-required","inventory_manager","no"],
  ["count-multiple-units","counter","2.5"],
  ["start-full-count","counter","no"],
  ["save-incomplete-count","counter","no"],
  ["request-count-recheck","inventory_manager","no"],
  ["stale-count-snapshot","counter","no"],
  ["cancel-unused-count","inventory_manager","no"],
  ["approved-opening-correction","inventory_manager","no"],
  ["create-traceable-lot","inventory_manager","no"],
  ["tracked-opening-receipt","inventory_manager","no"],
  ["issue-specific-lot","inventory_manager","no"],
  ["expired-lot-writeoff","inventory_manager","no"],
  ["lot-quantity-shortage","inventory_manager","no"],
  ["create-item","inventory_manager","no"],
  ["edit-item-reorder","inventory_manager","no"],
  ["add-item-barcode","inventory_manager","no"],
  ["remove-item-barcode","inventory_manager","no"],
  ["define-unit-conversion","inventory_manager","1000"],
  ["set-location-policy","inventory_manager","no"],
  ["deactivate-empty-item","inventory_manager","no"],
  ["reactivate-item","inventory_manager","no"],
  ["stock-blocks-deactivation","inventory_manager","no"],
  ["catalogue-scope-required","inventory_manager","no"],
  ["create-supplier","procurement_officer","no"],
  ["edit-supplier-terms","procurement_officer","no"],
  ["link-supplier-item","procurement_officer","no"],
  ["deactivate-unused-supplier","procurement_officer","no"],
  ["reactivate-supplier","procurement_officer","no"],
  ["open-orders-block-deactivation","procurement_officer","no"],
  ["full-delivery","receiver","no"],
  ["expired-delivery","receiver","no"],
  ["quantity-discrepancy","receiver","no"],
  ["wrong-item","receiver","no"],
  ["later-delivery","receiver","no"],
  ["check-order","receiver","no"],
  ["resume-delivery","receiver","no"],
  ["partial-delivery","receiver","no"],
  ["damaged-delivery","receiver","no"],
  ["fully-rejected","receiver","no"],
  ["blind-count","counter","0"],
  ["count-zero","counter","no"],
  ["approve-count","inventory_manager","no"],
  ["issue-kitchen","inventory_manager","issue"],
  ["transfer-stock","inventory_manager","no"],
  ["opening-stock","inventory_manager","no"],
  ["record-waste","inventory_manager","no"],
  ["order-supplies","procurement_officer","no"],
  ["request-purchase","procurement_officer","no"],
  ["purchase-approval","procurement_officer","no"],
  ["supplier-return","receiver","no"],
  ["staff-meal","inventory_manager","yes"],
  ["batch-production","inventory_manager","no"],
  ["housekeeping-supplies","inventory_manager","12"],
] as const){
  test(`${role}: perform ${lesson} using actual controls`,async({page},info)=>{
    if(lesson==="reverse-duplicate-staff-meal")page.on("dialog",dialog=>dialog.accept());
    const{lesson:task}=await prepare(page,lesson,role);
    if(lesson==="check-order"){
      const choices=page.getByRole("combobox",{name:"Purchase order",exact:true});
      await expect(choices.locator('option').filter({hasText:'TRAIN-PO-WRONG'})).toHaveCount(1);
      await expect(choices.locator('option').filter({hasText:'TRAIN-PO —'})).toHaveCount(1);
    }
    await guide(page,task,`${info.project.name}-${lesson}`);
    const coach=page.getByRole("complementary",{name:"Your training task"});
    await coach.getByRole("textbox",{name:task.question,exact:true}).fill(answer);
    await coach.getByRole("button",{name:"Check my work",exact:true}).click();
    await expect(coach.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
    await page.screenshot({path:`training-test-results/${info.project.name}-${lesson}-passed.png`});
    if(lesson==="transfer-receipt-variance"){
      await page.getByRole("button",{name:"Hide guide",exact:true}).click();
      await page.getByRole("link",{name:"TRAIN-TRANSFER",exact:true}).locator("xpath=ancestor::tr").screenshot({path:`training-test-results/${info.project.name}-transfer-variance-record.png`});
    }
  });
}

test("incorrect quantities get guidance and do not pass; saved counts resume",async({page})=>{
  const{lesson}=await prepare(page,"blind-count","counter");
  const field=page.getByRole("spinbutton",{name:"Counted quantity for Chicken (kg)",exact:true});
  await field.fill("24");await field.blur();
  await expect(page.locator(".inventory-training-correction")).toContainText("21");
  await field.fill("21");await page.getByRole("button",{name:"Save my counts",exact:true}).click();
  await page.reload();
  await expect(field).toHaveValue("21.0000");
  await expect(page.locator(".inventory-training-coach-label")).toContainText("Action 3 of");
  await page.getByRole("button",{name:"Submit saved count",exact:true}).click();
  await page.getByRole("button",{name:"Submit count",exact:true}).click();
  await page.getByRole("textbox",{name:lesson.question,exact:true}).fill("0");
  await page.getByRole("button",{name:"Check my work",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
});

test("a reviewer inspects actual stock and answers the record question",async({page})=>{
  const{lesson}=await prepare(page,"available-stock","viewer");
  await page.getByRole("textbox",{name:lesson.question,exact:true}).fill("available");
  await page.getByRole("textbox",{name:lesson.practical_question,exact:true}).fill("20");
  await page.getByRole("button",{name:"Check my work",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
});

test("an interrupted receiving draft restores quantities and the correct guide control",async({page})=>{
  const{lesson}=await prepare(page,"resume-delivery","receiver");
  await page.getByRole("combobox",{name:"Purchase order",exact:true}).selectOption("training-po");
  await page.locator('[data-training="receive-next"]').click();
  await page.getByRole("spinbutton",{name:"Arrived today for Chicken (kg)",exact:true}).fill("8");
  await page.getByRole("spinbutton",{name:"Rejected quantity for Chicken (kg)",exact:true}).fill("0");
  await page.getByRole("textbox",{name:"Delivery reference",exact:true}).fill(lesson.reference);
  await expect.poll(()=>page.evaluate(()=>Object.entries(localStorage).some(([key,value])=>key.startsWith("inventory-training-receiving:")&&JSON.parse(value).reference?.includes("RESUME-DELIVERY")))).toBeTruthy();
  await page.reload();
  await expect(page.getByRole("spinbutton",{name:"Arrived today for Chicken (kg)",exact:true})).toHaveValue("8");
  await expect(page.getByRole("textbox",{name:"Delivery reference",exact:true})).toHaveValue(lesson.reference);
  await expect(page.locator('[data-training="receive-review"]')).toHaveAttribute("data-inventory-training-focus","true");
  await page.locator('[data-training="receive-review"]').click();
  await page.locator('[data-training="receive-confirm"]').click();
  await page.locator('[data-training="confirm"]').click();
  await page.getByRole("textbox",{name:lesson.question,exact:true}).fill("no");
  await page.getByRole("button",{name:"Check my work",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
});

for(const[id,role,answer,observation]of[
  ["counter-foundations","counter","no","kg"],
  ["inspect-awarded-order","procurement_officer","no","draft"],
  ["inspect-approved-order-lock","procurement_officer","no","approved"],
  ["inspect-received-order-lock","procurement_officer","no","5"],
  ["find-your-work","inventory_manager","no","1"],
  ["catalogue-units","inventory_manager","1000","1000"],
  ["supplier-profile","procurement_officer","no","3"],
  ["expiry-rotation","inventory_manager","no","5"],
  ["recipe-cost","inventory_manager","1","50"],
  ["menu-mapping","inventory_manager","no","250"],
  ["asset-maintenance","inventory_manager","no","20000"],
  ["accounting-proof","owner","no","ready for review"],
  ["connected-work","owner","no","submitted"],
  ["management-review","viewer","no","2000"],
  ["admin-controls","owner","no","1000"],
]as const){
  test(`${role}: inspect ${id} in its actual workspace`,async({page},info)=>{
    const{lesson}=await prepare(page,id,role);
    const coach=page.getByRole("complementary",{name:"Your training task"});
    if(lesson.steps.length)await guide(page,lesson);
    else await coach.getByRole("link",{name:"Open the record to inspect →",exact:true}).click();
    if(id==="inspect-awarded-order")await page.getByRole("link",{name:"Open TRAIN-PO",exact:true}).click();
    if(id==="inspect-approved-order-lock"||id==="inspect-received-order-lock")await expect(page.locator('[data-training="po-amend-save"]')).toHaveCount(0);
    if(id==="inspect-received-order-lock")await expect(page.locator('[data-training="po-cancel"]')).toHaveCount(0);
    await coach.getByRole("textbox",{name:lesson.question,exact:true}).fill(answer);
    await coach.getByRole("textbox",{name:lesson.practical_question,exact:true}).fill(observation);
    await coach.getByRole("button",{name:"Check my work",exact:true}).click();
    await expect(coach.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
    await page.screenshot({path:`training-test-results/${info.project.name}-${id}-review.png`});
  });
}

test("guided, assisted and independent tasks earn one demonstrated skill",async({page})=>{
  const prepared=await prepare(page,"issue-kitchen","inventory_manager");
  let task=prepared.lesson;
  for(const mode of ["guided","assisted","independent"]){
    if(mode!=="guided"){
      await page.getByRole("link",{name:"Continue your course →",exact:true}).click();
      await page.getByRole("button",{name:"Issue chicken to the kitchen",exact:true}).click();
      await expect(page.getByRole("dialog",{name:"Lesson overview"})).toBeVisible();
      await page.getByRole("button",{name:`Start ${mode} practice`,exact:true}).click();
      await expect(page).toHaveURL(/\/stock$/);
      task=(await(await page.request.get("/api/v1/training/me")).json()).lesson;
    }
    if(mode==="guided")await guide(page,task);
    else{
      await page.getByRole("button",{name:"Work in the application",exact:true}).click();
      await page.locator('[data-training="stock-open"]').click();
      await page.locator("#stock-kind").selectOption("issue");
      await page.locator("#stock-location").selectOption("training-store");
      await page.locator("#stock-item").selectOption("training-chicken");
      await page.locator("#stock-quantity").fill(String(task.quantity));
      await page.locator("#stock-reason").fill("Kitchen preparation");
      await page.locator('[data-training="stock-review"]').click();
      await Promise.all([page.waitForResponse(response=>response.url().endsWith("/stock/issues")&&response.status()===201),page.locator('[data-training="confirm"]').click()]);
      await page.getByRole("button",{name:"Show guide",exact:true}).click();
    }
    await page.getByRole("textbox",{name:task.question,exact:true}).fill("issue");
    await page.getByRole("button",{name:"Check my work",exact:true}).click();
    await expect(page.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
  }
  await page.getByRole("link",{name:"Continue your course →",exact:true}).click();
  await expect(page.getByText("Independent task passed",{exact:true})).toHaveCount(1);
});

test("new training pages and guidance have no serious accessibility violations",async({page})=>{
  await page.goto("/training");
  await expect(page.getByLabel("Your name")).toBeVisible();
  let result=await new AxeBuilder({page}).include(".inventory-training").analyze();
  expect(result.violations.filter(row=>["serious","critical"].includes(row.impact||""))).toEqual([]);
  await prepare(page,"blind-count","counter");
  result=await new AxeBuilder({page}).include(".inventory-training-coach").include(".inventory-training-banner").analyze();
  expect(result.violations.filter(row=>["serious","critical"].includes(row.impact||""))).toEqual([]);
});


test("an unfinished monthly count cannot be refreshed over unsaved observations",async({page})=>{
  const{lesson}=await prepare(page,"cap-monthly-count","counter");
  const field=page.getByRole("spinbutton",{name:"Counted quantity for Chicken (kg)",exact:true});
  await field.fill(String(lesson.quantity));
  await expect(page.locator('[data-training="count-refresh"]')).toBeDisabled();
  await page.reload();
  await expect(field).toHaveValue("");
  await expect(page.locator('.inventory-training-coach-label')).toContainText("Action 1 of");
});

test("linked linen resumes the next handover with its disclosure closed",async({page})=>{
  const{lesson}=await prepare(page,"cap-housekeeping","inventory_manager");
  await guide(page,lesson,undefined,0,19);
  await page.reload();
  await expect(page).toHaveURL(/hotel\/property/);
  await guide(page,lesson,undefined,19);
  await page.getByRole("textbox",{name:lesson.question,exact:true}).fill("no");
  await page.getByRole("button",{name:"Check my work",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
});


test("batch cancellation explains missing details inside its dialog",async({page})=>{
  const {lesson}=await prepare(page,"cancel-started-production","inventory_manager");
  await page.locator('[data-training="production-cancel"]').click();
  await page.getByRole("button",{name:"Hide guide",exact:true}).click();
  const dialog=page.getByRole("alertdialog",{name:"Cancel this production batch?",exact:true});
  await dialog.getByRole("button",{name:"Cancel batch",exact:true}).click();
  await expect(dialog.getByRole("alert")).toContainText("Explain the cancellation");
  await dialog.getByLabel("Batch cancellation reason",{exact:true}).fill("Service plan changed");
  await dialog.getByRole("button",{name:"Cancel batch",exact:true}).click();
  await expect(dialog.getByRole("alert")).toBeVisible();
  await expect(dialog.getByLabel("Batch cancellation reason",{exact:true})).toHaveValue("Service plan changed");
  await dialog.getByLabel("Batch material disposition",{exact:true}).fill("No materials issued; ingredients remain in storage");
  await dialog.getByRole("button",{name:"Cancel batch",exact:true}).click();
  await expect(dialog).toHaveCount(0);
  await page.reload();
  await page.getByRole("textbox",{name:lesson.question,exact:true}).fill("no");
  await page.getByRole("button",{name:"Check my work",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
});

test("a stale batch cancellation retains details and shows the actual refusal",async({page})=>{
  const prepared=await prepare(page,"cancel-started-production","inventory_manager");
  await page.locator('[data-training="production-cancel"]').click();
  await page.getByRole("button",{name:"Hide guide",exact:true}).click();
  const dialog=page.getByRole("alertdialog",{name:"Cancel this production batch?",exact:true});
  await dialog.getByLabel("Batch cancellation reason",{exact:true}).fill("Service plan changed");
  await dialog.getByLabel("Batch material disposition",{exact:true}).fill("No materials issued; ingredients remain in storage");
  const response=await page.request.post("/api/v1/production-batches/training-batch/cancel",{headers:{...headers,"X-Training-Attempt":prepared.attempt_id},data:{reason:"Service plan changed",material_disposition:"No materials issued; ingredients remain in storage"}});
  expect(response.ok(),await response.text()).toBeTruthy();
  await dialog.getByRole("button",{name:"Cancel batch",exact:true}).click();
  await expect(dialog.getByRole("alert")).toContainText("Only open batches can be cancelled");
  await expect(dialog.getByLabel("Batch material disposition",{exact:true})).toHaveValue("No materials issued; ingredients remain in storage");
  await dialog.getByRole("button",{name:"Keep batch",exact:true}).click();
  await page.reload();
  await expect(page.locator('[data-training="production-cancel"]')).toHaveCount(0);
});


test("a validated CSV resumes its original apply job after interruption",async({page})=>{
  const {lesson}=await prepare(page,"import-item-catalogue","owner");
  await guide(page,lesson,undefined,0,3);
  await expect(page.getByText("Import validated and ready to apply.",{exact:true})).toBeVisible();
  await page.reload();
  await expect(page.locator('.inventory-training-coach-label')).toContainText('Action 4 of');
  await guide(page,lesson,undefined,3);
  await page.getByRole("textbox",{name:lesson.question,exact:true}).fill("no");
  await page.getByRole("button",{name:"Check my work",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
  const profile=await(await page.request.get('/api/v1/training/me')).json();
  const jobs=await(await page.request.get('/api/v1/migration/imports',{headers:{...headers,'X-Training-Attempt':profile.attempt.id}})).json();
  expect(jobs).toHaveLength(1);expect(jobs[0].status).toBe('applied');
});


test("a costing location change waits for its retained replacement control",async({page})=>{
  let delayed=false;
  await page.route('**/api/v1/recipes/training-recipe/costing-detail?location_id=training-store',async route=>{
    const response=await route.fetch(),body=await response.body();
    if(!delayed){delayed=true;await new Promise(resolve=>setTimeout(resolve,500))}
    await route.fulfill({status:response.status(),headers:response.headers(),body});
  });
  const {lesson}=await prepare(page,'calculate-food-margin','inventory_manager');
  await guide(page,lesson,undefined,0,1);
  await expect(page.locator('.inventory-training-coach-label')).toContainText('Action 2 of');
  await expect(page.getByLabel('Recipe costing location',{exact:true})).toHaveValue('training-store');
  await guide(page,lesson,undefined,1);
  await page.getByRole('textbox',{name:lesson.question,exact:true}).fill('no');
  await page.getByRole('button',{name:'Check my work',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Task passed',exact:true})).toBeVisible();
  await page.unrouteAll({behavior:'wait'});
});

for(const[id,role,observation,visibleText]of[
  ["interpret-stock-valuation","viewer","6000","Inventory value"],
  ["interpret-period-issues","viewer","-6","TRAIN-PERIOD-ISSUE"],
  ["interpret-waste-value","viewer","-1200","TRAIN-WASTE"],
  ["interpret-posted-count","viewer","-3","TRAIN-COUNT"],
  ["interpret-supplier-acceptance","viewer","80","80.00%"],
  ["interpret-actual-yield-cost","viewer","60","TRAIN-ALFREDO"],
  ["interpret-assurance-evidence","viewer","failed","Completed backup is within freshness limit"],
  ["sale-consumption","viewer","-340","TRAIN-SPAGHETTI"],
  ["inspect-pos-duplicate-delivery","viewer","1","TRAIN-SALE-COMPLETED"],
  ["inspect-unmapped-pos-refusal","viewer","0","Failed events"],
  ["inspect-cooked-sale-return","viewer","2","TRAIN-SALE-RETURNED"],
  ["inspect-unused-sale-void","viewer","170","TRAIN-SPAGHETTI"],
]as const){
  test(`${role}: interpret source evidence for ${id}`,async({page},info)=>{
    const{lesson}=await prepare(page,id,role);
    if(lesson.steps.length)await guide(page,lesson,`${info.project.name}-${id}`);
    const coach=page.getByRole("complementary",{name:"Your training task"});
    if(id==="interpret-period-issues"){
      await expect(page.locator('.ledger-summary')).toContainText("-6");
      await expect(page.getByText("TRAIN-EARLIER-ISSUE",{exact:true})).toHaveCount(0);
    }
    if(id==="inspect-cooked-sale-return")await expect(page.locator('[data-training-pos-document="TRAIN-SALE-RETURNED"]')).toHaveCount(0);
    await expect(page.locator('main').getByText(visibleText,{exact:false}).first()).toBeVisible();
    if(id.startsWith("inspect-")||id==="sale-consumption")await expect(page.locator('[data-training^="pos-mapping-toggle-"]')).toHaveCount(0);
    await coach.getByRole("textbox",{name:lesson.question,exact:true}).fill("no");
    await coach.getByRole("textbox",{name:lesson.practical_question,exact:true}).fill(observation);
    await coach.getByRole("button",{name:"Check my work",exact:true}).click();
    await expect(coach.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
    await page.screenshot({path:`training-test-results/${info.project.name}-${id}-passed.png`});
  });
}

test("staff meal shortages preserve physical stock and the unposted proposal",async({page},info)=>{
  const{lesson}=await prepare(page,"staff-meal-shortage","inventory_manager");
  await guide(page,lesson,`${info.project.name}-staff-meal-shortage`);
  await expect(page.getByText(/Insufficient stock for TRAIN-CHICKEN/)).toBeVisible();
  await expect(page.locator('#quantity-0')).toHaveValue("25");
  await page.getByRole("textbox",{name:lesson.question,exact:true}).fill("no");
  await page.getByRole("button",{name:"Check my work",exact:true}).click();
  await expect(page.getByRole("heading",{name:"Task passed",exact:true})).toBeVisible();
});


test("the real report export controls download the current isolated catalogue and balances",async({page},info)=>{
  const prepared=await prepare(page,"interpret-stock-valuation","viewer");
  await expect(page.locator(".operations-metrics")).toContainText("₱6,000.00");
  await page.goto('/reports');
  for(const[label,filename,header,line]of[
    ['Export items','items.csv','sku,name,category_id,base_unit_id,minimum_stock,standard_cost,is_active','TRAIN-CHICKEN,Chicken (kg)'],
    ['Export balances','stock-balances.csv','item_id,location_id,quantity,average_cost','training-chicken,training-store,24.0000,200.0000'],
  ]){
    const downloading=page.waitForEvent('download');await page.getByRole('button',{name:label,exact:true}).click();
    const file=await downloading;expect(file.suggestedFilename()).toBe(filename);
    const saved=info.outputPath(filename);await file.saveAs(saved);const contents=await readFile(saved,'utf8');
    expect(contents).toContain(header);expect(contents).toContain(line);
  }
  const result=await page.request.post('/api/v1/training/check',{headers:{...headers,'X-Training-Attempt':prepared.attempt_id},data:{answer:'no',observation:'6000'}});
  expect(result.ok(),await result.text()).toBeTruthy();expect((await result.json()).passed).toBeTruthy();
});
