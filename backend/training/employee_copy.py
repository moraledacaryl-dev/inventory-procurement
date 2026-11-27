"""Employee wording; lesson bindings, answers and business checks stay unchanged."""
from dataclasses import replace
import re

COPY_VERSION = "2026.11.27.3"

# Keep implementation and verification notes in the lesson definitions, not in
# the employee's instructions. Braced values are filled by the existing engine.
COPY = {
    "define-unit-conversion": {"feedback": "Check the assigned direction: {conversion_description}."},
    "count-multiple-units": {"feedback": "Record chicken in kg and amenities as individual kits, not boxes."},
    "create-governed-recipe": {"feedback": "Use 0.25 kg of chicken per portion, with waste factor 0.1."},
    "award-timely-quotation": {"feedback": "Supplies are needed within two days. Check delivery time as well as price."},
    "send-used-linen-to-laundry": {"feedback": "Move used towels to In laundry. They are not Available / clean yet."},
    "recipe-cost": {"rule": "Check ingredient units and the number of portions before approving a recipe."},
    "accounting-proof": {
        "situation": "A delivery is marked Delivered. Check its Accounting review status and whether a matching journal was posted.",
        "rule": "Delivered does not mean posted. Check the Accounting review and matching journal before taking further action.",
        "correction": "Check the Accounting review status and matching journal."},
    "staff-meal-shortage": {
        "concept": "A meal cannot use unavailable ingredients. Preview the quantities and cost before posting.",
        "situation": "The proposed staff meal needs {meal_shortage} kg of chicken, but Training stockroom has only {base} kg. Nothing has been cooked. Preview it, then try posting it for this practice. Both actions should be refused.",
        "rule": "Ask the supervisor to revise the meal or arrange more supplies before cooking."},
    "accept-accountable-operations-work": {"concept": "Accepted work needs a named person responsible for completing it.",
        "feedback": "Assign Fictional colleague and record notes verified need. Accepting the request does not issue supplies."},
    "connected-work": {"rule": "Check the original record and its status in the appropriate app. A notification does not replace a stock movement or approval."},
    "cap-owner-review": {"title": "Follow a supply request through handover and Accounting review",
        "situation": "Assign Fictional colleague to Training weekend supplies and accept it with notes verified need. A {quantity} kg chicken handover is provided for this practice. Complete the request with notes handover confirmed. Then open Accounting and requeue the reviewed failed TRAIN-RETRY record."},
    "reject-duplicate-operations-work": {"rule": "Check the duplicate, record why it was rejected and keep its history."},
    "requeue-failed-accounting-handoff": {
        "situation": "TRAIN-RETRY failed while Accounting was unavailable. The order is approved and Accounting has not accepted the delivery. After the issue has been reviewed, requeue the same record.",
        "rule": "Retry the original record. Keep its amount and reference, and check the Accounting result afterward."},
    "cap-busy-weekend": {
        "title": "Order weekend supplies and follow the delivery",
        "situation": "TRAIN-REQUEST needs {quantity} kg of chicken within two days. Training Budget Foods offers PHP 200/kg in 8 days. Enter Training Valley Foods' PHP 220/kg offer with 1 delivery day, {terms} payment days and Notes {reference}; leave expiry blank. Award it to Training stockroom. For this practice, colleagues provide PO approval, receive {cap_arrived} kg with 2 kg rejected, and issue the {cap_accepted} accepted kg to the kitchen. Open the linked PO and check what is still outstanding."},
    "cap-restaurant-service": {
        "situation": "TRAIN-BATCH planned 12 Chicken Alfredo portions. Record {cap_material} kg of chicken used and {quantity} usable portions, with no rejects. A practice POS sale then uses {cap_sale} prepared portions. Record Training staff lunch using 2 prepared portions at Training stockroom. Do not deduct the raw chicken again."},
    "cap-monthly-count": {
        "situation": "You count {quantity} kg of chicken and {cap_kit_count} amenity kits. Save both quantities and submit the count. A separate review is provided for this practice. Refresh the same count and check its final status."},
    "run-isolated-acceptance": {
        "situation": "Run acceptance checks and review the results. No completed backup is recorded, so the backup check should fail.",
        "rule": "Keep failed checks visible and report them. Do not mark a backup complete unless it was completed and verified."},
    "retry-eligible-inbound-event": {
        "title": "Check why a POS record cannot use Retry",
        "situation": "TRAIN-POS-RETRY came from POS. For this practice, select Retry and read the refusal. Keep the record unchanged and ask the integration reviewer to arrange a retry from POS using the original sale reference.",
        "concept": "Retry here sends failed messages to other apps. It cannot replay a sale received from POS.",
        "example": "Fixing a product mapping does not record the original sale. Check whether it was already recorded before arranging a retry.",
        "rule": "Use the original sale reference and the correct retry process. Never record the same sale twice."},
    "interpret-assurance-evidence": {
        "situation": "Open Final assurance. The stock totals match, but no completed backup is recorded. Read the backup check's Status without recording another review.",
        "rule": "Matching stock totals do not prove that a backup is ready to restore."},
    "sale-consumption": {
        "situation": "POS recorded {quantity} made-to-order Chicken Alfredo sales. Each portion uses 0.1 kg spaghetti, 0.25 kg chicken, 0.05 L cream and 0.05 L sauce. These portions were not prepared in an earlier batch. Open TRAIN-SALE-COMPLETED's stock document and read its signed Net value.",
        "concept": "A mapped sale deducts its recipe ingredients once at the assigned location.",
        "rule": "Check the product, recipe and stock location. Do not deduct ingredients again after they have already been used."},
    "inspect-pos-duplicate-delivery": {
        "title": "Check that a repeated sale deducted stock only once",
        "situation": "POS sent the same sale twice. In POS Synchronization, read Processed events and check the original stock document. Do not create another sale reference.",
        "concept": "Sending the same sale again must not deduct stock twice.",
        "example": "A repeated two-portion sale keeps one sale record and one ingredient deduction.",
        "rule": "Find the original sale before retrying. A slow response is not a reason to create another sale."},
    "inspect-unmapped-pos-refusal": {
        "title": "Check a sale with a missing product mapping",
        "situation": "TRAIN-SALE-UNMAPPED could not be recorded because TRAIN-UNMAPPED has no recipe mapping. No ingredients were deducted. Read Failed events in POS Synchronization, then report the sale and product references to the integration reviewer.",
        "concept": "A missing mapping can stop a sale before it appears in the failure list. Zero Failed events does not prove that every sale was recorded.",
        "rule": "Check the original sale and product mapping. Ask for a reviewed retry; do not invent stock or record the sale twice."},
    "inspect-cooked-sale-return": {
        "situation": "POS recorded {quantity} cooked meals, a refund, and one returned meal marked as waste. Read Processed events and inspect the original stock document. The ingredients remain used.",
        "concept": "A refund or discarded cooked meal does not return raw ingredients to stock.",
        "example": "The sale, refund and waste return are three records. Only the original sale deducts the ingredients.",
        "rule": "Keep the ingredients consumed. Record the refund and physical waste separately."},
    "inspect-unused-sale-void": {
        "title": "Check stock after a sale is voided",
        "situation": "A sale of {quantity} portions was finalized before preparation. The supervisor confirms the ingredients were not used. Open TRAIN-SALE-COMPLETED and read its signed Net value. TRAIN-SALE-VOIDED does not change that stock document. Ask the inventory supervisor to arrange the stock correction separately.",
        "concept": "Voiding a sale does not restore ingredients. Stock corrections require a physical check and approval.",
        "example": "A two-portion sale deducts PHP 170. Voiding it leaves that deduction in place until an approved stock correction is recorded.",
        "rule": "Check the physical stock and original sale. Get approval for a separate correction when ingredients were not used."},
    "retry-reviewed-outbound-event": {
        "title": "Retry a reviewed failed delivery",
        "situation": "TRAIN-SAFETY is a failed Operations alert. The delivery issue has been reviewed. Retry the same record once and check that its status becomes Pending.",
        "concept": "Retry sends the same failed message again. It does not create another stock transaction.",
        "example": "The record keeps its original reference and details when it returns to Pending.",
        "rule": "Retry only the reviewed failed record. Check the delivery result afterward."},
    "refuse-accepted-accounting-generic": {
        "title": "Protect an accepted Accounting record in Retry"},
    "refuse-accepted-accounting-dedicated": {
        "title": "Protect an accepted Accounting record in Requeue"},
    "staff-meal-reserved-stock": {
        "situation": "Training stockroom has {base} kg of chicken, with 4 kg reserved for another job. The proposed meal needs {meal_reserved_need} kg, so available stock is short by 1 kg. Enter Training reserved-stock check for four servings. Preview it, then try posting it for this practice. Both actions should be refused.",
        "concept": "Reserved ingredients belong to another job. Check available stock before preparing a staff meal.",
        "rule": "Keep the reservation intact. Ask the supervisor to revise the meal or arrange more supplies."},
    "create-operating-department": {
        "concept": "Departments identify who is responsible for the work. Use the approved department code and name.",
        "rule": "Check for an existing department before adding one. Keep the existing behavior settings."},
    "record-assurance-review": {
        "situation": "Review the assurance report, then Record snapshot. Stock totals should match, but no completed backup is recorded. Keep the failed checks visible; do not mark the review ready."},
}
for key in ("refuse-accepted-accounting-generic", "refuse-accepted-accounting-dedicated"):
    COPY[key].update(
        situation="TRAIN-SAFETY is marked Failed, but its Accounting receipt says Accepted. For this practice, try the displayed retry and read the refusal. Keep the accepted record unchanged and ask Accounting to check the conflicting status.",
        concept="An accepted Accounting receipt must not be sent again just because another status says Failed.",
        example="The retry is refused and the accepted receipt stays unchanged.",
        rule="Keep the original amount, reference and accepted receipt. Ask Accounting to resolve the conflicting status.")

REPLACEMENTS = (
    ("Your approved global asset assignment covers this workspace. ", ""),
    ("All handoff records in this training stay local.", ""),
    ("Every notification and status handoff remains inside this training.", ""),
    ("No live POS system is connected in this training.", ""),
    ("No live POS is connected here.", ""),
    ("Accounting delivery is disabled in this training.", ""),
    ("; the training handoff stays local", ""),
    ("a local Accounting handoff", "an Accounting delivery record"),
    ("local pending handoff", "pending delivery record"),
    ("original local POS evidence", "original POS records"),
    ("Both Accounting handoffs remain pending locally", "Both Accounting deliveries remain Pending"),
    ("pending locally", "Pending"),
    ("fictional internal scan code", "scan code"),
    ("fictional scan code", "scan code"),
    ("fictional supplier", "supplier"),
    ("fictional email", "email"),
    ("fictional POS product", "POS product"),
    ("fictional Staff colleague", "Staff colleague"),
    ("fictional independent reviewer and receiving colleague", "practice reviewer and receiving colleague"),
    ("fictional Accounting reviewer", "Accounting reviewer"),
    ("fictional kitchen colleague", "kitchen colleague"),
    ("fictional colleague", "colleague"),
    ("fictional counter", "counter"),
    ("fictional contact", "contact"),
    ("fictional practice CSV deliberately repeats", "practice CSV repeats"),
    ("fictional file", "practice file"),
    ("in this fictional practice", "for this practice"),
    ("in this isolated shortage exercise", "for this practice"),
    ("in the isolated exercise", "for this practice"),
    ("In this isolated check,", "For this practice,"),
    ("through the real order record", "in the original order"),
    ("after its real handover", "after the supplies are handed over"),
    ("Check the real saved record", "Check the saved record"),
    ("local responsibilities", "responsibilities for that location"),
    ("The source blocks self-approval.", "You cannot approve your own work."),
    ("The source applies this rule even to an owner.", "This rule also applies to owners."),
    ("Training menu names are fictional fixtures.", ""),
    ("Training events stay in this sandbox.", ""),
    ("The canonical identity", "The assigned person"),
    ("canonical SKU", "item code"),
    ("canonical identity", "assigned person"),
    ("source-linked", "matching"),
    ("source documents", "original documents"),
    ("source transactions", "original transactions"),
    ("source order", "original order"),
    ("source identity", "original reference"),
    ("source event", "original record"),
    ("source production document", "production record"),
    ("source file", "original file"),
    ("original/reversal links", "original and correction records"),
    ("real source", "Inventory"),
    ("real local handler", "Inventory"),
    ("actual local handler", "Inventory"),
    ("real handler", "Inventory"),
    ("source handler", "Inventory"),
    ("local status handoff", "status history"),
    ("local handoff", "delivery record"),
    ("actual source", "Inventory"),
    ("In this isolated practice,", "For this practice,"),
    ("In this isolated exercise,", "For this practice,"),
    ("in this isolated exercise", "for this practice"),
    ("in this isolated check", "for this practice"),
    ("the real refusal", "the refusal"),
    ("actual shortage refusal", "shortage message"),
    ("idempotency key", "original reference"),
    ("payload", "details"),
    ("synthetic", "practice"),
    ("backend", "system"),
    ("under the shared stock locks", "when you post"),
    ("under the stock locks", "when you post"),
)


def employee_text(text):
    for original,replacement in REPLACEMENTS:
        text=text.replace(original,replacement)
    text=re.sub(r"\b(?:actual|real) (?:409|422) refusal\b", "refusal", text)
    text=re.sub(r"\b(?:HTTP )?(?:409|422) (?:response|refusal|error)\b", "message", text)
    text=re.sub(r"\s+", " ", text).strip()
    return text


def employee_lesson(lesson):
    fields={key:employee_text(COPY.get(lesson.id,{}).get(key,getattr(lesson,key)))
            for key in ("title","situation","concept","example","rule","question")}
    correction=COPY.get(lesson.id,{}).get("rule",lesson.correction)
    if lesson.situation and correction.endswith(lesson.situation):
        correction=correction[:-len(lesson.situation)].strip()
    fields["correction"]=employee_text(COPY.get(lesson.id,{}).get("correction",correction))
    fields["steps"]=tuple(replace(step,instruction=employee_text(step.instruction)) for step in lesson.steps)
    return replace(lesson,**fields)


def employee_feedback(text, lesson, values):
    """Keep the specific correction without repeating the complete task."""
    situation=lesson.situation.format(**values)
    if situation and text.startswith(situation):
        reminder=COPY.get(lesson.id,{}).get("feedback",lesson.rule).format(**values)
        text=reminder+" "+text[len(situation):].strip()
    return employee_text(text)
