import {expect,test} from "@playwright/test";

async function signIn(page:import("@playwright/test").Page){
  await page.goto("/login");
  await page.getByLabel("Email address").fill(process.env.E2E_OWNER_EMAIL||"owner@example.com");
  await page.locator('input[name="password"]').fill(process.env.E2E_OWNER_PASSWORD||"password123");
  await page.getByRole("button",{name:"Sign in"}).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("receiving retains quantities, lot fields and DR across history changes and PO search",async({page})=>{
  await signIn(page);
  await page.route("**/api/v1/receiving/workspace?*",async route=>{
    const original=await route.fetch();
    if(!original.ok())return route.fulfill({response:original});
    const body=await original.json();
    // The test database may contain no approved PO. Add a mock-only eligible
    // order to exercise editing without creating or posting real records.
    const search=new URL(route.request().url()).searchParams.get("po_search");
    const mockOrder={
      id:"mock-draft-po",purchase_order_number:"PO-MOCK-DRAFT",
      supplier_id:"mock-supplier",supplier_code:"MOCK-SUP",supplier_name:"Test supplier",
      delivery_location_id:"mock-location",delivery_location_code:"TEST",
      delivery_location_name:"Test storeroom",expected_delivery_date:null,
      status:"approved",ordered_quantity:"5",received_quantity:"0",
      outstanding_quantity:"5",lines:[{
        id:"mock-draft-line",item_id:"mock-item",sku:"MOCK-ITEM",
        item_name:"Test delivery item",ordered_quantity:"5",received_quantity:"0",
        returned_quantity:"0",outstanding_quantity:"5",
        returnable_quantity:"0",unit_price:"10",
      }],
    };
    body.purchase_orders=search==="NO_MATCH_PO"?[]:[mockOrder,...body.purchase_orders];
    // Simulate a large history without posting any business transaction.
    body.pagination.receipts={page:1,page_size:25,total:51,has_previous:false,has_next:true};
    const requested=new URL(route.request().url()).searchParams.get("receipts_page");
    if(requested==="2")body.pagination.receipts={page:2,page_size:25,total:51,has_previous:true,has_next:true};
    if(new URL(route.request().url()).searchParams.get("po_search")==="NO_MATCH_PO")body.purchase_orders=[];
    await route.fulfill({response:original,contentType:"application/json",body:JSON.stringify(body)});
  });
  await page.goto("/receiving");
  const selector=page.getByRole("combobox",{name:"Purchase order"});
  await expect(selector.locator('option[value="mock-draft-po"]')).toHaveCount(1);
  await selector.selectOption("mock-draft-po");
  await page.getByRole("button",{name:"Next: count the delivery"}).click();
  const quantity=page.locator('.guided-line-table input[aria-label^="Arrived today for"]').first();
  await quantity.fill("1");
  const lot=page.locator('.guided-line-table input[aria-label^="Lot number for"]').first();
  await page.getByText("Lot and expiry (if shown on package)").first().click();
  await lot.fill("KEEP-MY-LOT");
  await page.getByRole("textbox",{name:"Delivery reference"}).fill("KEEP-MY-DR");
  await page.getByRole("button",{name:"Next receipts"}).click();
  await expect(quantity).toHaveValue("1");
  await expect(lot).toHaveValue("KEEP-MY-LOT");
  await expect(page.getByRole("textbox",{name:"Delivery reference"})).toHaveValue("KEEP-MY-DR");
  await page.getByRole("textbox",{name:"Find purchase orders"}).fill("NO_MATCH_PO");
  await page.getByRole("button",{name:"Find orders"}).click();
  await expect(quantity).toHaveValue("1");
  await expect(page.getByRole("textbox",{name:"Delivery reference"})).toHaveValue("KEEP-MY-DR");
});

test("items use server paging and search rather than silently truncating catalogue",async({page})=>{
  await signIn(page);
  await page.route("**/api/v1/items/catalogue-workspace?*",async route=>{
    const original=await route.fetch();
    if(!original.ok())return route.fulfill({response:original});
    const payload=await original.json();
    const url=new URL(route.request().url());
    const pageIndex=Number(url.searchParams.get("page")||1);
    payload.pagination={page:pageIndex,page_size:25,total:51,has_previous:pageIndex>1,has_next:pageIndex<3};
    payload.summary={...payload.summary,catalogue_items:51};
    await route.fulfill({response:original,contentType:"application/json",body:JSON.stringify(payload)});
  });
  await page.goto("/items");
  await expect(page.getByText(/Page 1 · 51 matching item/)).toBeVisible();
  await page.getByRole("button",{name:"Next items"}).click();
  await expect(page.getByText(/Page 2 · 51 matching item/)).toBeVisible();
  await page.getByRole("textbox",{name:"Search items by name or SKU"}).fill("COFFEE");
  await page.getByRole("button",{name:"Search",exact:true}).click();
  await expect(page.getByText(/Page 1 · 51 matching item/)).toBeVisible();
});
