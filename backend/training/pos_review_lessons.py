"""Read genuine local POS-handler results; never offer an Inventory sale button."""
from training.lesson_types import Lesson,Step
ROLES=("viewer","owner")

def read(id,title,situation,concept,example,rule,question,document=False,quantity=2):
    steps=(Step('[data-training-pos-document="TRAIN-SALE-COMPLETED"]',"Open the original sale's stock document and inspect all four ingredient lines.",event="read",outcome="/stock/documents/*"),) if document else ()
    if id=="inspect-unused-sale-void":steps=(Step('[data-training-pos-document="TRAIN-SALE-VOIDED"]',"Open the verified unused-sale correction's reversal document.",event="read",outcome="/stock/documents/*"),)
    return Lesson(id,"S",title,ROLES,"/integrations/pos","read_pos",situation,concept,example,rule,question,"no",rule,("production.py","pos_sync.py","stock_ledger.py"),steps,quantity,global_access=True)

LESSONS=[
 read("sale-consumption","Trace a made-to-order POS sale to four ingredients",
    "A fictional POS counterpart completed {quantity} made-to-order Chicken Alfredo sales locally using the real source handler. Each portion uses 0.1 kg spaghetti, 0.25 kg chicken, 0.05 L cream and 0.05 L house sauce. Nothing was prepared in an earlier batch for this scenario. Open TRAIN-SALE-COMPLETED's stock document and read its signed Net value.",
    "A mapped made-to-order sale consumes the approved raw recipe once at its mapped stock location. The sale document records ingredient quantity and cost; it does not prove Accounting accepted or posted a journal.",
    "At PHP 100/kg spaghetti, 200/kg chicken, 300/L cream and 200/L sauce, one portion costs PHP 85. Two portions consume PHP 170. A prepared-portion workflow instead needs its separate serving recipe.",
    "Verify product, approved recipe, location and all ingredients. Do not deduct raw ingredients again after a prepared batch already consumed them.",
    "Should the raw ingredients be issued a second time after this mapped sale already consumed them? yes or no",True,4),
 read("inspect-pos-duplicate-delivery","Verify that a repeated POS event did not deduct twice",
    "A fictional POS counterpart delivered the same sale event twice with the same identity and quantities. Both calls used the real handler. In POS Synchronization read Processed events, then follow the preserved original document if needed. Do not create a new sale identity to retry the first one.",
    "Idempotency means the same event can be retried without repeating its stock movement. Reusing an event identity with changed business details is a conflict, not a second legitimate sale.",
    "A repeated two-portion sale remains one processed event and one consumption document, with the original ingredient quantities.",
    "Check the original sale and event identity before retrying. A slow response alone is not permission to invent another transaction.",
    "Should the same completed sale be resent under a new sale identity merely because its response was slow? yes or no"),
 read("inspect-unmapped-pos-refusal","Recognize a refused unmapped sale without inventing a failed row",
    "The fictional POS counterpart attempted TRAIN-SALE-UNMAPPED using product TRAIN-UNMAPPED. The actual local handler refused it with 422 before saving a POS row or consuming stock. In POS Synchronization read Failed events. This source screen shows zero, so an empty failure counter does not prove that upstream intake succeeded. Escalate the sale and product references to the integration steward.",
    "This handler can reject an unmapped product before it creates a persistent failed event. Intake diagnostics and source references are needed alongside the workspace; there is no sale-posting button in Inventory.",
    "No mapping means no authorized recipe deduction. Zero displayed failed events can coexist with an actual refused intake.",
    "Preserve the external sale/product references and ask the integration steward to verify and correct the mapping. Check original consumption before any reviewed replay; never manufacture stock or a replacement sale.",
    "Does zero Failed events alone prove that the unmapped sale was successfully processed? yes or no"),
 read("inspect-cooked-sale-return","Review discarded prepared food without restoring raw ingredients",
    "A fictional POS counterpart completed a made-to-order sale of {quantity} portions, then recorded one cooked portion returned with explicit waste disposition through the real local handler. In POS Synchronization read Processed events and check the original sale document. The return has no new stock document: the raw ingredients remain consumed.",
    "A returned cooked meal cannot be reconstructed into usable chicken, cream, pasta and sauce. The source waste return links the original sale without a second stock deduction or ingredient restoration.",
    "A two-portion completed sale and one waste-return event are two processed lifecycle events. They retain only the original recipe consumption document.",
    "Separate financial refunds from physical disposition. The legacy financial refund/void handler reverses ingredients without a physical-disposition gate; do not use it for cooked or discarded meals. Escalate that source limitation to the supervisor and integration steward.",
    "Does returning or refunding cooked food make its raw ingredients usable stock again? yes or no"),
 read("inspect-unused-sale-void","Trace a verified unused-sale correction to its linked reversal",
    "The supervisor verified a mistaken finalization of {quantity} portions before any physical preparation: all ingredients remain unused and present. The fictional POS counterpart recorded the separately authorized void using the real local handler. Open TRAIN-SALE-VOIDED's linked reversal document and read its signed Net value. This correction is not appropriate for cooked, consumed or discarded food.",
    "This legacy handler reverses the original recipe movements. Its physical-disposition gate is an upstream limitation, so the exercise is restricted to a verified unconsumed mistake with supervisor authorization.",
    "A mistaken two-portion sale originally deducts PHP 170, and its linked correction restores PHP 170. Both immutable documents remain; nothing is physically cooked or discarded in this scenario.",
    "Verify unused physical stock and authorization before correction. Preserve original event and reversal links. Money refunded for cooked food is not evidence that ingredients returned.",
    "May this unused-sale correction be used to restore raw ingredients from a cooked meal? yes or no",True),
]
