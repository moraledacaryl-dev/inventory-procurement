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
  await page.evaluate(id=>localStorage.setItem("inventory-training-attempt",id),data.attempt_id);
  await page.goto(data.lesson.route);
  await expect(page.getByRole("complementary",{name:"Your training task"})).toBeVisible();
  return data;
}

async function guide(page:Page,lesson:TrainingLesson,screenshotPrefix?:string){
  for(let index=0;index<lesson.steps.length;index++){
    const step=lesson.steps[index];
    await expect(page.locator(".inventory-training-coach-label")).toContainText(`Action ${index+1} of`);
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

for(const[lesson,role,answer]of[
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
