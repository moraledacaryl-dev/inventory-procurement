import { expect, test } from "@playwright/test";

const email=process.env.E2E_OWNER_EMAIL||"owner@example.com";
const password=process.env.E2E_OWNER_PASSWORD||"password123";

async function signIn(page:import("@playwright/test").Page){
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button",{name:"Sign in"}).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("receiving shows choose, count and review steps without posting stock",async({page})=>{
  await signIn(page);
  await page.goto("/receiving");
  await expect(page.getByRole("heading",{name:"Step 1: Which order arrived?"})).toBeVisible();
  const next=page.getByRole("button",{name:"Next: count the delivery"});
  await expect(next).toBeDisabled();
  const options=page.getByRole("combobox",{name:"Purchase order"}).locator("option");
  if(await options.count()>1){
    await page.getByRole("combobox",{name:"Purchase order"}).selectOption({index:1});
    await next.click();
    await expect(page.getByRole("heading",{name:"Step 2: What actually arrived?"})).toBeVisible();
    await expect(page.getByRole("button",{name:"Next: check details"})).toBeDisabled();
    await expect(page.getByText(/Supplier delivery receipt \(DR\) number/)).toBeVisible();
  }
});

test("purchasing tabs work with left/right keyboard arrows",async({page})=>{
  await signIn(page);
  await page.goto("/purchasing");
  const first=page.getByRole("tab",{name:"To order"});
  await first.focus();
  await page.keyboard.press("ArrowRight");
  const second=page.getByRole("tab",{name:"Requests for approval"});
  await expect(second).toBeFocused();
  await expect(second).toHaveAttribute("aria-selected","true");
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("tab",{name:"Quotes & orders"})).toHaveAttribute("aria-selected","true");
});

test("stock modal keeps keyboard focus and restores the previous button",async({page})=>{
  await signIn(page);
  await page.goto("/stock");
  await page.locator(".stock-guided-action > summary").click();
  await expect(page.getByRole("group",{name:"What happened to the stock?"})).toBeVisible();
  await page.locator('select[name="location"]').selectOption({index:1});
  await page.locator('select[name="item"]').selectOption({index:1});
  await page.locator('input[name="quantity"]').fill("1");
  const trigger=page.getByRole("button",{name:"Check before posting"});
  await trigger.click();
  const dialog=page.getByRole("alertdialog",{name:"Post this stock transaction?"});
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button",{name:"Cancel"})).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByRole("button",{name:"Post transaction"})).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("a blind count hides live quantities and prevents submitting unsaved changes",async({page})=>{
  const login=await page.request.post("/api/v1/auth/login",{data:{email,password}});
  expect(login.ok()).toBeTruthy();
  const token=(await login.json()).access_token as string;
  const headers={Authorization:`Bearer ${token}`};
  const locResponse=await page.request.get("/api/v1/locations",{headers});
  expect(locResponse.ok()).toBeTruthy();
  const locations=(await locResponse.json()) as {id:string;is_active:boolean}[];
  const location=locations.find(loc=>loc.is_active);
  expect(location).toBeTruthy();
  const created=await page.request.post("/api/v1/counts",{headers,data:{location_id:location!.id,blind_count:true,approval_threshold:0}});
  expect(created.ok()).toBeTruthy();
  const count=await created.json();
  await signIn(page);
  await page.goto(`/counts/${count.id}`);
  await expect(page.getByRole("heading",{name:"Step 1: Count the items"})).toBeVisible();
  await expect(page.getByRole("columnheader",{name:"Live"})).toHaveCount(0);
  await expect(page.getByRole("columnheader",{name:"Changed during count"})).toHaveCount(0);
  const countInput=page.locator(".count-input").first();
  await expect(countInput).toBeVisible();
  await countInput.fill("0");
  await expect(page.getByRole("button",{name:"Submit saved count"})).toBeDisabled();
  await expect(page.getByRole("button",{name:"Save my counts"})).toBeEnabled();
});

test("mobile receiving item rows show readable labels and fit the viewport",async({page},testInfo)=>{
  test.skip(!testInfo.project.name.includes("mobile"),"Mobile-only check");
  await signIn(page);
  await page.goto("/receiving");
  const selector=page.getByRole("combobox",{name:"Purchase order"});
  if(await selector.locator("option").count()>1){
    await selector.selectOption({index:1});
    await page.getByRole("button",{name:"Next: count the delivery"}).click();
    const cell=page.locator(".guided-line-table td[data-label]").first();
    await expect(cell).toBeVisible();
    await expect(cell).toHaveCSS("display","grid");
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(2);
  }
});
