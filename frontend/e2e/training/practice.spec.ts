import { expect, test, type Page } from "@playwright/test";
import type {TrainingLesson} from "../../lib/inventory-training";
import AxeBuilder from "@axe-core/playwright";

const headers={"X-Requested-With":"HiddenOasisInventory"};
async function prepare(page:Page,lesson_id:string,role:string){
  expect((await page.request.post("/api/v1/training/enrol",{headers,data:{name:"Fictional browser learner",role}})).ok()).toBeTruthy();
  const response=await page.request.post("/api/v1/training/start",{headers,data:{lesson_id}});
  expect(response.ok(),await response.text()).toBeTruthy();
  const data=await response.json() as {attempt_id:string;lesson:TrainingLesson};
  await page.goto("/training");
  await page.evaluate(id=>{localStorage.setItem("inventory-training-attempt",id);sessionStorage.setItem("inventory-training-attempt",id)},data.attempt_id);
  await page.goto(data.lesson.route);
  await expect(page.getByRole("complementary",{name:"Your training task"})).toBeVisible();
  return data;
}

async function guide(page:Page,lesson:TrainingLesson,screenshotPrefix?:string,startIndex=0){
  for(let index=startIndex;index<lesson.steps.length;index++){
    const step=lesson.steps[index];
    await expect(page.locator(".inventory-training-coach-label")).toContainText(`Action ${index+1} of`);
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
    if(index===0&&screenshotPrefix)await page.screenshot({path:`training-test-results/${screenshotPrefix}-start.png`});
    if(step.event==="change")await target.selectOption(String(step.value));
    else if(step.event==="input")await target.fill(String(step.value));
    else await target.click();
  }
  await expect(page.getByRole("button",{name:"Check my work",exact:true})).toBeVisible();
}

test("a new employee starts training with a clear role and next lesson",async({page},info)=>{
  await page.goto("/");
  await expect(page).toHaveURL(/training/);
  await page.getByLabel("Your name").fill("New stockroom colleague");
  await page.getByLabel("Your training responsibilities").selectOption("inventory_manager");
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
  page.on("dialog",dialog=>dialog.accept());
  const{lesson}=await prepare(page,"create-item","inventory_manager");
  await page.locator('[data-training="item-create-open"]').click();
  await page.locator('#item-workspace').selectOption(String(lesson.steps[1].value));
  await page.locator('#item-type').selectOption(String(lesson.steps[2].value));
  await page.locator('#item-sku').fill("TRAIN-OIL");
  await page.locator('#item-name').fill("Training cooking oil");
  await expect(page.locator('.inventory-training-coach-label')).toContainText("Action 6 of");
  await expect.poll(()=>page.evaluate(()=>Object.entries(localStorage).some(([key,value])=>key.startsWith("inventory-training:draft:")&&JSON.parse(value).name==="Training cooking oil"))).toBeTruthy();
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

test("a newly created blind count resumes its real record and unfinished line",async({page})=>{
  const{lesson}=await prepare(page,"start-full-count","counter");
  await page.locator('[data-training="count-create-open"]').click();
  await page.locator('#count-location').selectOption("training-store");
  await page.locator('#count-notes').fill(lesson.reference);
  await page.locator('[data-training="count-create-save"]').click();
  await expect(page).toHaveURL(/\/counts\/[a-f0-9-]{36}$/);
  const record=new URL(page.url()).pathname;
  await page.getByRole("spinbutton",{name:"Counted quantity for Chicken (kg)",exact:true}).fill(String(lesson.quantity));
  await Promise.all([page.waitForResponse(response=>response.url().endsWith('/entries')&&response.status()===200),page.locator('[data-training="count-save"]').click()]);
  await page.getByRole("link",{name:"← Training course",exact:true}).click();
  const resume=page.getByRole("link",{name:"Continue practice →",exact:true});
  await expect(resume).toHaveAttribute("href",record);
  await resume.click();
  await expect(page).toHaveURL(new RegExp(record+'$'));
  await expect(page.getByRole("columnheader",{name:"Snapshot",exact:true})).toHaveCount(0);
  await guide(page,lesson,undefined,5);
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
    const{lesson:task}=await prepare(page,lesson,role);
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
    await coach.getByRole("link",{name:"Open the record to inspect →",exact:true}).click();
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
