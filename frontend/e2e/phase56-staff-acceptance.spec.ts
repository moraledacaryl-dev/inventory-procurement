import { expect, test } from "@playwright/test";

/** Six-role rehearsal on the isolated visual-acceptance database only.
 * These scenarios never confirm a purchase order, receipt, count, or stock post.
 */
const enabled=process.env.VISUAL_CAPTURE==="1";
const password=process.env.E2E_VISUAL_PASSWORD||"visual-acceptance-password";
const roles=[
  {role:"owner",email:"visual-owner@example.com",receive:true,count:true,manual:true,stock:true},
  {role:"inventory_manager",email:"visual-inventory-manager@example.com",receive:false,count:true,manual:false,stock:true},
  {role:"procurement_officer",email:"visual-procurement@example.com",receive:false,count:false,manual:true,stock:false},
  {role:"receiver",email:"visual-receiver@example.com",receive:true,count:false,manual:false,stock:false},
  {role:"counter",email:"visual-counter@example.com",receive:false,count:true,manual:false,stock:false},
  {role:"viewer",email:"visual-viewer@example.com",receive:false,count:false,manual:false,stock:false},
] as const;

async function signIn(page:import("@playwright/test").Page,email:string){
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button",{name:"Sign in"}).click();
  await expect(page).toHaveURL(email.includes("counter")?/\/counts$/:/\/dashboard$/);
}

for(const scenario of roles){
  test("isolated staff walkthrough — "+scenario.role,async({page},testInfo)=>{
    test.skip(!enabled,"Only runs in isolated visual acceptance");
    test.setTimeout(90_000);
    const postRequests:string[]=[];
    const pageErrors:string[]=[];
    page.on("request",request=>{
      if(request.method()==="POST"&&/^\/api\/v1\/(receiving|counts|stock|purchase-orders)(\/|$)/.test(new URL(request.url()).pathname)){
        postRequests.push(request.url());
      }
    });
    page.on("pageerror",error=>pageErrors.push(error.message));
    await signIn(page,scenario.email);

    const userResponse=await page.request.get("/api/v1/auth/me");
    expect(userResponse.status()).toBe(200);
    const currentUser=await userResponse.json();
    expect(currentUser.role).toBe(scenario.role);

    if(scenario.role!=="counter"){
      await page.goto("/receiving");
      await expect(page.getByRole("heading",{name:"Receiving",exact:true})).toBeVisible();
      const receivable=page.getByRole("heading",{name:"Record a delivery"});
      if(scenario.receive){
        await expect(receivable).toBeVisible();
        const selection=page.getByRole("combobox",{name:"Purchase order"});
        const poOption=selection.locator('option').filter({hasText:"VPO-2026-001"}).first();
        await expect(poOption).toHaveCount(1);
        const poId=await poOption.getAttribute("value");
        expect(poId).toBeTruthy();
        await selection.selectOption(poId!);
        await page.getByRole("button",{name:"Next: count the delivery"}).click();
        await expect(page.getByRole("heading",{name:"Step 2: What actually arrived?"})).toBeVisible();
        const firstQuantity=page.locator(".guided-line-table input[aria-label^='Arrived today for']").first();
        await firstQuantity.fill("1");
        await page.getByRole("textbox",{name:"Delivery reference"}).fill("VISUAL-STAFF-DR-DRAFT");
        await page.getByRole("button",{name:"Next: check details"}).click();
        await expect(page.getByRole("heading",{name:"Step 3: Check before posting"})).toBeVisible();
        await page.getByRole("button",{name:"Confirm this delivery"}).click();
        const dialog=page.getByRole("alertdialog",{name:"Post this goods receipt?"});
        await expect(dialog).toBeVisible();
        await dialog.getByRole("button",{name:"Cancel"}).click();
        await expect(dialog).toHaveCount(0);
      }else{
        await expect(receivable).toHaveCount(0);
      }
    }else{
      const disallowed=await page.request.get("/api/v1/receiving/workspace");
      expect(disallowed.status()).toBe(403);
    }

    if(scenario.role!=="receiver"&&scenario.role!=="procurement_officer"){
      await page.goto("/counts");
      await expect(page.getByRole("heading",{name:"Counts",exact:true})).toBeVisible();
      const newCount=page.getByRole("heading",{name:"Start a new count"});
      if(scenario.count)await expect(newCount).toBeVisible();
      else await expect(newCount).toHaveCount(0);
    }else{
      const noCountAccess=await page.request.get("/api/v1/counts");
      expect(noCountAccess.status()).toBe(403);
    }

    if(scenario.role==="owner"||scenario.role==="procurement_officer"||scenario.role==="viewer"||scenario.role==="inventory_manager"){
      await page.goto("/purchasing");
      await expect(page.getByRole("heading",{name:"Purchasing",exact:true})).toBeVisible();
      const manual=page.getByRole("tab",{name:"Manual order"});
      if(scenario.manual){
        await expect(manual).toBeVisible();
        await manual.click();
        await expect(page.getByRole("heading",{name:"Create a purchase order without a quotation"})).toBeVisible();
      }else await expect(manual).toHaveCount(0);
    }

    await page.goto("/stock");
    await expect(page.getByRole("heading",{name:"Stock",exact:true})).toBeVisible();
    const stockAction=page.getByRole("heading",{name:"Record a stock movement"});
    if(scenario.stock)await expect(stockAction).toBeVisible();
    else await expect(stockAction).toHaveCount(0);

    expect(postRequests,"The staff rehearsal must never post a business transaction").toEqual([]);
    expect(pageErrors,"No uncaught browser errors across staff role journey").toEqual([]);
    await testInfo.attach("phase56-"+scenario.role+"-staff-workflow",{
      body:await page.screenshot({fullPage:true}),contentType:"image/png",
    });
  });
}
