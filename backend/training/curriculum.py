"""Versioned lesson content and typed outcome contracts, separate from execution.

Every task uses an existing Inventory route. Knowledge checks alone never certify
a transaction lesson. Independent attempts start from a fresh, different fixture.
"""
from dataclasses import replace
from typing import Literal
from training.lesson_types import Lesson, Step

VERSION = "2026.11.26.11"
Role = Literal["owner", "inventory_manager", "procurement_officer", "receiver", "counter", "viewer"]
Mode = Literal["guided", "assisted", "independent"]
ROLES = ["inventory_manager", "procurement_officer", "receiver", "counter", "viewer", "owner"]
ROLE_NAMES = {"inventory_manager": "Stock and department supplies", "procurement_officer": "Purchasing",
    "receiver": "Receiving deliveries", "counter": "Physical stock counts", "viewer": "Reports and review", "owner": "Owner and administration"}


STOCK = ("inventory_manager", "owner")
BUY = ("procurement_officer", "owner")
RECEIVE = ("receiver", "owner")
COUNT = ("counter", "inventory_manager", "owner")
READ = ("inventory_manager", "procurement_officer", "receiver", "viewer", "owner")
REPORT = ("inventory_manager", "procurement_officer", "viewer", "owner")


def s(target, instruction, value=None, event="click"):
    return Step(target, instruction, value, event)


def stock_steps(action="issue"):
    steps = [
        s('[data-training="stock-open"]', "Open Record a stock movement."),
        s('#stock-kind', "Choose {action_label}.", action, "change"),
        s('[name="location"]', "Choose TRAIN-STORE — Training stockroom.", '{store}', "change"),
        s('[name="item"]', "Choose {practice_name}.", '{practice_item}', "change"),
        s('[name="quantity"]', "Enter {quantity} kg. Use the amount in the situation.", "{quantity}", "input"),
        s('[name="reason"]', "Enter {movement_reason} as the reason.", "{movement_reason}", "input"),
        s('[data-training="stock-review"]', "Check the item, location and quantity before posting."),
        s('[data-training="confirm"]', "Post the transaction only after checking the summary."),
    ]
    if action == "receipt":
        steps.insert(5,s('[name="cost"]', "Enter PHP 200 per kg as the unit cost. Do not enter the total value.", "200", "input"))
    return tuple(steps)


RECEIPT_STEPS = (
    s('[aria-label="Purchase order"]', "Choose TRAIN-PO — the order from Training Valley Foods.", '{po}', "change"),
    s('[data-training="receive-next"]', "Continue to count the delivery."),
    s('[aria-label="Arrived today for Chicken (kg)"]', "Enter {quantity} for the chicken that arrived today.", "{quantity}", "input"),
    s('[aria-label="Rejected quantity for Chicken (kg)"]', "Enter {rejected} rejected. Accepted is arrived minus rejected.", "{rejected}", "input"),
    s('[aria-label="Delivery reference"]', "Enter the delivery receipt number {reference}.", "{reference}", "input"),
    s('[data-training="receive-review"]', "Check your details. Explain any rejected quantity before continuing."),
    s('[data-training="receive-confirm"]', "Review the accepted and rejected amounts, then confirm this delivery."),
    s('[data-training="confirm"]', "Post this receipt. Only accepted goods enter stock."),
)

COUNT_STEPS = (
    s('[aria-label="Counted quantity for Chicken (kg)"]', "You physically counted {quantity} kg. Enter {quantity}, even though recorded stock is hidden.", "{quantity}", "input"),
    s('[data-training="count-save"]', "Save your counts. Saved entries survive leaving this page."),
    s('[data-training="count-submit"]', "Submit the saved count for evaluation."),
    s('[data-training="confirm"]', "Confirm submission. A counter cannot approve their own difference."),
)

LESSONS = [
    Lesson("available-stock", "A", "How much stock can we use?", READ, "/stock", "read_stock",
        "The kitchen needs chicken for service. Some chicken is already set aside for another job.",
        "Physical stock is what the system records on hand. Reserved stock is set aside. Available stock is physical minus reserved. Consumed stock has already left inventory.",
        "There are 24 kg on hand and 4 kg reserved. You can use 20 kg without taking another job's supplies.",
        "Check available stock, the item unit and the storage location before requesting or issuing supplies.",
        "Which stock amount should you check before issuing supplies?", "available",
        "Use available stock: physical stock minus stock already reserved.", ("inventory_operations.py", "inventory.py")),
    Lesson("find-your-work", "B", "Find a record and check your role", READ, "/dashboard", "read_stock",
        "You are starting your shift and need to find the stockroom's chicken record.",
        "Use the navigation to open Stock. A filter narrows the list; it does not move stock. Search and location choices can hide records outside the selected view.",
        "Choose the training stockroom, then the chicken item. Read the amount and its unit before deciding what to do.",
        "If a button is restricted, ask an authorized colleague. A training pass does not change your production permissions.",
        "Does filtering a list change stock? Answer yes or no.", "no", "Filters only change what you see.", ("dashboard.py", "modules.py")),
    Lesson("catalogue-units", "C", "Read item units and conversions", READ, "/items/{chicken}", "read_stock",
        "Chicken is bought by kilogram. A recipe may be written in grams.",
        "A base unit is the unit used for stock. A conversion tells the system how two units relate. Purchase quantities and recipe quantities must use the correct units.",
        "1 kilogram equals 1,000 grams. A recipe using 250 g uses 0.25 kg, not 250 kg.",
        "Check the base unit, conversion direction and multiplier. Ask the catalogue owner to correct errors before posting stock.",
        "How many grams are in 1 kg?", "1000", "1 kg = 1,000 g. A factor of 1,000 in the wrong direction creates a major stock error.", ("catalogue_configuration.py", "inventory_operations.py")),
    Lesson("opening-stock", "D", "Record an opening balance", STOCK, "/stock", "receipt",
        "A new training storeroom has {quantity} kg of chicken at PHP 200 per kg that has not been recorded. This is opening stock, not a supplier delivery against a PO.",
        "Opening stock establishes a starting record. Receiving against a purchase order belongs in Receiving. Quantity is the amount; unit cost is the cost of one base unit.",
        "A starting balance of 5 kg at PHP 200 per kg is PHP 1,000 of inventory. Never enter the total value as the quantity.",
        "Record the correct location, base-unit quantity and evidence. Investigate errors through the authorized correction workflow.",
        "Does a purchase order alone add physical stock? yes or no", "no", "Stock increases only when an appropriate stock receipt is posted.", ("inventory.py",), stock_steps("receipt"), 5),
    Lesson("issue-kitchen", "E", "Issue chicken to the kitchen", STOCK, "/stock", "issue",
        "The kitchen takes {quantity} kg of chicken from the training stockroom for today's cooking.",
        "An issue records supplies taken for use. It reduces stock. A transfer moves stock between tracked locations without consuming it.",
        "If 24 kg is recorded and 5 kg is issued, recorded stock becomes 19 kg. Check reservations before issuing.",
        "Record what was actually issued. A shortage is a reason to investigate or request supplies, not to invent a receipt.",
        "Which action records supplies taken for use?", "issue", "Use an issue when supplies leave stock for use.", ("inventory.py",), stock_steps(), 5),
    Lesson("transfer-stock", "F", "Move stock to another location", STOCK, "/stock", "transfer",
        "Move {quantity} kg of chicken from the stockroom to the kitchen's tracked storage.",
        "A direct transfer decreases the source and increases the destination. A controlled transfer has dispatch and receipt stages and can record differences.",
        "Moving 5 kg leaves 19 kg at the source and adds 5 kg at the destination. The resort still owns the same total quantity.",
        "Check both locations. Use controlled transfer orders when dispatch and receiving acknowledgement are required.",
        "Does an internal transfer create additional total stock? yes or no", "no", "A transfer moves existing stock between locations.", ("inventory.py", "controlled_inventory.py"), stock_steps("transfer"), 5),
    Lesson("blind-count", "G", "Count what is physically there", COUNT, "/counts/{count}", "count",
        "Count the chicken in the training stockroom. Your physical count is {quantity} kg. Do not guess the system's hidden amount.",
        "A blind count hides recorded stock so you count independently. A variance means your count differs from the record. Save progress before leaving.",
        "If you physically count 21, enter 21. Enter 0 when none is there. A blank entry means not counted, not zero.",
        "Enter physical quantities in the correct unit. Submit only when every line is counted. An authorized independent person reviews differences.",
        "What number must you enter when none is physically there?", "0", "Enter 0. Leaving a line blank means the item has not been counted.", ("guided_counts.py", "inventory.py"), COUNT_STEPS, 21),
    Lesson("count-zero", "G", "Record zero stock and save your work", COUNT, "/counts/{count}", "count",
        "There is no chicken in this training shelf. Enter zero and submit the count.",
        "Zero is a completed physical count. It may reveal a significant difference, which must be reviewed. Changing the number to match the system hides the problem.",
        "Save a zero count, leave the page and return. The saved zero remains; unsaved text may not.",
        "Save often and report interruptions or stock movement during a count.",
        "Is an empty field the same as a saved zero? yes or no", "no", "An empty field means uncounted; enter and save 0.", ("guided_counts.py",), COUNT_STEPS, 0),
    Lesson("approve-count", "G", "Review a colleague's count variance", STOCK, "/counts/{count}", "approve_count",
        "A different training counter submitted {quantity} kg. Review the difference and approve only after checking the evidence.",
        "Independent approval separates entering a count from accepting a stock adjustment. Recount questionable lines. Stock movement after the snapshot requires a fresh count.",
        "A counter's 21 kg against a recorded 24 kg is a difference of -3 kg. Posting an approved adjustment changes stock to 21 kg.",
        "Never approve your own variance. Do not use adjustments to bypass counting controls.",
        "Can the count creator approve their own variance? yes or no", "no", "The source blocks self-approval. A different authorized reviewer must decide.", ("guided_counts.py",), (s('[data-training="count-approve"]', "Check the submitted quantities, then approve and post."), s('[data-training="confirm"]', "Confirm after verifying the difference.")), 21),
    Lesson("record-waste", "H", "Record spoiled supplies", STOCK, "/inventory-operations", "waste",
        "{quantity} kg of chicken spoiled. Keep it out of food preparation and record spoilage through the waste workflow.",
        "Waste records stock that can no longer be used. It removes quantity and records its value. It is different from returning accepted goods to a supplier.",
        "If 2 kg spoils, record 2 kg with spoilage as the cause. Do not use a supplier receipt or invent a count to conceal it.",
        "Use the real cause, correct location and supporting reference. Follow resort food-safety instructions for physical disposal.",
        "Should spoiled food be recorded as a new receipt? yes or no", "no", "Use the appropriate waste reason; a receipt would increase stock.", ("controlled_inventory.py",), (), 2),
    Lesson("supplier-profile", "I", "Find a supplier and check its history", ("procurement_officer", "receiver", "viewer", "owner", "inventory_manager"), "/suppliers/{supplier}", "read_supplier",
        "A delivery comes from Training Valley Foods. Confirm its identity and history before choosing a supplier.",
        "A supplier profile connects contact details, item links, prices and purchase history. Preferred supplier does not mean every offer is automatically suitable.",
        "Compare price, lead time, acceptance history and payment terms. A cheap offer arriving after the weekend may not meet the need.",
        "Keep supplier details accurate and do not deactivate a supplier to hide outstanding orders.",
        "Is the lowest price always the best choice? yes or no", "no", "Also check availability, quality, delivery time and terms.", ("supplier_360.py", "procurement.py")),
    Lesson("request-purchase", "J", "Check stock before requesting a purchase", BUY, "/purchasing", "requisition",
        "Kitchen needs {quantity} kg of additional chicken for a busy weekend. Check available stock, reserved stock and outstanding orders first.",
        "A requisition is a request to buy supplies. It needs a department, location, quantity and clear reason. Submitting is not approval or receipt.",
        "If enough stock and a confirmed delivery already cover the need, investigate before making a duplicate request.",
        "Explain the need and required date. Follow the submitted request through review; do not create duplicate requests while waiting.",
        "Does submitting a purchase request add stock? yes or no", "no", "A request asks for permission to buy; it does not receive supplies.", ("procurement_planning.py", "procurement.py"), (), 8),
    Lesson("purchase-approval", "K", "Review purchasing authority and quotations", BUY, "/purchasing", "approve_po",
        "A colleague prepared an order for {quantity} kg. Check supplier, costs, delivery location and your approval limit.",
        "Purchase approval requires the route permission, a matching operational scope and enough monetary authority for non-owners. The creator cannot approve their own purchase.",
        "An order of 10 kg at PHP 200 costs PHP 2,000. An approver with a PHP 1,000 limit cannot approve it.",
        "Reject incomplete requests or ask for correction. Compare offers before awarding, and avoid duplicate purchases.",
        "Can a PHP 1,000 approval limit cover a PHP 2,000 order? yes or no", "no", "The approval limit must cover the entire order, within its location scope.", ("quotation_po_workspace.py", "procurement.py"), (), 10),
    Lesson("order-supplies", "L", "Create an order without receiving stock", BUY, "/purchasing", "purchase_order",
        "Prepare a draft order for {quantity} kg of chicken from Training Valley Foods to the training stockroom at PHP 200 per kg.",
        "A purchase order tells the supplier what the resort intends to buy. Draft, approval, physical receipt and payment are different events.",
        "Approving 10 kg creates a purchasing commitment. Stock remains unchanged until accepted goods are received.",
        "Check item, purchase unit, price, supplier and destination. Review amendment and cancellation restrictions before changing an existing order.",
        "Does an approved PO mean the supplies are physically available? yes or no", "no", "An approved order is a commitment; receipt records what arrives.", ("procurement.py", "quotation_po_workspace.py"), (), 10),
    Lesson("supplier-return", "N", "Return previously accepted goods", RECEIVE, "/receiving", "return",
        "The resort previously accepted 10 kg of chicken. A later quality check finds {quantity} kg must be returned to Training Valley Foods.",
        "A purchase return removes previously accepted stock and records a supplier-related handoff. Rejected goods that never entered stock cannot be returned again.",
        "If 10 kg was accepted and 2 kg already returned, at most 8 kg remains returnable, also subject to stock on hand.",
        "Use the original PO, a clear reason and supplier reference. A return does not prove that Accounting posted a credit or payment.",
        "Can you return stock that was already rejected at delivery? yes or no", "no", "Only previously accepted, not-yet-returned quantities are returnable.", ("receiving_workspace.py",), (), 2),
    Lesson("expiry-rotation", "O", "Check lots and expiry before use", REPORT, "/reports", "read_stock",
        "You are choosing chicken for service. Check its expiry information and physical condition before use.",
        "A lot identifies a batch. FIFO means use older receipts first. FEFO means use the batch expiring first. A report does not physically rotate goods for you.",
        "Milk expiring tomorrow should be considered before milk expiring next week, subject to food-safety and condition checks.",
        "Inspect, separate unsafe supplies and record appropriate waste or rejection. Do not assume automatic FEFO enforcement.",
        "Does a software expiry report physically move goods on a shelf? yes or no", "no", "Employees must inspect and rotate goods physically.", ("inventory_operations.py",)),
    Lesson("recipe-cost", "P", "Check a recipe's ingredients and yield", STOCK, "/production/recipes/{recipe}", "read_recipe",
        "Training Chicken Alfredo uses 0.25 kg of chicken for one serving. Check recipe quantity, unit and yield.",
        "A recipe describes ingredients needed for an output. Yield is how much usable output the recipe produces. Waste factors and ingredient prices affect cost.",
        "At PHP 200 per kg, 0.25 kg of chicken costs PHP 50. Four servings require 1 kg before any applicable waste factor.",
        "Check ingredient units and output yield before approving or revising recipes. Training menu names are fictional fixtures.",
        "How many kg are needed for four portions at 0.25 kg each?", "1", "4 × 0.25 kg = 1 kg.", ("production.py", "recipe_costing.py")),
    Lesson("batch-production", "Q", "Record actual batch yield", STOCK, "/production/batches/{batch}", "production",
        "A planned batch of 12 portions produced only {quantity} usable portions. Record actual ingredient use and actual yield.",
        "Batch production consumes raw ingredients and creates finished stock. Planned output and actual output can differ; the actual result affects cost per portion.",
        "If the same ingredients make 10 usable portions instead of 12, cost per usable portion rises. Do not record 12 just to match the plan.",
        "Review actual materials, shortages and yield before executing. An unsuccessful batch requires the supported cancellation/waste procedure, not invented output.",
        "Should you record the planned yield when actual output is lower? yes or no", "no", "Record the actual usable output and actual ingredients.", ("production_execution.py",), (), 10),
    Lesson("menu-mapping", "R", "Understand menu and POS product links", STOCK, "/fnb/menu", "read_recipe",
        "Check the training Chicken Alfredo menu item and its recipe link before making it available for sale.",
        "Menu products, variants, SKU, recipes and reusable modifier templates must refer to the intended records. Pricing rules are different from ingredient consumption.",
        "Extra cheese and extra pepperoni are examples of add-ons. Check allowed selections, prices and mappings in their actual configuration.",
        "Keep the authoritative catalogue consistent. A product being visible in POS does not prove that ingredient mapping is correct.",
        "Does a visible POS product guarantee a correct ingredient recipe? yes or no", "no", "Check the product-to-recipe mapping and integration status.", ("menu.py", "pos_rules.py", "pos_sync.py")),
    Lesson("sale-consumption", "S", "Review a sale without restoring eaten food", ("owner",), "/integrations/pos", "read_recipe",
        "A guest receives a refund after eating Chicken Alfredo. Review the sale and its inventory disposition.",
        "A finalized sale can consume mapped ingredients. A financial refund and physical stock restoration are different. Duplicate event protection prevents the same sale being consumed twice.",
        "Spaghetti, chicken and cream that were cooked and eaten do not physically return when a refund is issued.",
        "Review source sale, mapping errors and the authorized reversal disposition. Escalate failed events; do not add ingredients back casually.",
        "Should a refund for eaten food automatically restore its ingredients? yes or no", "no", "A financial refund does not make eaten ingredients usable stock.", ("production.py", "pos_sync.py")),
    Lesson("staff-meal", "T", "Record supplies used for staff meals", STOCK, "/fnb/staff-meals", "staff_meal",
        "Use {quantity} kg of chicken for a staff lunch. Record the actual ingredients in the training stockroom.",
        "A staff meal records stock consumed and its meal cost. Preview available quantity and total cost before posting. Reversal is a controlled correction, not a normal refund.",
        "2 kg at PHP 200 costs PHP 400 in chicken. Divide total meal cost by actual servings when reviewing cost per serving.",
        "Record the meal once, use accurate quantities and review shortages. Do not post a duplicate if the first request is still processing.",
        "Does posting a staff meal reduce ingredient stock? yes or no", "yes", "The posted meal deducts its actual ingredient quantities.", ("staff_meals.py",), (), 2),
    Lesson("housekeeping-supplies", "U", "Prepare guest rooms with the right supplies", STOCK, "/stock", "issue",
        "Housekeeping needs {quantity} guest amenity kits to prepare Solace, Café Suite and Perch 1. Issue the kits from the training stockroom.",
        "A room par is the target amount needed. Reusable linen moves between locations and conditions; consumable amenities are issued for use. These are different workflows.",
        "Three rooms needing four amenity kits each require 12 kits. Check available stock before issuing them.",
        "Use the correct item and base unit. Do not record towels as consumed when they are merely sent to laundry.",
        "How many kits are needed for three rooms using four kits each?", "12", "3 × 4 = 12 kits. Check actual room requirements before issuing.", ("property_operations.py", "inventory.py"), stock_steps(), 12),
    Lesson("asset-maintenance", "V", "Distinguish assets from consumable supplies", STOCK, "/assets", "read_stock",
        "A refrigerator needs repair. Review its asset and maintenance information before choosing a purchasing or maintenance workflow.",
        "An asset is equipment used over time. Light bulbs and cleaning supplies are consumables. Capital versus expense and depreciation decisions belong to authorized financial reviewers.",
        "Repairing a refrigerator does not mean the refrigerator was consumed. Parts, labor and equipment lifecycle changes need their own records.",
        "Use the registered asset, correct location and maintenance record. Ask the authorized reviewer about accounting treatment.",
        "Is a refrigerator normally consumed each time it is used? yes or no", "no", "Equipment remains an asset; consumable supplies are used up.", ("assets.py", "pass5_operations.py")),
    Lesson("accounting-proof", "W", "Read Accounting delivery and journal evidence", ("owner",), "/integrations/accounting", "read_stock",
        "A receipt event shows delivered. Determine whether it was accepted and whether source-linked journal proof exists.",
        "Sent, received, awaiting review, accepted, journal posted and financially reconciled are distinct states. An outbox success confirms delivery to intake only.",
        "An accepted intake without a verified linked journal is not proof that the general ledger was posted. A journal is not proof of payment.",
        "Review errors and the source event before retrying. Keep all training delivery disabled; no real Accounting endpoint is involved.",
        "Does delivered prove that a journal was posted? yes or no", "no", "Delivery is only an intake step. Look for verified source-linked journal evidence.", ("accounting_integration.py", "operations.py")),
    Lesson("connected-work", "X", "Know where connected work belongs", ("owner",), "/integrations/operations", "read_stock",
        "Operations sends a department purchasing need. Inventory must review it and follow its authorized purchasing workflow.",
        "Operations tracks follow-up work; Inventory tracks supplies and purchasing; POS records sales; Staff owns shared employee identities; Accounting reviews financial handoffs.",
        "A low-stock alert is a prompt to investigate, not an automatically approved purchase or a new stock receipt.",
        "Check the source and status in the appropriate application. A notification does not replace the required stock or approval transaction.",
        "Does a low-stock notification itself receive supplies? yes or no", "no", "A notification asks for attention. Receiving is a separate workflow.", ("operational_integrations.py", "shared_master_data.py")),
    Lesson("management-review", "Y", "Investigate stock and purchasing reports", REPORT, "/reports", "read_stock",
        "Kitchen consumption increased this week. Review stock movements and relevant activity before drawing conclusions.",
        "A report is evidence to investigate. More sales, a recipe change, staff meals, waste, transfers or entry errors can all change consumption. Quantity and value answer different questions.",
        "A higher ingredient price can increase valuation without increasing quantity. Increased sales can increase consumption without proving waste.",
        "Compare like dates, locations and units. Follow unusual figures to their source documents and ask the responsible person.",
        "Does increased consumption alone prove theft? yes or no", "no", "Review sales, recipes, transfers, waste, meals and source transactions first.", ("final_assurance.py", "inventory_operations.py")),
    Lesson("admin-controls", "Z", "Check access and recover safely", ("owner",), "/settings/access-scopes", "read_stock",
        "A receiver cannot see an order in another storage location. Review the role and authorized location scope.",
        "Role permission and location access both apply. Inactive scopes deny access; they do not become unrestricted. Recovery and migration actions must stay in an isolated environment.",
        "A receiving role does not grant purchasing approval. A purchase approval also needs a matching scope and sufficient monetary limit for non-owners.",
        "Grant only approved access. Preserve audit evidence and backups; never practise destructive recovery on production.",
        "Does a training certificate automatically grant production permissions? yes or no", "no", "Production access is a separate authorized administrative decision.", ("pass6_controls.py", "readiness.py", "stabilization.py")),
]

_deliveries = [
    ("full-delivery", "Receive a complete delivery", 10, 0, "All 10 kg arrived in good condition."),
    ("partial-delivery", "Receive only what arrived", 8, 0, "Only 8 of the ordered 10 kg arrived. Two kg are still outstanding."),
    ("damaged-delivery", "Reject damaged goods at the door", 10, 2, "10 kg arrived, but 2 kg has damaged packaging and must be rejected."),
    ("expired-delivery", "Reject expired goods", 10, 3, "10 kg arrived; 3 kg has unacceptable expiry and must be rejected. Write the reason."),
    ("fully-rejected", "Record a fully rejected delivery", 10, 10, "All 10 kg arrived but is unusable. Reject all of it. Do not add stock."),
    ("quantity-discrepancy", "Record a delivery quantity difference", 6, 1, "6 kg arrived; 1 kg is damaged. Record 6 arrived and 1 rejected, accepting 5."),
    ("wrong-item", "Handle an incorrect item", 10, 10, "The delivery is the wrong item for this line. Record rejection with a clear wrong-item reason; do not add the ordered item to stock."),
    ("later-delivery", "Receive the remaining order later", 2, 0, "8 kg arrived on an earlier delivery. The remaining 2 kg arrives today. Use a new delivery reference."),
    ("check-order", "Check the order before posting", 8, 0, "Two orders look similar. Use TRAIN-PO from Training Valley Foods, not the decoy order."),
    ("resume-delivery", "Continue an interrupted receipt", 8, 0, "Only 8 kg arrived. Save the delivery draft by entering details, leave the page, then return and finish the receipt."),
]
for ident, title, qty, rejected, situation in _deliveries:
    steps = list(RECEIPT_STEPS)
    if rejected:
        steps.insert(4, s('[aria-label="Reason for rejecting Chicken (kg)"]', "Write the actual reason: {reject_reason}.", "{reject_reason}", "input"))
    LESSONS.append(Lesson(ident, "M", title, RECEIVE, "/receiving", "receiving", situation,
        "Arrived is what the supplier delivered. Rejected is what you refused. Accepted is arrived minus rejected. Only accepted stock is added; all arrived quantity counts toward PO fulfillment.",
        "10 kg arrived and 2 kg was rejected: stock rises by 8 kg. The order may be received in full even though usable stock is short. Arrange follow-up through purchasing.",
        "Check item, condition, expiry, lot, location, quantity and delivery reference. Never record supplies that did not arrive. Rejection does not automatically leave the PO outstanding.",
        "Does rejected quantity increase usable stock? yes or no", "no", "Rejected goods never enter usable stock. Accepted = arrived minus rejected.", ("receiving_workspace.py",), tuple(steps), qty, rejected))

EXTRA_STEPS = {
    "waste": (s('[data-training="waste-open"]', "Open Waste and spoilage."),
        s('#waste-item', "Choose the chicken item.", '{chicken}', "change"),
        s('#waste-location', "Choose Training stockroom.", '{store}', "change"),
        s('#waste-reason', "Choose Spoilage as the cause.", "spoilage", "change"),
        s('#waste-quantity', "Enter the {quantity} kg that spoiled.", "{quantity}", "input"),
        s('[data-training="waste-post"]', "Check the cause and quantity, then record the write-off.")),
    "purchase_order": (s('#purchase-tab-manual', "For this exercise, your manager authorized a manual order. Open Manual order."),
        s('[aria-label="Supplier"]', "Choose Training Valley Foods.", '{supplier}', "change"),
        s('[aria-label="Delivery location"]', "Choose Training stockroom.", '{store}', "change"),
        s('[aria-label="Purchase order line 1 item"]', "Choose Chicken (kg).", '{chicken}', "change"),
        s('[aria-label="Purchase order line 1 quantity"]', "Order {quantity} kg.", "{quantity}", "input"),
        s('[aria-label="Purchase order line 1 unit price"]', "Enter PHP 200 per kg.", "200", "input"),
        s('[data-training="po-save"]', "Review the order and save the draft. This does not add stock.")),
    "return": (s('[data-training="return-open"]', "Open Return accepted stock to supplier."),
        s('[data-training="return-po"]', "Choose TRAIN-PO, the original order.", '{po}', "change"),
        s('[data-training="return-reason"]', "Explain the later quality failure.", "quality failure", "input"),
        s('[aria-label="Quantity to return for Chicken (kg)"]', "Return {quantity} kg of previously accepted stock.", "{quantity}", "input"),
        s('[data-training="return-review"]', "Review the quantity, source order and reason."),
        s('[data-training="confirm"]', "Post the supplier return after checking it.")),
    "production": (s('[data-training="production-start"]', "Start the planned batch."),
        s('[aria-label="Actual quantity for training-chicken"]', "The batch used 3 kg of chicken. Enter 3.", "3", "input"),
        s('[aria-label="Actual total output"]', "The usable output is {quantity} portions with no output rejects. Enter {quantity}.", "{quantity}", "input"),
        s('[data-training="production-post"]', "Check actual ingredients and output, then complete and post.")),
    "staff_meal": (s('[data-training="meal-name"]', "Name this meal Training staff lunch.", "Training staff lunch", "input"),
        s('[data-training="meal-location"]', "Choose Training stockroom.", '{store}', "change"),
        s('#ingredient-0', "Choose Chicken (kg).", '{chicken}', "change"),
        s('#quantity-0', "Enter the {quantity} kg actually used.", "{quantity}", "input"),
        s('[data-training="meal-preview"]', "Preview the stock and meal cost."),
        s('[data-training="meal-post"]', "Review the preview and post the meal once.")),
    "requisition": (s('[aria-label="Reorder planning location"]', "Choose Training stockroom and review available stock and on-order quantities.", '{store}', "change"),
        s('[aria-label="Select TRAIN-CHICKEN for replenishment"]', "Select the chicken replenishment line."),
        s('[data-training="request-department"]', "Enter Kitchen as the requesting department.", "Kitchen", "input"),
        s('[data-training="request-reason"]', "Explain the need: busy weekend.", "busy weekend", "input"),
        s('[data-training="request-review"]', "Check the suggested quantity and request approval."),
        s('[data-training="confirm"]', "Submit the requisition after checking its location and amount.")),
    "approve_po": (s('[data-training="po-approve"]', "This order was created by a different colleague. Review supplier, price, location and your authority, then approve."),
        s('[data-training="confirm"]', "Confirm approval after reviewing the commitment. Training events stay in this sandbox.")),
}
for index, lesson in enumerate(LESSONS):
    if lesson.workflow in EXTRA_STEPS:
        LESSONS[index] = replace(lesson, steps=EXTRA_STEPS[lesson.workflow])
        if lesson.workflow == "approve_po":
            LESSONS[index] = replace(LESSONS[index], route="/purchasing/orders/{po}")
    elif lesson.workflow == "transfer":
        steps = list(lesson.steps)
        steps.insert(3, s('[name="destination"]', "Choose Training kitchen as the destination.", '{kitchen}', "change"))
        LESSONS[index] = replace(lesson, steps=tuple(steps))
    if lesson.id == "housekeeping-supplies":
        LESSONS[index] = replace(LESSONS[index], steps=tuple(replace(step,instruction=step.instruction.replace(" kg", " kits")) for step in LESSONS[index].steps))
    if lesson.id == "expiry-rotation":
        LESSONS[index] = replace(LESSONS[index], route="/inventory-operations")

OUTCOMES = {"issue":"/stock/issues", "receipt":"/stock/receipts", "transfer":"/stock/transfers",
    "count":"/counts/training-count/submit", "approve_count":"/counts/training-count/approve-guided",
    "receiving":"/receiving/purchase-orders/training-po", "return":"/receiving/purchase-orders/training-po/returns",
    "waste":"/inventory-controls/waste", "purchase_order":"/purchase-orders", "approve_po":"/purchase-orders/training-po/approve",
    "requisition":"/procurement/planning/requisitions", "production":"/production-batches/training-batch/execute", "staff_meal":"/staff-meals"}
for index, lesson in enumerate(LESSONS):
    if lesson.steps and lesson.workflow in OUTCOMES:
        steps=list(lesson.steps)
        steps[-1]=replace(steps[-1],outcome=OUTCOMES[lesson.workflow])
        if lesson.workflow == "count":
            steps[1]=replace(steps[1],outcome="/counts/training-count/entries")
        if lesson.workflow == "production":
            steps[0]=replace(steps[0],outcome="/production-batches/training-batch/start")
        LESSONS[index]=replace(lesson,steps=tuple(steps))

from training.catalogue_lessons import LESSONS as CATALOGUE_LESSONS
LESSONS.extend(CATALOGUE_LESSONS)
from training.control_lessons import LESSONS as CONTROL_LESSONS
from training.procurement_lessons import LESSONS as PROCUREMENT_LESSONS
LESSONS.extend(CONTROL_LESSONS)
LESSONS.extend(PROCUREMENT_LESSONS)
from training.food_lessons import LESSONS as FOOD_LESSONS
LESSONS.extend(FOOD_LESSONS)
from training.property_lessons import LESSONS as PROPERTY_LESSONS
LESSONS.extend(PROPERTY_LESSONS)
from training.connected_lessons import LESSONS as CONNECTED_LESSONS
LESSONS.extend(CONNECTED_LESSONS)
from training.capstone_lessons import build_capstones
LESSONS.extend(build_capstones({lesson.id:lesson for lesson in LESSONS}))

from training.extensions_lessons import LESSONS as EXTENSION_LESSONS
LESSONS.insert(1,next(lesson for lesson in EXTENSION_LESSONS if lesson.id=="counter-foundations"))
LESSONS.extend(lesson for lesson in EXTENSION_LESSONS if lesson.id!="counter-foundations")

from training.admin_lessons import LESSONS as ADMIN_LESSONS
from training.csv_lessons import LESSONS as CSV_LESSONS
LESSONS.extend(ADMIN_LESSONS)
LESSONS.extend(CSV_LESSONS)

from training.steward_lessons import LESSONS as STEWARD_LESSONS
LESSONS.extend(STEWARD_LESSONS)

BY_ID = {lesson.id: lesson for lesson in LESSONS}
assert len(BY_ID) == len(LESSONS)

# Linked capstones retain one database; unfinished sequences are labeled honestly.
CAPSTONES = [
    {"id": "busy-weekend", "title": "Prepare for a busy weekend", "linked":True,"lessons": ["cap-busy-weekend"]},
    {"id": "delivery-problems", "title": "Handle supplier delivery problems", "linked":True,"lessons": ["cap-delivery-recovery"]},
    {"id": "restaurant-service", "title": "Follow restaurant ingredients", "linked":True,"lessons": ["cap-restaurant-service"]},
    {"id": "monthly-count", "title": "Complete a monthly stock count", "linked":True,"lessons": ["cap-monthly-count"]},
    {"id": "housekeeping", "title": "Prepare rooms for arriving guests", "linked":True,"lessons": ["cap-housekeeping"]},
    {"id": "owner-review", "title": "Review the resort's inventory controls", "linked":True,"lessons": ["cap-owner-review"]},
]
