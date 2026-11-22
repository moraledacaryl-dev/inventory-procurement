import { expect, test } from "@playwright/test";
const email=process.env.E2E_OWNER_EMAIL||"owner@example.com";
const password=process.env.E2E_OWNER_PASSWORD||"password123";

test("receiving history pages independently on desktop and mobile",async({page})=>{
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button",{name:"Sign in"}).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  const seen:{receipts:number;returns:number}[]=[];
  await page.route("**/api/v1/receiving/workspace?*",async route=>{
    const url=new URL(route.request().url());
    const receiptsPage=Number(url.searchParams.get("receipts_page")||1);
    const returnsPage=Number(url.searchParams.get("returns_page")||1);
    seen.push({receipts:receiptsPage,returns:returnsPage});
    const original=await route.fetch();
    expect(original.ok()).toBeTruthy();
    const body=await original.json();
    const startR=(receiptsPage-1)*25+1;
    const startT=(returnsPage-1)*25+1;
    const lengthR=receiptsPage===1?25:1;
    const lengthT=returnsPage===1?25:1;
    body.receipts=Array.from({length:lengthR},(_,i)=>{
      const number=startR+i;
      return {
        id:`receipt-${number}`,goods_receipt_number:`GRN-QA-${number}`,
        purchase_order_id:"po-qa",purchase_order_number:"VPO-2026-001",
        supplier_code:"CAFE-SUPPLY",supplier_name:"Cafe Supply Partner",
        delivery_location_code:"MAIN",stock_document_id:"doc-qa",
        delivery_reference:`DR-QA-${number}`,accepted_value:"25",
        rejected_value:"0",has_discrepancy:false,received_at:"2026-11-22T08:00:00Z",
      };
    });
    body.returns=Array.from({length:lengthT},(_,i)=>{
      const number=startT+i;
      return {
        id:`return-${number}`,return_number:`PRTN-QA-${number}`,
        purchase_order_id:"po-qa",purchase_order_number:"VPO-2026-001",
        supplier_code:"CAFE-SUPPLY",supplier_name:"Cafe Supply Partner",
        stock_document_id:"doc-qa",reason:"Quality inspection",
        created_at:"2026-11-22T08:00:00Z",
      };
    });
    body.summary={...body.summary,receipts:26,returns:26};
    body.pagination={
      receipts:{page:receiptsPage,page_size:25,total:26,has_previous:receiptsPage>1,has_next:receiptsPage===1},
      returns:{page:returnsPage,page_size:25,total:26,has_previous:returnsPage>1,has_next:returnsPage===1},
    };
    await route.fulfill({response:original,contentType:"application/json",body:JSON.stringify(body)});
  });
  await page.goto("/receiving");
  await expect(page.getByText("Showing 1–25 of 26 receipts")).toBeVisible();
  await expect(page.getByText("Showing 1–25 of 26 returns")).toBeVisible();
  await expect(page.getByRole("link",{name:"GRN-QA-1",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Next receipts"}).click();
  await expect(page.getByText("Showing 26–26 of 26 receipts")).toBeVisible();
  await expect(page.getByRole("link",{name:"GRN-QA-26",exact:true})).toBeVisible();
  await expect(page.getByText("Showing 1–25 of 26 returns")).toBeVisible();
  await page.getByRole("button",{name:"Next returns"}).click();
  await expect(page.getByText("Showing 26–26 of 26 returns")).toBeVisible();
  await expect(page.getByText("Showing 26–26 of 26 receipts")).toBeVisible();
  await page.getByRole("button",{name:"Previous receipts"}).click();
  await expect(page.getByText("Showing 1–25 of 26 receipts")).toBeVisible();
  expect(seen).toEqual(expect.arrayContaining([
    {receipts:1,returns:1},{receipts:2,returns:1},
    {receipts:2,returns:2},{receipts:1,returns:2},
  ]));
  if(page.viewportSize()&&page.viewportSize()!.width<760){
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(2);
  }
});
