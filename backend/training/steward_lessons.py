"""Remaining actual maintenance controls and a read-only price analysis."""
from training.lesson_types import Lesson, Step, input_step as fill, select_step as choose, action_step as act
STOCK=("inventory_manager","owner")
BUY=("procurement_officer","owner")


def task(id,module,title,roles,route,situation,concept,example,rule,question,steps,sources,global_access=False,quantity=5):
    return Lesson(id,module,title,roles,route,"steward_"+id,situation,concept,example,rule,question,"no",rule+" "+situation,sources,tuple(steps),quantity,global_access=global_access)


LESSONS=[
    task("unlink-obsolete-supplier-item","I","Remove an obsolete supplier-item link",BUY,"/items/{chicken}",
        "Training Valley Foods no longer supplies chicken for new purchases. The purchasing steward approved removing its item link. Remove that exact link while preserving the supplier, existing TRAIN-PO and all stock history.",
        "A supplier-item link is sourcing configuration. Removing it neither cancels an existing order nor returns goods already received.",
        "An old price/lead-time link can be removed while the original approved order remains an obligation that must be followed up separately.",
        "Verify the item and supplier before unlinking. Preserve current orders and coordinate an approved replacement source.",
        "Does removing this supplier link cancel the existing purchase order? yes or no",(
            act('[data-training-unlink-supplier="training-supplier"]',"Remove only the Training Valley Foods item link.","/supplier-items/*"),),("catalogue_configuration.py",),global_access=True),
    task("create-authorized-storage-location","Z","Create an approved storage location",("owner",),"/locations",
        "The administrator approved a new child storeroom under Training stockroom. Create code TRAIN-CAFE-STORE, name Training café supplies, type Storeroom and parent TRAIN-STORE. It starts empty; no supplies have moved yet.",
        "A location describes where stock can be recorded. Creating a location does not issue, transfer or receive supplies or grant staff access.",
        "A new café storeroom needs its own approved transfer and appropriate staff scopes before an actual handover can be recorded there.",
        "Use the approved stable code and hierarchy, then arrange access and real movements separately.",
        "Does creating a storage location move supplies into it? yes or no",(
            act('[data-training="location-create-open"]',"Open Add storage location."),
            fill('#location-code',"Use stable code TRAIN-CAFE-STORE.","TRAIN-CAFE-STORE"),
            fill('#location-name',"Name it Training café supplies.","Training café supplies"),
            choose('#location-type',"Choose Storeroom.","storeroom"),
            choose('#location-parent',"Choose Training stockroom as its parent.",'{store}'),
            act('[data-training="location-create-save"]',"Create the approved empty child location.","/locations")),("inventory.py",),global_access=True),
    task("correct-storage-location-label","Z","Correct a location name without moving stock",("owner",),"/locations/{kitchen}",
        "The administrator approved the clearer name Training kitchen dry store for TRAIN-KITCHEN. Change only its name. Keep its stable code, Storeroom type and top-level hierarchy unchanged.",
        "A label correction changes how the same location is described. It does not move its balances or create another location.",
        "The original TRAIN-KITCHEN references remain the same after an approved display-name correction.",
        "Check the original stable code before changing the label. Do not replace a location merely to hide its stock history.",
        "Does renaming a location physically transfer its stock? yes or no",(
            fill('#location-detail-name',"Use the approved name Training kitchen dry store.","Training kitchen dry store"),
            act('[data-training="location-detail-save"]',"Save only the approved label correction.","/locations/training-kitchen")),("location_controls.py",)),
    task("stock-screen-signed-correction","H","Record an authorized signed balance correction",STOCK,"/stock",
        "A supervisor verified that the original opening record overstated the physical chicken by {quantity} kg. Use the Stock screen's Correct the stock balance option for this approved correction: signed change {correction_delta} kg, unit cost PHP 200/kg, reason Verified opening correction and reference {reference}. This is not a supplier delivery or a new physical issue.",
        "A signed correction removes an overstatement with a negative quantity. It preserves the old posting and adds a traceable correction; a count difference still needs its proper count review.",
        "A verified overstatement of 5 kg is a -5 kg adjustment, not another +5 kg receipt. The stored weighted-average cost determines the removal's value.",
        "Use this route only with verified authorization and evidence. Do not conceal waste, a supplier return or an unreceived delivery with an adjustment.",
        "Should an adjustment be used to pretend an unreceived supplier delivery arrived? yes or no",(
            act('[data-training="stock-open"]',"Open Record a stock movement."),
            choose('#stock-kind',"Choose Correct the stock balance.","adjustment"),
            choose('[name="location"]',"Choose Training stockroom.",'{store}'),
            choose('[name="item"]',"Choose Chicken (kg).",'{chicken}'),
            fill('[name="quantity"]',"Remove the overstatement using signed change {correction_delta} kg.",'{correction_delta}'),
            fill('[name="cost"]',"Verify PHP 200 per kg, not the line total.","200"),
            fill('[name="reason"]',"Record Verified opening correction.","Verified opening correction"),
            fill('[name="reference"]',"Keep reference {reference}.",'{reference}'),
            act('[data-training="stock-review"]',"Review the signed removal and original correction evidence."),
            act('[data-training="confirm"]',"Post this one authorized correction.","/stock/adjustments")),("inventory.py",)),
    task("assign-menu-selling-controls","R","Assign approved selling rules and shared add-ons",STOCK,"/fnb/menu",
        "Edit Training Chicken Alfredo. Keep its Regular base price PHP 250, original SKU, availability and POS visibility. Assign pricing tag train-main, a PHP 220 conditional price for Training drink and main, and reusable group Training plate extras. A separate Training iced coffee product already has qualifying tag train-drink. No live POS is connected here.",
        "Products must have the approved qualifying/target tags and variant price for a conditional rule to apply. Reusable add-ons retain a central definition; configuration save is separate from POS synchronization and guest sales.",
        "The base plate is PHP 250. Its PHP 220 conditional price applies only when the approved drink condition is met; optional cheese and sauce add their configured prices separately.",
        "Check both sides of a promotion, prices and shared options before offering it. A priced add-on does not by itself map extra ingredient consumption; verify its POS handling and synchronization separately. Do not create a conflicting product copy.",
        "Does the PHP 220 conditional price apply without the qualifying drink? yes or no",(
            act('[data-training="menu-edit-training-review-menu"]',"Edit the existing Training Chicken Alfredo product."),
            fill('[aria-label="Menu pricing tags"]',"Assign the target tag train-main.","train-main"),
            fill('[aria-label="Variant 1 conditional price for Training drink and main"]',"Use approved conditional price PHP 220.","220"),
            act('[aria-label="Use reusable group Training plate extras"]',"Select the existing shared Training plate extras group."),
            act('[data-training="menu-save"]',"Retain base price, identity, availability and POS visibility, then save.","/fnb/menu/training-review-menu")),("menu.py","pos_rules.py"),global_access=True),
    task("retry-eligible-inbound-event","S","Stop an inbound POS event from using outbound Retry",("owner",),"/integrations",
        "TRAIN-POS-RETRY is a failed inbound POS diagnostic. The steward has checked its mapping, but this inbox Retry is for outbound delivery only. In this isolated exercise click its Retry and read the refusal. Keep the original failed event unchanged; the POS sender must use its reviewed intake retry with the original identity.",
        "A corrected mapping does not make an inbound event eligible for an outbound worker. Pending would not prove consumption or financial acceptance.",
        "Inbound POS evidence stays Failed after the refused generic retry. The original sender and integration steward must verify the original sale before any real replay.",
        "Use the correct direction and authority. Generic Retry accepts only eligible failed/dead-letter outbound events; both retry routes protect delivered or accepted Accounting evidence.",
        "May an inbound POS event be queued through the outbound Retry button? yes or no",(
            act('[data-training="integration-retry-training-pos-retry"]',"Read the real refusal: this event is inbound, not outbound.","/integration-events/training-pos-retry/retry",409),),("operations.py",),global_access=True),
    task("activate-verified-pos-mapping","S","Activate a checked product-recipe mapping",("owner",),"/integrations/pos",
        "TRAIN-POS-PLATE has an inactive mapping to approved TRAIN-ALFREDO at Training stockroom. The integration steward verified the exact product, recipe and location. Activate that mapping for future handling. No historical sale is being consumed by this action.",
        "Activation enables a verified existing mapping. It must not point to a draft or retired recipe; failed historical work still needs its separately reviewed retry process.",
        "An activated one-portion mapping will use the approved recipe when a later eligible sale is processed, not merely when this button is pressed.",
        "Verify the exact approved formula and location before activation. Inspect any old failed events separately and prevent duplicate consumption.",
        "Does mapping activation itself consume historical sales? yes or no",(
            act('[data-training="pos-mapping-toggle-training-pos-map"]',"Activate the verified mapping to approved TRAIN-ALFREDO.","/pos-mappings/training-pos-map/activate"),),("pos_sync.py",),global_access=True),
    task("calculate-food-margin","P","Compare food cost, gross profit and margin",STOCK,"/production/recipes/{recipe}",
        "At Training stockroom, the approved one-portion formula costs PHP 50. Run a Margin scenario using selling price PHP {margin_price}. Read food cost, gross margin and gross profit per unit. This analysis must not change menu/POS prices or stock.",
        "Gross profit per unit is selling price less recipe cost. Food cost percent divides recipe cost by selling price; gross margin percent divides gross profit by selling price. These exclude other costs such as labor and overhead.",
        "At PHP 250 selling price and PHP 50 recipe cost, gross profit is PHP 200, food cost is 20% and gross margin is 80%; these figures do not mean PHP 200 net profit.",
        "Check the cost location and units first. Analyze an approved candidate price without treating it as authority to change menu prices.",
        "Does Calculate margin change the approved menu selling price? yes or no",(
            choose('[aria-label="Recipe costing location"]',"Choose Training stockroom for the cost basis.",'{store}'),
            fill('[aria-label="Margin selling price"]',"Analyze price PHP {margin_price} per output unit.",'{margin_price}'),
            act('[data-training="margin-calculate"]',"Calculate and read food cost, gross margin and gross profit per unit.","/recipes/training-recipe/margin-scenario")),("recipe_costing.py",)),
]
