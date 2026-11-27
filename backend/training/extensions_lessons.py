"""Actual selling controls, cancellation and departmental unit decisions."""
from training.lesson_types import Lesson, Step, input_step as fill, select_step as choose, action_step as act
STOCK=("inventory_manager","owner")


def task(id,module,title,route,situation,concept,example,rule,steps,sources,quantity=5):
    return Lesson(id,module,title,STOCK,route,"extended_"+id,situation,concept,example,rule,
        ({"Q":"Does cancelling a batch automatically dispose of spoiled ingredients? yes or no","E":"Should a packaging count replace the configured stock base-unit quantity? yes or no"}.get(module,"Does saving this configuration prove it was synchronized to the external POS? yes or no")),"no",rule+" "+situation,sources,tuple(steps),quantity,global_access=module=="R")


LESSONS=[
    Lesson("counter-foundations","A","Check your count, unit and responsibility",("counter","owner"),"/counts/{count}","read_count",
        "Before counting TRAIN-CHICKEN, inspect TRAIN-COUNT. Read the item name and unit. Leave the physical quantity blank until you have counted it.",
        "Physical stock is what is present. Reserved stock is set aside; available stock excludes reservations. Consumed stock has left inventory. A blind counter records physical observations without seeing system quantities.",
        "If you physically find 8 kg, record 8 kg even if someone suggests a different system amount. Zero means counted and none found; blank means not yet counted.",
        "Check the correct shelf, item and unit. Ask a different authorized reviewer to investigate differences; do not guess hidden quantities.",
        "Is an uncounted blank the same as a physical zero? yes or no","no","Inspect the count first and keep uncounted observations blank.",("guided_counts.py",)),
    task("create-conditional-price-rule","R","Define a conditional selling rule","/fnb/selling-rules",
        "Create rule Training drink and pastry. Use qualifying group train-drink and discounted group train-pastry. Keep the rule active with default priority 100. Actual products and special prices will be assigned separately in Menu & Products.",
        "A rule connects qualifying and discounted product groups. It does not set every product's price or create a sale.",
        "A drink can qualify a pastry for its separately approved special price. Products must belong to the correct groups before this can apply.",
        "Use approved groups and prices. Confirm product assignments and synchronization with the POS owner before offering the promotion.",(
            fill('[data-training="pricing-name"]',"Name the rule Training drink and pastry.","Training drink and pastry"),
            fill('[data-training="pricing-qualifier"]',"Use qualifying group train-drink.","train-drink"),
            fill('[data-training="pricing-target"]',"Use discounted group train-pastry.","train-pastry"),
            act('[data-training="pricing-save"]',"Keep Active checked and save the approved group relationship.","/fnb/pos-rules/pricing")),("pos_rules.py","menu.py")),
    task("deactivate-conditional-price-rule","R","Retire an expired promotion without deleting it","/fnb/selling-rules",
        "The approved Training weekend promotion has ended. Open that exact rule from the library, clear Active and save. Preserve its name, qualifying train-drink group, discounted train-pastry group and priority 100.",
        "Deactivation preserves configuration and history. It does not refund old sales or restore stock.",
        "Ending a weekend offer stops its future use after the configured catalogue is synchronized; past customer orders remain unchanged.",
        "Retire only the approved rule and coordinate POS synchronization. Confirm actual POS state before promising a changed price.",(
            act('[data-training="pricing-edit-training-rule"]',"Open Training weekend promotion from the rule library."),
            act('[data-training="pricing-active"]',"Clear Active for this expired promotion."),
            act('[data-training="pricing-save"]',"Save the inactive rule while preserving its groups.","/fnb/pos-rules/pricing/training-rule")),("pos_rules.py","menu.py")),
    task("create-reusable-add-ons","R","Create reusable multiple-choice pizza add-ons","/fnb/selling-rules",
        "Create template Training pizza extras with cashier prompt Choose pizza extras. Allow Multiple allowed. Enter Extra cheese | 30 and Extra pepperoni | 40 on separate lines. Keep it active. Assigning this template to products is a separate authorized step.",
        "A reusable modifier group avoids maintaining conflicting copies of the same add-on. Multiple selection permits more than one option; each chosen option adds its own price.",
        "Extra cheese at PHP 30 plus extra pepperoni at PHP 40 adds PHP 70 to the approved base price.",
        "Check each option and price, keep the group optional as configured, and verify product assignment before selling it.",(
            fill('[data-training="modifier-template-name"]',"Name it Training pizza extras.","Training pizza extras"),
            fill('[data-training="modifier-template-prompt"]',"Use prompt Choose pizza extras.","Choose pizza extras"),
            choose('[data-training="modifier-template-mode"]',"Allow multiple optional add-ons.","multi"),
            fill('[data-training="modifier-template-options"]',"Enter two lines: Extra cheese | 30, then Extra pepperoni | 40.","Extra cheese | 30\nExtra pepperoni | 40"),
            act('[data-training="modifier-template-save"]',"Keep the group active and save the reusable options.","/fnb/pos-rules/modifiers")),("pos_rules.py","menu.py")),
    task("correct-reusable-add-on-price","R","Correct an approved reusable add-on price","/fnb/selling-rules",
        "The authorized menu steward approved Extra cheese at PHP 35 instead of PHP 30. Open Training pizza extras and change only that option. Keep Extra pepperoni at PHP 40, multiple optional selection and the active status.",
        "A shared template change is master configuration. Verify its affected products and POS synchronization; the Inventory save is not proof of a completed sale or successful external delivery.",
        "Cheese at PHP 35 and pepperoni at PHP 40 adds PHP 75 when both are selected, before any other pricing rules.",
        "Change only the approved option, retain its stable identity and coordinate downstream product configuration.",(
            act('[data-training="modifier-template-edit-training-modifier"]',"Open Training pizza extras from the library."),
            fill('[data-training="modifier-template-options"]',"Keep both lines: Extra cheese | 35 and Extra pepperoni | 40.","Extra cheese | 35\nExtra pepperoni | 40"),
            act('[data-training="modifier-template-save"]',"Save the approved shared price correction.","/fnb/pos-rules/modifiers/training-modifier")),("pos_rules.py","menu.py")),
]

for started in (False,True):
    id="cancel-started-production" if started else "cancel-unstarted-production"
    steps=[act('[data-training="production-cancel"]',"Open cancellation for TRAIN-BATCH."),fill('[aria-label="Batch cancellation reason"]',"Record the genuine reason: Service plan changed.","Service plan changed")]
    if started:steps.append(fill('[aria-label="Batch material disposition"]',"Verify and record: No materials issued; ingredients remain in storage.","No materials issued; ingredients remain in storage"))
    steps.append(act('[data-training="confirm"]',"Cancel only after verifying the batch and material situation.","/production-batches/training-batch/cancel"))
    LESSONS.append(task(id,"Q","Cancel started preparation with material accountability" if started else "Cancel a plan before ingredients are used","/production/batches/{batch}",
        "TRAIN-BATCH "+("was started in the system, but physical preparation has not begun and no materials were issued. Cancel it with reason Service plan changed and material disposition No materials issued; ingredients remain in storage." if started else "is planned, but service needs changed before preparation. Cancel it with reason Service plan changed. No ingredients were used."),
        "Cancellation records a reason; it does not automatically dispose of materials, restore consumed ingredients or create finished goods.",
        "An untouched plan leaves stock unchanged. If materials were actually used or spoiled, record their real disposition through the authorized movement process as well.",
        "Inspect what physically happened before cancellation. An in-progress batch requires an explicit material disposition; never claim used food remains unused.",steps,("production_execution.py",)))

for id,title,item,quantity,unit,calculation in (
    ("issue-cafe-case","Convert a café case into the stock base unit","TRAIN-CANS — Café canned drink",24,"cans","One case contains 24 individual cans. The stock base unit is Each. Issue {quantity} individual cans, not {quantity} cases."),
    ("issue-bar-volume","Measure bar syrup in the configured volume unit","TRAIN-SYRUP — Bar syrup (mL)",60,"mL","The bottle contains 750 mL. Stock uses mL, so a measured {quantity} mL serving issue is not {quantity} bottles."),
):
    LESSONS.append(task(id,"E",title,"/stock",
        calculation+" Record the actual handover from Training stockroom with reason Service replenishment.",
        "Read the base unit before entry. Purchase packaging and physical serving measures must be converted to the unit the stock line expects.",
        "Two 24-can cases contain 48 individual cans; a 60 mL measured syrup issue is 0.08 of a 750 mL bottle.",
        "Record the actual measured base-unit quantity, check the item and location, and ask the catalogue steward about missing conversions.",(
            act('[data-training="stock-open"]',"Open Record a stock movement."),
            choose('#stock-kind',"Choose Used or issued stock.","issue"),
            choose('[name="location"]',"Choose Training stockroom.",'{store}'),
            choose('[name="item"]',"Choose "+item+".",'{service_item}'),
            fill('[name="quantity"]',"Enter {quantity} "+unit+" in the stock base unit.","{quantity}"),
            fill('[name="reason"]',"Use reason Service replenishment.","Service replenishment"),
            act('[data-training="stock-review"]',"Review the measured quantity and its base unit."),
            act('[data-training="confirm"]',"Post only the actual handover.","/stock/issues")),("inventory.py",),quantity))
