import {expect,test,type Page} from "@playwright/test";

async function signIn(page:Page){
  await page.goto("/login");
  await page.getByLabel("Email address").fill(process.env.E2E_OWNER_EMAIL||"owner@example.com");
  await page.locator('input[name="password"]').fill(process.env.E2E_OWNER_PASSWORD||"password123");
  await page.getByRole("button",{name:"Sign in"}).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

async function itemSettings(page:Page){
  await signIn(page);
  const items=await(await page.request.get("/api/v1/items")).json();
  const units=await(await page.request.get("/api/v1/units")).json();
  const suppliers=await(await page.request.get("/api/v1/suppliers")).json();
  const locations=await(await page.request.get("/api/v1/locations")).json();
  expect(units.length).toBeGreaterThan(1);expect(suppliers.length).toBeGreaterThan(0);expect(locations.length).toBeGreaterThan(0);
  const item=items[0],from=units[0],to=units[1],supplier=suppliers[0],location=locations[0];
  const config={barcodes:[{id:"edit-barcode",barcode:"EDIT-OLD",barcode_type:"INTERNAL",is_primary:false}],
    conversions:[{id:"edit-conversion",from_unit_id:from.id,from_unit_code:from.code,to_unit_id:to.id,to_unit_code:to.code,multiplier:"2",is_active:true}],
    supplier_items:[{id:"edit-supplier",supplier_id:supplier.id,supplier_code:supplier.code,supplier_name:supplier.name,supplier_sku:"OLD",last_price:"12",lead_time_days:3,minimum_order_quantity:"2",is_preferred:false}],
    location_settings:[{id:"edit-policy",location_id:location.id,location_code:location.code,location_name:location.name,minimum_stock:"2",reorder_quantity:"4",maximum_stock:"12",preferred_supplier_id:null,preferred_supplier_name:null,cycle_count_days:30,is_active:true}]};
  await page.route(`**/api/v1/items/${item.id}/configuration`,route=>route.fulfill({json:config}));
  await page.goto(`/items/${item.id}`);
  await expect(page.getByRole("heading",{name:"Purchasing and stock configuration"})).toBeVisible();
  return {config,item,from,to,supplier,location};
}

test("an existing conversion is edited in place and rejects identical units",async({page})=>{
  const{config,item,from,to}=await itemSettings(page);let saves=0;
  await page.route(`**/api/v1/items/${item.id}/conversions/edit-conversion`,async route=>{
    expect(route.request().method()).toBe("PATCH");saves++;
    expect(route.request().postDataJSON()).toEqual({from_unit_id:from.id,to_unit_id:to.id,multiplier:3.5,is_active:false});
    Object.assign(config.conversions[0],{multiplier:"3.5",is_active:false});await route.fulfill({json:config.conversions[0]});
  });
  const trigger=page.getByRole("button",{name:`Edit conversion ${from.code} to ${to.code}`,exact:true});await trigger.click();
  const dialog=page.getByRole("alertdialog",{name:"Edit unit conversion",exact:true});
  await dialog.getByRole("combobox",{name:"To unit",exact:true}).selectOption(from.id);
  await dialog.getByRole("button",{name:"Save changes",exact:true}).click();
  await expect(dialog.getByRole("alert")).toContainText("Choose different");expect(saves).toBe(0);
  await dialog.getByRole("combobox",{name:"To unit",exact:true}).selectOption(to.id);await dialog.getByLabel("Multiplier",{exact:true}).fill("3.5");
  await dialog.getByLabel("Available for new entries").uncheck();await dialog.getByRole("button",{name:"Save changes",exact:true}).click();
  await expect(dialog).toHaveCount(0);expect(saves).toBe(1);
  await trigger.click();await expect(dialog.getByLabel("Multiplier",{exact:true})).toHaveValue("3.5");
  await expect(dialog.getByLabel("Available for new entries")).not.toBeChecked();
});

test("policy edits preserve entered values after a failed save and keep a blank maximum",async({page})=>{
  const{config,location}=await itemSettings(page);let attempts=0;
  await page.route("**/api/v1/item-location-settings/edit-policy",async route=>{
    expect(route.request().method()).toBe("PATCH");attempts++;
    expect(route.request().postDataJSON()).toEqual({minimum_stock:5,reorder_quantity:9,maximum_stock:null,preferred_supplier_id:null,cycle_count_days:14,is_active:true});
    if(attempts===1)return route.fulfill({status:409,json:{detail:"Save was interrupted. Try again."}});
    Object.assign(config.location_settings[0],{minimum_stock:"5",reorder_quantity:"9",maximum_stock:null,cycle_count_days:14});
    await route.fulfill({json:config.location_settings[0]});
  });
  await page.getByRole("button",{name:`Edit policy ${location.name}`,exact:true}).click();
  const dialog=page.getByRole("alertdialog",{name:"Edit location policy",exact:true});
  await dialog.getByLabel("Minimum stock",{exact:true}).fill("5");await dialog.getByLabel("Reorder quantity",{exact:true}).fill("9");
  await dialog.getByLabel("Maximum stock (optional)",{exact:true}).fill("");await dialog.getByLabel("Count every (days)",{exact:true}).fill("14");
  await dialog.getByRole("button",{name:"Save changes",exact:true}).click();
  await expect(dialog.getByRole("alert")).toContainText("interrupted");await expect(dialog.getByLabel("Minimum stock",{exact:true})).toHaveValue("5");
  await expect(dialog.getByLabel("Maximum stock (optional)",{exact:true})).toHaveValue("");
  await dialog.getByRole("button",{name:"Save changes",exact:true}).click();await expect(dialog).toHaveCount(0);expect(attempts).toBe(2);
});

test("barcode and supplier edits retain the original record identities",async({page})=>{
  const{config,item,supplier}=await itemSettings(page);let barcodeSaved=false,supplierSaved=false;
  await page.route(`**/api/v1/items/${item.id}/barcodes/edit-barcode`,async route=>{
    expect(route.request().method()).toBe("PATCH");expect(route.request().postDataJSON()).toEqual({barcode:"EDIT-NEW",barcode_type:"INTERNAL",is_primary:true});
    Object.assign(config.barcodes[0],{barcode:"EDIT-NEW",is_primary:true});barcodeSaved=true;await route.fulfill({json:config.barcodes[0]});
  });
  await page.getByRole("button",{name:"Edit barcode EDIT-OLD",exact:true}).click();
  const barcode=page.getByRole("alertdialog",{name:"Edit barcode",exact:true});await barcode.getByLabel("Barcode",{exact:true}).fill("EDIT-NEW");
  await barcode.getByLabel("Primary barcode").check();await barcode.getByRole("button",{name:"Save changes",exact:true}).click();await expect(barcode).toHaveCount(0);expect(barcodeSaved).toBe(true);
  await page.route("**/api/v1/supplier-items/edit-supplier",async route=>{
    expect(route.request().method()).toBe("PATCH");expect(route.request().postDataJSON()).toEqual({supplier_sku:"UPDATED",last_price:22.5,lead_time_days:5,minimum_order_quantity:3,is_preferred:true});
    Object.assign(config.supplier_items[0],{supplier_sku:"UPDATED",last_price:"22.5",lead_time_days:5,minimum_order_quantity:"3",is_preferred:true});supplierSaved=true;await route.fulfill({json:config.supplier_items[0]});
  });
  await page.getByRole("button",{name:`Edit supplier terms ${supplier.name}`,exact:true}).click();
  const terms=page.getByRole("alertdialog",{name:"Edit supplier terms",exact:true});
  await terms.getByLabel("Supplier item code",{exact:true}).fill("UPDATED");await terms.getByLabel("Last price (PHP)",{exact:true}).fill("22.5");
  await terms.getByLabel("Delivery lead time (days)",{exact:true}).fill("5");await terms.getByLabel("Minimum order quantity",{exact:true}).fill("3");
  await terms.getByLabel("Preferred supplier",{exact:true}).check();await terms.getByRole("button",{name:"Save changes",exact:true}).click();await expect(terms).toHaveCount(0);expect(supplierSaved).toBe(true);
});

test("maintenance completion requires explicit costs and retains them after a failed save",async({page})=>{
  await signIn(page);let saves=0;
  const row={id:"costed-work",work_order_number:"MWO-COST",asset_id:"asset",title:"Repair ventilation fan",priority:"normal",status:"in_progress",scheduled_date:null,labor_cost:"0",external_cost:"0",downtime_hours:"0"};
  await page.route("**/api/v1/maintenance/work-orders",route=>route.fulfill({json:[row]}));
  await page.route("**/api/v1/assets",route=>route.fulfill({json:[{id:"asset",asset_tag:"FAN",status:"active"}]}));
  await page.route("**/api/v1/maintenance/plans",route=>route.fulfill({json:[]}));
  await page.route("**/api/v1/accounting-mappings",route=>route.fulfill({json:[]}));
  await page.route("**/api/v1/maintenance/work-orders/costed-work/complete",async route=>{
    saves++;expect(route.request().postDataJSON()).toEqual({labor_cost:450.5,external_cost:125,downtime_hours:1.25,completion_notes:"Fan guard checked"});
    if(saves===1)return route.fulfill({status:409,json:{detail:"Save was interrupted. Try again."}});
    Object.assign(row,{status:"completed",labor_cost:"450.5",external_cost:"125",downtime_hours:"1.25"});await route.fulfill({json:row});
  });
  await page.goto("/assets/maintenance");await page.getByRole("button",{name:"Complete",exact:true}).click();
  const dialog=page.getByRole("alertdialog",{name:"Complete work order",exact:true});
  await dialog.getByRole("button",{name:"Complete work order",exact:true}).click();expect(saves).toBe(0);
  await dialog.getByLabel("Labor cost (PHP)",{exact:true}).fill("450.50");await dialog.getByLabel("Other costs (PHP)",{exact:true}).fill("125");
  await dialog.getByLabel("Downtime (hours)",{exact:true}).fill("1.25");await dialog.getByLabel("Completion notes",{exact:true}).fill("Fan guard checked");
  await dialog.getByRole("button",{name:"Complete work order",exact:true}).click();await expect(dialog.getByRole("alert")).toContainText("interrupted");
  await expect(dialog.getByLabel("Labor cost (PHP)",{exact:true})).toHaveValue("450.50");
  await dialog.getByRole("button",{name:"Complete work order",exact:true}).click();await expect(dialog).toHaveCount(0);expect(saves).toBe(2);
  await expect(page.getByRole("cell",{name:/Labor.*450\.50/})).toBeVisible();await expect(page.getByRole("cell",{name:/^(?:Downtime \(h\)\s*)?1\.25$/})).toBeVisible();
});
