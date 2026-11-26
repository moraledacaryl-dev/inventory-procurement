import {expect,test} from "@playwright/test";

test("rejected delivery stays selectable and explains replacement follow-up",async({page})=>{
  await page.goto("/login");
  await page.getByLabel("Email address").fill(process.env.E2E_OWNER_EMAIL||"owner@example.com");
  await page.locator('input[name="password"]').fill(process.env.E2E_OWNER_PASSWORD||"password123");
  await page.getByRole("button",{name:"Sign in"}).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.route("**/api/v1/receiving/workspace?*",async route=>{
    const response=await route.fetch();
    expect(response.ok()).toBeTruthy();
    const body=await response.json();
    body.purchase_orders=[{
      id:"replacement-po",purchase_order_number:"PO-REPLACEMENT",supplier_id:"supplier",
      supplier_code:"SUP",supplier_name:"Replacement supplier",delivery_location_id:"location",
      delivery_location_code:"STORE",delivery_location_name:"Storeroom",expected_delivery_date:null,
      status:"partially_received",ordered_quantity:"5",received_quantity:"5",outstanding_quantity:"1",
      replacement_required:true,lines:[{
        id:"replacement-line",item_id:"item",sku:"REPLACE",item_name:"Replacement ingredient",
        ordered_quantity:"5",received_quantity:"5",accepted_quantity:"4",rejected_quantity:"1",
        outstanding_quantity:"1",returned_quantity:"0",returnable_quantity:"4",unit_price:"20",
      }],
    }];
    await route.fulfill({response,contentType:"application/json",body:JSON.stringify(body)});
  });
  await page.goto("/receiving");
  await page.getByRole("combobox",{name:"Purchase order"}).selectOption("replacement-po");
  await expect(page.getByText("Rejected deliveries still need acceptable replacements.",{exact:false})).toBeVisible();
  await page.getByRole("button",{name:"Next: count the delivery"}).click();
  await expect(page.getByText("Rejected quantities remain outstanding",{exact:false})).toBeVisible();
  const arrived=page.getByRole("spinbutton",{name:"Arrived today for Replacement ingredient",exact:true});
  await expect(arrived).toHaveAttribute("max","1");
  await arrived.fill("2");
  await expect(page.getByText("More than the remaining order")).toBeVisible();
  await expect(page.getByRole("button",{name:"Next: check details"})).toBeDisabled();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(2);
});
