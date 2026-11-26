"""Build linked exercises from the already verified real-control patterns.

Each definition represents one attempt database, not a list of separate lessons.
The factory receives patterns explicitly to avoid circular curriculum imports.
"""
from dataclasses import replace
from training.lesson_types import Lesson, Step


def build_capstones(patterns):
    monthly=patterns["count-multiple-units"]
    delivery=patterns["damaged-delivery"]
    returned=patterns["supplier-return"]
    return_steps=tuple(replace(step,
        value="1" if step.target=='[aria-label="Quantity to return for Chicken (kg)"]' else step.value,
        instruction="Return only 1 kg of the previously accepted chicken." if step.target=='[aria-label="Quantity to return for Chicken (kg)"]' else step.instruction) for step in returned.steps)
    def linen_steps(id,qty,source,source_condition,dest,dest_condition,reason,ref,open_form=False):
        replacements={"{quantity}":qty,"{property_source}":source,"{property_from_condition}":source_condition,"{property_destination}":dest,"{property_to_condition}":dest_condition,"{property_reason}":reason,"{reference}":ref}
        steps=patterns[id].steps if open_form else patterns[id].steps[1:]
        return tuple(replace(step,value=replacements.get(step.value,step.value),instruction=("Record "+qty+" towels." if step.target=='[aria-label="Circulation quantity"]' else "Use handover reference "+ref+"." if step.target=='[aria-label="Circulation reference"]' else step.instruction)) for step in steps)
    house_steps=patterns["housekeeping-supplies"].steps+(Step('.nav-link[href="/hotel/property"]',"Open Property & Linen from the application navigation.",event="read",outcome="/property/balances"),)
    house_steps+=linen_steps("issue-clean-linen","4","{store}","{prop_clean}","{kitchen}","{prop_in_use}","{prop_issue}","TRAIN-ROOM-ISSUE",True)
    house_steps+=linen_steps("send-used-linen-to-laundry","2","{kitchen}","{prop_in_use}","{store}","{prop_laundry}","{prop_wash}","TRAIN-LAUNDRY")
    house_steps+=linen_steps("return-clean-linen","1","{store}","{prop_laundry}","{store}","{prop_clean}","{prop_wash}","TRAIN-CLEAN")
    owner_steps=patterns["accept-accountable-operations-work"].steps+patterns["complete-evidenced-operations-work"].steps+(
        Step('[data-training="integrations-back"]',"Return to the integrations overview."),
        Step('[data-training="integrations-accounting"]',"Open Accounting to check the separate failed handoff.",event="read",outcome="/integrations/accounting/workspace"),
    )+patterns["requeue-failed-accounting-handoff"].steps
    busy_steps=patterns["record-supplier-quotation"].steps+tuple(replace(step,target='[data-training-award-supplier="training-supplier"]' if step.target=='[data-training="quote-award-training-quote-fast"]' else step.target,instruction="Compare both offers and award the one-day offer you just recorded." if step.target=='[data-training="quote-award-training-quote-fast"]' else "Create the linked order. The fictional independent reviewer and receiving colleague then process their own authorized stages." if step.target=='[data-training="confirm"]' else step.instruction) for step in patterns["award-timely-quotation"].steps)+(Step('[data-training-order-requisition="training-requisition"]',"Open this awarded offer's linked order to inspect the partial receipt and remaining quantity.",event="read",outcome="/purchase-orders/*/detail"),)
    restaurant_steps=tuple(replace(step,value="{cap_material}" if step.target=='[aria-label="Actual quantity for training-chicken"]' else step.value,instruction="The actual batch used {cap_material} kg raw chicken. Enter that actual use." if step.target=='[aria-label="Actual quantity for training-chicken"]' else step.instruction) for step in patterns["batch-production"].steps)+(Step('.nav-link[href="/fnb/staff-meals"]',"Open Staff Meals in the application navigation.",event="read",outcome="/staff-meals"),)+tuple(replace(step,value="{alfredo}" if step.target=='#ingredient-0' else "2" if step.target=='#quantity-0' else step.value,instruction="Choose the prepared Training Chicken Alfredo portions, not raw chicken." if step.target=='#ingredient-0' else "Use 2 prepared portions for the actual staff lunch." if step.target=='#quantity-0' else step.instruction) for step in patterns["staff-meal"].steps)
    return [
        Lesson("cap-busy-weekend","K","Source weekend demand and follow the linked delivery",("procurement_officer","owner"),"/purchasing?view=source","capstone_busy",
            "Your colleague's independently approved TRAIN-REQUEST covers {quantity} kg additional weekend demand after available stock, reservations and commitments were checked. It is needed within two days. Training Budget Foods already offers PHP 200/kg in 8 days. Record Training Valley Foods' actual PHP 220/kg offer, 1 delivery day, {terms} payment days and Notes {reference}; leave expiry blank. Award that timely offer to Training stockroom. Deterministic authorized colleagues then independently approve its PO, receive {cap_arrived} kg with 2 rejected and issue all {cap_accepted} accepted kg to the kitchen against that receipt. Open the linked PO and inspect the partial delivery. These colleague actions simulate separate responsibilities, not automatic production approvals.",
            "One demand connects offers, an award, independent order approval, a partial receipt and an evidenced issue. Ordering and approval do not create physical stock. Only accepted goods are available for the later issue.",
            "For 10 kg ordered, 8 kg arrives and 2 kg is rejected: 6 kg is accepted and can be issued. The order still records 8 kg arrived and 2 kg outstanding. The rejected amount is not usable stock.",
            "Choose an offer that meets the actual deadline, preserve the original request and order links, obtain independent approval and use receipt evidence for handover.",
            "Should the cheap eight-day offer win when the supplies are needed in two days? yes or no","no",
            "Check the actual quotation price, timing, notes and linked order. Do not create a second manual order. Reset this capstone after an incorrect award.",("quotation_po_workspace.py","procurement.py","receiving_workspace.py","inventory.py"),busy_steps,10),
        Lesson("cap-restaurant-service","Q","Trace raw ingredients into prepared portions, sales and staff meals",("inventory_manager","owner"),"/production/batches/{batch}","capstone_restaurant",
            "TRAIN-BATCH planned 12 prepared Training Chicken Alfredo portions. Actual preparation used {cap_material} kg raw chicken and yielded {quantity} usable portions with zero rejects. Start and post those actual amounts. A faithful local POS counterpart then records a sale of {cap_sale} portions through approved TRAIN-SERVE, which consumes prepared portions rather than raw chicken again. Finally post Training staff lunch at Training stockroom using 2 of those prepared portions. All three stages remain in this same sandbox and all Accounting handoffs remain local.",
            "Preparation deducts raw ingredients and creates prepared stock at actual unit cost. A serving recipe consumes that prepared stock. Staff meals consume their actual items too. A sale must not deduct the raw ingredients a second time.",
            "2.5 kg at PHP 200 makes 10 portions costing PHP 50 each. Selling 4 prepared portions and using 2 for staff leaves 4 portions. Chicken was deducted once during preparation.",
            "Record actual ingredients and usable yield. Check whether the sale recipe consumes raw or prepared stock, then record staff meals once using the actual consumed item.",
            "Should the sale deduct raw chicken again when preparation already converted it into the mapped prepared portions? yes or no","no",
            "Use the actual raw amount and output, then choose prepared portions in the staff meal. Reset if raw chicken was incorrectly charged a second time.",("production.py","recipe_costing.py","staff_meals.py"),restaurant_steps,10),
        Lesson("cap-housekeeping","U","Prepare rooms and trace the same linen through laundry",("inventory_manager","owner"),"/stock","capstone_housekeeping",
            "Prepare two guest rooms. Issue {quantity} individual guest amenity kits for use, with reason Room preparation. The approved towel standard is 2 per room: hand 4 clean Training bath towels from Training stockroom to Training room floor In use, reference TRAIN-ROOM-ISSUE. Later send 2 used towels from that floor to Training stockroom In laundry, reference TRAIN-LAUNDRY. Only 1 towel is inspected clean: return it at Training stockroom from In laundry to Available / clean, reference TRAIN-CLEAN. Keep all three handovers in this same record.",
            "Amenities are consumed. Towels circulate and remain resort property. A room standard describes a need; only actual handovers change the location and condition balances.",
            "From 12 clean towels, issuing 4 leaves 8 clean and 4 in use. Sending 2 to laundry and returning 1 clean finishes with 9 clean, 2 in use and 1 still in laundry. Total remains 12.",
            "Issue consumables once. Count each reusable handover and retain its location, condition and reference. Do not mark unfinished laundry clean.",
            "Should all laundry be recorded clean when only one towel was accepted? yes or no","no",
            "Check the amenity issue and all three towel references. Correct an unposted form; reset this capstone if a wrong handover was posted.",("inventory.py","property_operations.py"),house_steps,6),
        Lesson("cap-owner-review","X","Follow accountable work through handover and local financial retry",("owner",),"/integrations/operations","capstone_owner",
            "Review the verified Training weekend supplies request. Assign Fictional colleague, accept with notes verified need. A deterministic authorized training colleague will then post its linked {quantity} kg chicken issue. After that evidenced handover, complete the same request with notes handover confirmed. Return to the integrations overview and requeue the separate reviewed failed TRAIN-RETRY Accounting event. All handoffs remain pending locally; no real Staff or Accounting service receives them.",
            "An operational decision accepts responsibility, the linked stock issue proves handover, and Accounting event delivery has a separate lifecycle. Completing follow-up must not issue stock a second time.",
            "Accept, inspect the confirmed linked handover, complete and retain both status messages. Retrying a failed approval event preserves its identity; it does not prove a journal or payment.",
            "Require an accountable person and business evidence before completion. Retry only an eligible reviewed failure and verify final Accounting proof separately.",
            "Does a pending retry prove a General Ledger journal was posted? yes or no","no",
            "Use the same request and its linked issue, then requeue the existing eligible failed event. Do not create another stock issue or claim delivery.",("operational_integrations.py","accounting_integration.py","inventory.py"),owner_steps,5),
        Lesson("cap-monthly-count","G","Close a blind monthly count with independent review",("counter","inventory_manager","owner"),"/counts/{count}","capstone_monthly",
            "In this monthly stocktake you physically find {quantity} kg chicken and {cap_kit_count} individual amenity kits. Enter and save both physical quantities and submit this same session. A deterministic authorized colleague then checks and independently approves the differences. Refresh this count to inspect its final status. The simulated review is a training counterpart action, not automatic approval in real work.",
            "One counting session connects physical entries, submission, independent approval and its stock-adjustment document. A blind counter must never be shown a hidden snapshot to influence their observation.",
            "If you find 21 kg, record 21 kg. A different authorized person reviews any difference and the same count retains the entries, approval and correction history.",
            "Record physical truth, save every line, obtain independent review and check the same session's final result. Do not post a second adjustment for an approved count.",
            "Should you change your physical count just to avoid independent review? yes or no","no",
            "Use the physical quantities in the situation. Save both lines, submit and refresh the same count after the simulated colleague reviews it. Do not enter a separate adjustment.",
            ("guided_counts.py","inventory.py"),
            monthly.steps+(Step('[data-training="count-refresh"]',"Refresh this same count to see the colleague's independent approval and posted status.",event="read",outcome="/counts/training-count/detail"),),21),
        Lesson("cap-delivery-recovery","M","Handle a damaged delivery and a later supplier return",("receiver","owner"),"/receiving","capstone_delivery",
            "TRAIN-PO orders 10 kg chicken. Today {quantity} kg arrives, but 2 kg is damaged and rejected. Post the actual arrival with delivery reference {reference}. After inspection, 1 kg of the accepted chicken fails quality and the supervisor authorizes its return. Return that 1 kg against the same order with reason quality failure. Keep the receipt, rejection, return and remaining order linked in this one practice record.",
            "Rejected goods never enter usable stock. A later return removes previously accepted goods and preserves their original order and receipt evidence. Neither action invents another delivery.",
            "If 8 kg arrives and 2 kg is rejected, usable stock increases by 6 kg. Returning 1 of those accepted kg leaves a net increase of 5 kg. The order records 8 kg arrived, including the rejection, and 1 kg returned.",
            "Record arrived, rejected and later-returned quantities separately. Use the same original order, retain both stock documents and check outstanding quantities through the real order record.",
            "Should a later supplier return be posted as another new receipt? yes or no","no",
            "Post only the actual arrived and rejected quantities, then return 1 kg of previously accepted stock against TRAIN-PO. Reset the capstone if an incorrect transaction was already posted.",
            ("receiving_workspace.py","procurement.py"),delivery.steps+return_steps,8,2),
    ]
