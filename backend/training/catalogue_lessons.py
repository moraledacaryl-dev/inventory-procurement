"""Catalogue and supplier maintenance, including genuine refusal outcomes."""
from training.lesson_types import Lesson, Step

STOCK = ("inventory_manager", "owner")
BUY = ("procurement_officer", "owner")


def input_step(target, instruction, value):
    return Step(target, instruction, value, "input")


def select_step(target, instruction, value):
    return Step(target, instruction, value, "change")


def save(target, instruction, endpoint, status=None):
    return Step(target, instruction, outcome=endpoint, outcome_status=status)


def lesson(id, module, title, roles, route, situation, concept, example, rule,
           question, answer, correction, steps, *, quantity=0, global_access=True):
    sources=("inventory.py", "inventory_operations.py", "catalogue_configuration.py") if module=="C" else ("procurement.py", "supplier_360.py", "catalogue_configuration.py")
    if isinstance(steps,Step): steps=(steps,)
    return Lesson(id,module,title,roles,route,"catalogue_"+id,situation,concept,example,rule,
                  question,answer,correction,sources,steps,quantity,global_access=global_access)


LESSONS = [
    lesson("create-item","C","Create a correctly classified item",STOCK,"/items",
        "You have been assigned global item-maintenance access. Set up TRAIN-OIL, Training cooking oil, as an F&B Ingredient bought and stored in litres. Its minimum is {quantity} litres and standard cost is PHP 150 per litre. Do not record stock yet.",
        "An item record describes a supply. Its base unit controls quantities throughout stock and recipes. Creating the record does not mean anything was delivered.",
        "A 5-litre container contains 5 base litres. It is not 5 millilitres or five individual bottles unless those are deliberately configured units.",
        "Check classification and base unit before the first stock transaction. Creating a catalogue item never establishes an opening balance.",
        "Does creating an item add physical stock? yes or no","no","Create the catalogue record only. An opening balance or real receipt is a separate authorized transaction.",(
            Step('[data-training="item-create-open"]',"Open Add item."),
            select_step('#item-workspace',"Choose F&B.","fnb"),
            select_step('#item-type',"Choose Ingredient.","ingredient"),
            input_step('#item-sku',"Use the unique SKU TRAIN-OIL.","TRAIN-OIL"),
            input_step('#item-name',"Enter Training cooking oil.","Training cooking oil"),
            select_step('#item-category',"Choose Training food.","category"),
            select_step('#item-unit',"Choose TRAIN-L, the litre base unit.","litre"),
            select_step('#item-location',"Choose Training stockroom.","store"),
            input_step('#item-minimum',"Set the minimum to {quantity} litres.","{quantity}"),
            input_step('#item-cost',"Enter PHP 150 for one litre, not the value of all stock.","150"),
            save('[data-training="item-create-save"]',"Review the unit and classification, then create the item.","/items")),quantity=12),
    lesson("edit-item-reorder","C","Change a minimum without changing stock",STOCK,"/items/{chicken}",
        "You have global item-maintenance authority. The approved minimum for chicken is now {quantity} kg. Update only that minimum; leave its name, base unit, cost and stock controls unchanged.",
        "A minimum is a replenishment trigger. Editing it changes purchasing guidance, not the quantity on the shelf.",
        "Changing the minimum from 40 kg to 12 kg does not issue 28 kg. Physical movements still need their own records.",
        "Change the policy that was approved. Do not change a base unit or permit negative stock as a shortcut.",
        "Does changing minimum stock move physical stock? yes or no","no","The minimum is a policy. Leave quantities, base unit and stock controls unchanged.",(
            input_step('#detail-minimum',"Enter the approved minimum of {quantity} kg.","{quantity}"),
            save('[data-training="item-detail-save"]',"Save the policy and confirm the item reloads.","/items/training-chicken")),quantity=12),
    lesson("add-item-barcode","C","Add a scan code to the intended item",STOCK,"/items/{chicken}",
        "You have global item-maintenance authority. Add the fictional internal scan code {barcode} to Chicken (kg). Use INTERNAL as the code type.",
        "A barcode identifies an existing item. Assigning it to the wrong item makes scanning select the wrong supply even when the printed description looks familiar.",
        "A scan of a chicken label must resolve to chicken, not cooking oil. The scan code does not say how many kilograms arrived.",
        "Check the item before linking a unique scan code. A barcode does not replace a quantity or unit.",
        "Does adding a barcode record a delivery? yes or no","no","A scan code identifies the item. Receiving still records actual quantities.",(
            input_step('[data-training="barcode-form"] [name="barcode"]',"Enter the fictional scan code {barcode}.","{barcode}"),
            select_step('[data-training="barcode-form"] [name="barcode_type"]',"Choose INTERNAL for this training code.","INTERNAL"),
            save('[data-training="barcode-save"]',"Add the barcode to this chicken item.","/items/training-chicken/barcodes"))),
    lesson("remove-item-barcode","C","Remove an obsolete scan code",STOCK,"/items/{chicken}",
        "The supplier stopped using TRAIN-OLD-SCAN. You have global item-maintenance authority. Remove that obsolete code from Chicken (kg), while keeping the item and its history.",
        "Removing a barcode removes a scanning shortcut. It does not delete the item or erase stock movements.",
        "When a label is replaced, remove the old scan code only after checking the intended item. Keep the canonical SKU.",
        "Remove the obsolete code, not the item or its stock history.",
        "Should removing an obsolete barcode erase stock history? yes or no","no","Only remove the old scan identity. Keep the item and its movement records.",(
            save('[data-training="barcode-remove"]',"Check TRAIN-OLD-SCAN belongs to chicken, then remove this code.","/items/training-chicken/barcodes/training-old-barcode"))),
    lesson("define-unit-conversion","C","Configure the direction of a unit conversion",STOCK,"/items/{chicken}",
        "You have global item-maintenance authority. Configure {conversion_description} for chicken. Check the From unit, To unit and multiplier together.",
        "The multiplier answers how many To units equal one From unit. The reverse direction uses the reciprocal; it is not the same number.",
        "One kg is 1,000 g. One g is 0.001 kg. Swapping the direction without changing the multiplier can create a million-fold error.",
        "Read a conversion as a full sentence before saving: one From unit equals multiplier To units.",
        "How many grams are in one kilogram?","1000","1 kg equals 1,000 g. The reverse is 1 g equals 0.001 kg.",(
            select_step('[data-training="conversion-form"] [name="from_unit_id"]',"Choose {conversion_from_name} as the From unit.","conversion_from"),
            input_step('[data-training="conversion-form"] [name="multiplier"]',"Enter {conversion_multiplier} as the multiplier.","{conversion_multiplier}"),
            select_step('[data-training="conversion-form"] [name="to_unit_id"]',"Choose {conversion_to_name} as the To unit.","conversion_to"),
            save('[data-training="conversion-save"]',"Read the direction again, then add the conversion.","/items/training-chicken/conversions"))),
    lesson("set-location-policy","C","Set a stockroom-specific replenishment policy",STOCK,"/items/{chicken}",
        "For the training stockroom, set chicken minimum to {quantity} kg, reorder quantity to 20 kg, maximum to 60 kg and count interval to 7 days. Leave supplier override blank. Your location assignment permits this stockroom.",
        "A location policy applies to one storage location. Its minimum, reorder target and maximum are different values; the count interval schedules review, not stock consumption.",
        "A kitchen can have a lower minimum than the main stockroom. Changing the kitchen policy should not silently change the stockroom's policy.",
        "Check the location and units. A replenishment policy never creates a purchase order or changes physical stock by itself.",
        "Does saving a location policy automatically order supplies? yes or no","no","The policy supports planning. A purchase still needs the actual request and approval workflow.",(
            select_step('[data-training="policy-form"] [name="location_id"]',"Choose Training stockroom.","store"),
            input_step('[data-training="policy-form"] [name="minimum_stock"]',"Enter a minimum of {quantity} kg.","{quantity}"),
            input_step('[data-training="policy-form"] [name="reorder_quantity"]',"Enter a reorder quantity of 20 kg.","20"),
            input_step('[data-training="policy-form"] [name="maximum_stock"]',"Enter a maximum of 60 kg.","60"),
            input_step('[data-training="policy-form"] [name="cycle_count_days"]',"Count every 7 days.","7"),
            save('[data-training="policy-save"]',"Review the location and save its policy.","/item-location-settings")),quantity=12,global_access=False),
    lesson("deactivate-empty-item","C","Retire an item without erasing history",STOCK,"/items/{retired}",
        "TRAIN-RETIRED is no longer used. You have global item-maintenance authority. It has zero stock at every location. Deactivate it after checking its stock position.",
        "Deactivation stops future use while preserving the record. It is different from deleting historical transactions.",
        "An unused supply with zero stock can be retired. A supply still on a shelf must first follow its legitimate issue, transfer, return or disposal workflow.",
        "Never invent an adjustment merely to make deactivation possible.",
        "Can an item with non-zero stock be deactivated? yes or no","no","The application blocks non-zero stock. Resolve the physical stock through its legitimate workflow first.",(
            Step('[data-training="item-status"]',"Check zero stock, then choose Deactivate item."),
            save('[data-training="confirm"]',"Confirm deactivation. The record stays in history.","/items/training-retired"))),
    lesson("reactivate-item","C","Bring a retired item back into use",STOCK,"/items/{retired}",
        "TRAIN-RETIRED has been approved for use again. You have global item-maintenance authority. Reactivate its existing record instead of creating a duplicate SKU.",
        "Reactivation keeps one continuous item identity. It does not recreate opening stock or restore supplies that were consumed.",
        "If a seasonal supply returns, reactivate the correct existing SKU after review, then separately record actual incoming stock.",
        "Reuse the approved identity; record real stock separately.",
        "Does reactivation restore previously consumed stock? yes or no","no","Reactivation changes availability of the catalogue record, not its physical quantity.",(
            Step('[data-training="item-status"]',"Choose Reactivate item."),
            save('[data-training="confirm"]',"Confirm that this existing item may be used again.","/items/training-retired"))),
    lesson("stock-blocks-deactivation","C","Recognize why an item cannot be retired",STOCK,"/items/{chicken}",
        "A colleague asks you to retire chicken even though it still has stock. In this isolated practice, try Deactivate and read the refusal. Leave the chicken and its stock unchanged.",
        "A protective refusal is a useful outcome. Changing recorded stock just to bypass it would hide the physical supplies that still exist.",
        "If there are 24 kg on hand, a request to hide the item does not justify writing off 24 kg.",
        "Stop at the refusal. Investigate the physical supplies and use the appropriate authorized movement if needed.",
        "Should you write off stock just to bypass deactivation? yes or no","no","Do not change stock to bypass a control. Keep the item active and resolve the real situation.",(
            Step('[data-training="item-status"]',"Try Deactivate item in this fictional practice."),
            save('[data-training="confirm"]',"Confirm the trial and read why the application refuses it.","/items/training-chicken",409))),
    lesson("catalogue-scope-required","C","Recognize when your assignment is insufficient",("inventory_manager",),"/items/{chicken}",
        "You manage the training stockroom, but have no global catalogue assignment. In this isolated exercise, try changing chicken's minimum to {quantity} kg. Read the refusal, leave the saved record unchanged and ask the global catalogue steward.",
        "A role and a location assignment are separate controls. Permission to manage stock in one storeroom does not automatically authorize global catalogue changes.",
        "A stockroom manager may count and issue authorized supplies while a global steward controls the item's master settings.",
        "Ask the authorized steward. Do not switch accounts, change your role or alter stock to bypass the control.",
        "Does a stockroom assignment automatically grant global catalogue access? yes or no","no","A location scope grants local responsibilities. Global master-data work needs its own authorized assignment.",(
            input_step('#detail-minimum',"Enter {quantity} as the proposed minimum in this isolated exercise.","{quantity}"),
            save('[data-training="item-detail-save"]',"Try saving, then read the access refusal. The saved minimum must stay unchanged.","/items/training-chicken",403)),quantity=12,global_access=False),
    lesson("create-supplier","I","Add a fictional supplier with clear terms",BUY,"/suppliers",
        "Purchasing approved a new fictional supplier: TRAIN-GARDEN, Training Garden Supplies. The contact is Training contact, email garden@example.com and payment terms are {terms} days. Leave optional phone details blank.",
        "A supplier record holds identity, contact details and agreed terms. Adding it does not place an order, accept a delivery or make a payment.",
        "Terms of 14 days describe when an invoice is due under the agreement; they are not evidence that it has been paid.",
        "Use an approved unique code and verified terms. Keep ordering, receiving and payment evidence separate.",
        "Does adding a supplier create a payment? yes or no","no","A supplier profile creates no payment or delivery. Those need separate authorized workflows.",(
            Step('[data-training="supplier-create-open"]',"Open Add supplier."),
            input_step('#supplier-code',"Use TRAIN-GARDEN as the unique supplier code.","TRAIN-GARDEN"),
            input_step('#supplier-name',"Enter Training Garden Supplies.","Training Garden Supplies"),
            input_step('#supplier-contact',"Enter Training contact.","Training contact"),
            input_step('#supplier-email',"Enter the fictional email garden@example.com.","garden@example.com"),
            input_step('#supplier-terms',"Enter the agreed {terms} days.","{terms}"),
            save('[data-training="supplier-create-save"]',"Check the code and terms, then add the supplier.","/suppliers"))),
    lesson("edit-supplier-terms","I","Update approved contact and payment terms",BUY,"/suppliers/{supplier}",
        "Training Valley Foods supplied an approved contact change: Training purchasing contact. The new payment terms are {terms} days. Update those details without changing its code or historical orders.",
        "Master-data updates maintain current contact and commercial terms. They do not rewrite old purchase receipts or prove financial settlement.",
        "A new contact helps future purchasing. A previous delivery remains the same historical transaction.",
        "Save approved current terms and retain historical purchasing evidence.",
        "Does changing payment terms mark an invoice paid? yes or no","no","Terms are an agreement, not payment evidence.",(
            input_step('#supplier-detail-contact',"Enter Training purchasing contact.","Training purchasing contact"),
            input_step('#supplier-detail-terms',"Enter the approved {terms} days.","{terms}"),
            save('[data-training="supplier-detail-save"]',"Review and save the approved changes.","/suppliers/training-supplier"))),
    lesson("link-supplier-item","I","Link an item to its preferred supplier",BUY,"/items/{amenities}",
        "Link Guest amenity kit to Training Valley Foods. Its supplier code is TRAIN-KIT, last price PHP 50, lead time 3 days and minimum order quantity 2 kits. Mark this source as preferred.",
        "The supplier-item link stores commercial references. Preferred source supports planning; it does not bypass comparison or approval.",
        "A lead time of 3 days is a planning estimate. MOQ 2 means the supplier's minimum order quantity, not the amount currently in stock.",
        "Check the intended item, supplier, units and price. Save commercial references without inventing stock.",
        "Does a preferred supplier remove purchase approval requirements? yes or no","no","Preferred is a planning preference. Actual approval and quantity controls still apply.",(
            select_step('[data-training="supplier-link-form"] [name="supplier_id"]',"Choose Training Valley Foods.","supplier"),
            input_step('[data-training="supplier-link-form"] [name="supplier_sku"]',"Enter TRAIN-KIT as the supplier item code.","TRAIN-KIT"),
            input_step('[data-training="supplier-link-form"] [name="last_price"]',"Enter PHP 50 for one kit.","50"),
            input_step('[data-training="supplier-link-form"] [name="lead_time_days"]',"Enter 3 delivery days.","3"),
            input_step('[data-training="supplier-link-form"] [name="minimum_order_quantity"]',"Enter a minimum order quantity of 2 kits.","2"),
            Step('[data-training="supplier-link-form"] [name="is_preferred"]',"Mark this approved source as Preferred."),
            save('[data-training="supplier-link-save"]',"Check the price and units, then link the supplier.","/suppliers/training-supplier/items"))),
    lesson("deactivate-unused-supplier","I","Retire a supplier after checking open orders",BUY,"/suppliers/{unused_supplier}",
        "TRAIN-OLD-SUPPLIER is no longer approved for new purchasing. It has no open orders. Deactivate its existing supplier record after reviewing the workspace.",
        "Deactivation keeps historical records but prevents new purchasing use. Open obligations must be resolved before the supplier can be retired.",
        "An inactive supplier's previous receipts and returns remain available as evidence.",
        "Check open orders before deactivation. Keep the original supplier identity and history.",
        "Does supplier deactivation erase historical receipts? yes or no","no","The profile and historical purchasing evidence remain.",(
            Step('[data-training="supplier-status"]',"Check that there are no open orders, then choose Deactivate supplier."),
            save('[data-training="confirm"]',"Confirm supplier deactivation.","/suppliers/training-unused-supplier"))),
    lesson("reactivate-supplier","I","Reactivate an approved supplier identity",BUY,"/suppliers/{unused_supplier}",
        "Purchasing approved TRAIN-OLD-SUPPLIER for use again. Reactivate the existing supplier identity rather than creating a duplicate profile.",
        "Reactivation restores availability for future authorized purchasing. It does not recreate earlier orders or mark old obligations paid.",
        "A seasonal supplier can return under the same reviewed identity, preserving its performance history.",
        "Review the identity and approved terms; reuse the existing profile.",
        "Should you create a duplicate code to bypass an inactive supplier? yes or no","no","Reactivate the approved existing identity through the authorized control.",(
            Step('[data-training="supplier-status"]',"Choose Reactivate supplier."),
            save('[data-training="confirm"]',"Confirm reactivation of the existing supplier.","/suppliers/training-unused-supplier"))),
    lesson("open-orders-block-deactivation","I","Handle a supplier with outstanding obligations",BUY,"/suppliers/{supplier}",
        "Training Valley Foods still has an approved open purchase order. In this isolated practice, try deactivation and read the refusal. Keep the supplier, order and stock unchanged.",
        "An open order is an outstanding obligation. Hiding the supplier would make normal follow-up harder, so the application requires the order to be resolved first.",
        "An order awaiting 10 kg is still open even though no goods have arrived. Deactivation is not cancellation.",
        "Resolve the legitimate order through its own authorized workflow. Do not invent receipts or cancel commitments merely to hide a supplier.",
        "Does deactivating a supplier cancel its purchase orders? yes or no","no","Supplier status and purchase-order cancellation are separate controls.",(
            Step('[data-training="supplier-status"]',"Try Deactivate supplier in this fictional practice."),
            save('[data-training="confirm"]',"Read the refusal caused by the outstanding order.","/suppliers/training-supplier",409))),
]
