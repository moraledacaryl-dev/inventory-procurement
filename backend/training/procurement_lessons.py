"""Independent purchasing controls and commercial decisions on real records."""
from training.lesson_types import Lesson, input_step as fill, select_step as choose, action_step as act

BUY=("procurement_officer","owner")
QUEUE="/purchasing?view=requisitions"
SOURCE="/purchasing?view=source"
ORDER="/purchasing/orders/{po}"


def task(id,module,title,situation,concept,example,rule,question,steps=(),roles=BUY,route=QUEUE,read=False):
    return Lesson(id,module,title,roles,route,"read_procurement" if read else "procurement_"+id,
        situation,concept,example,rule,question,"no",rule+" "+situation,
        ("procurement.py","quotation_po_workspace.py"),steps,5)


LESSONS=[
    task("approve-purchase-request","J","Review and approve another person's request",
        "A colleague requested {quantity} kg of chicken under TRAIN-REQUEST for Training stockroom. You checked the documented need, available stock, reservations and open orders. The additional purchase is justified and within your approval limit. Approve this request.",
        "Request approval accepts the need to buy. It does not receive goods, choose a supplier or approve a purchase order.",
        "Approving a request for 5 kg leaves physical stock unchanged. Purchasing still needs supplier offers and an independently approved order.",
        "Check demand and existing commitments before approving another person's request. Keep request approval separate from order approval.",
        "Does approving a request prove the goods arrived? yes or no",
        (act('[data-training="request-approve-training-requisition"]',"Review TRAIN-REQUEST and approve the justified need.","/requisitions/training-requisition/approve"),)),
    task("reject-duplicate-request","J","Reject an unnecessary purchase request",
        "TRAIN-REQUEST repeats supplies already covered by an approved order. You verified that no extra purchase is needed. Reject this submitted duplicate; keep the existing order and stock unchanged.",
        "A rejected request remains part of the history. Rejection stops this demand from becoming another purchase.",
        "Two requests for the same weekend delivery do not mean the resort needs twice the supplies.",
        "Check the real need and existing orders. Tell the requester why the duplicate was rejected; this screen has no separate rejection-reason field.",
        "Should a duplicate request be approved just because it is in the queue? yes or no",
        (act('[data-training="request-reject-training-requisition"]',"Reject the verified duplicate TRAIN-REQUEST.","/requisitions/training-requisition/reject"),)),
    task("request-self-approval","J","Recognize independent request approval",
        "You submitted TRAIN-REQUEST yourself. In this isolated exercise, try approving it and read the refusal. Leave it submitted for a different authorized approver.",
        "The person requesting a purchase cannot independently check their own request. The source applies this rule even to an owner.",
        "An urgent kitchen need still needs another authorized person to review it.",
        "Ask another authorized approver. Do not change the requester or use another person's account.",
        "Can you independently approve your own purchase request? yes or no",
        (act('[data-training="request-approve-training-requisition"]',"Try approval and read the independent-review refusal.","/requisitions/training-requisition/approve",409),)),
    task("record-supplier-quotation","K","Record a supplier's actual offer",
        "TRAIN-REQUEST is approved for {quantity} kg chicken. Training Valley Foods offers PHP 220 per kg, delivery in 1 day and payment in {terms} days. Record this offer with Notes {reference}. The supplier gave no expiry date, so leave Valid until blank.",
        "A quotation is a supplier's offer. Recording it creates neither usable stock nor an approved supplier commitment.",
        "Five kg at PHP 220 costs PHP 1,100. One delivery day and 14 payment days describe different parts of the offer.",
        "Copy the actual price, delivery and payment terms. Compare offers before awarding, then obtain separate PO approval.",
        "Does saving a quotation approve a purchase order? yes or no",(
            act('[data-training="quote-record-training-requisition"]',"Open Record quotation for TRAIN-REQUEST."),
            choose('[data-training="quote-supplier"]',"Choose Training Valley Foods.",'{supplier}'),
            fill('[data-training="quote-delivery-days"]',"The supplier can deliver in 1 day.","1"),
            fill('[data-training="quote-payment-days"]',"Enter {terms} payment days.","{terms}"),
            fill('[aria-label="Quotation price for Chicken (kg)"]',"Enter PHP 220 per kg, not the total.","220"),
            fill('[data-training="quote-notes"]',"Enter the offer reference {reference}.","{reference}"),
            act('[data-training="quote-save"]',"Save the actual offer; leave its unspecified expiry blank.","/quotations")),route=SOURCE),
    task("award-timely-quotation","K","Compare price with the required delivery time",
        "The approved request needs {quantity} kg within two days. Training Budget Foods offers PHP 200/kg in 8 days; Training Valley Foods offers PHP 220/kg in 1 day. Both cover the same quantity. Award the offer that meets the deadline, for delivery to Training stockroom. Keep the new PO as a draft for independent approval.",
        "The lowest total may arrive too late. Compare the quantity, price, delivery time and payment terms against the actual need.",
        "For 5 kg, saving PHP 100 is not useful when an 8-day delivery misses an event in two days. A one-day offer at PHP 1,100 meets that deadline.",
        "Choose a justified offer and verify the destination. Awarding creates a linked draft PO; it does not approve, receive or pay it.",
        "Must the lowest-priced offer always win when it misses the required delivery? yes or no",(
            act('[data-training="quote-award-training-quote-fast"]',"Compare both offers and award the one-day Training Valley Foods offer."),
            choose('[data-training="award-location"]',"Check Training stockroom as the delivery location.",'{store}'),
            act('[data-training="confirm"]',"Create one linked draft PO for independent approval.","/requisitions/training-requisition/award-quotation")),route=SOURCE),
    task("inspect-awarded-order","K","Find the order already created from an offer",
        "TRAIN-FAST has already been awarded once. Inspect its linked TRAIN-PO. Report the actual order status, and leave the existing order unchanged.",
        "The awarded offer links to its existing purchase order. The disabled Award control prevents treating that offer as a new purchase.",
        "If TRAIN-FAST already created a draft, open that draft rather than creating an unrelated manual order for the same demand.",
        "Follow the existing order and its approval status. Never duplicate the purchase to get past an awarded offer.",
        "Should an already awarded offer be copied into a duplicate order? yes or no",route=SOURCE,read=True),
    task("purchase-approval-limit","L","Recognize an approval above your limit",
        "A colleague's TRAIN-PO is a draft for {quantity} kg at PHP 200/kg. Your assigned approval limit is PHP 100. Try approving the order in this isolated exercise and read the refusal. Leave the draft for a properly authorized approver.",
        "Permission to open an order is different from authority to approve its monetary value.",
        "A PHP 1,000 order exceeds a PHP 100 approval limit even though its item and location are correct.",
        "Ask an approver with the required authority. Do not split or reduce a real purchase to evade the limit.",
        "Should you split an order only to bypass your approval limit? yes or no",(
            act('[data-training="po-approve"]',"Review the total and try Approve PO."),
            act('[data-training="confirm"]',"Read the approval-limit refusal and keep the order as a draft.","/purchase-orders/training-po/approve",403)),roles=("procurement_officer",),route=ORDER),
    task("amend-draft-order","L","Correct a draft before independent approval",
        "The supplier confirmed that TRAIN-PO should contain {quantity} kg chicken at PHP 220/kg. The order is still a draft. Correct its quantity and price, set Notes to {reference}, and save the amendment without approving it.",
        "A draft can be amended before approval. The audit records the change; the order still needs independent approval after its final terms are checked.",
        "Correcting 10 kg at PHP 200 to 5 kg at PHP 220 changes the draft total from PHP 2,000 to PHP 1,100 and does not change stock.",
        "Check the final quantity, price and notes. Amend only an eligible draft and preserve the independent approval step.",
        "Does saving an amendment independently approve the order? yes or no",(
            fill('[aria-label="Order quantity for Chicken (kg)"]',"Correct the draft to {quantity} kg.","{quantity}"),
            fill('[aria-label="Order unit price for Chicken (kg)"]',"Correct the unit price to PHP 220/kg.","220"),
            fill('[data-training="po-amend-notes"]',"Record the amendment reference {reference}.","{reference}"),
            act('[data-training="po-amend-save"]',"Save the corrected draft for later independent approval.","/purchase-orders/training-po/amend")),route=ORDER),
    task("cancel-unreceived-order","L","Cancel an order before any receipt",
        "TRAIN-PO was approved, but the event was cancelled and no goods have been received. The authorized cancellation has been confirmed. Cancel the order while retaining its history. All handoff records in this training stay local.",
        "Pre-receipt cancellation stops an eligible order. It is not a supplier return and does not remove stock that was never received.",
        "Cancelling an unreceived 10 kg order leaves stock unchanged and records a cancellation handoff for Accounting.",
        "Verify that no receipts exist and that the cancellation is authorized. Retain the record and check the cancellation status.",
        "Does cancelling an unreceived order physically issue stock? yes or no",(
            act('[data-training="po-cancel"]',"Choose Cancel PO after checking that received quantity is zero."),
            act('[data-training="confirm"]',"Confirm the authorized cancellation; keep its history.","/purchase-orders/training-po/cancel-workspace")),route=ORDER),
    task("inspect-approved-order-lock","L","Recognize that an approved order is controlled",
        "TRAIN-PO is already approved. Inspect its status and control statement. Its draft-amendment form is no longer available. Report the status and ask the authorized purchaser to handle any commercial change.",
        "Approval fixes the commercial terms. The screen removes draft editing controls once the order is approved.",
        "An approved 10 kg order cannot silently become 5 kg by changing a draft input.",
        "Keep the approved evidence. Use the authorized follow-on process instead of making an unrelated stock adjustment.",
        "Can an approved order be silently edited as a draft? yes or no",route=ORDER,read=True),
    task("inspect-received-order-lock","L","Recognize that receipts prevent cancellation",
        "A colleague already received all {quantity} kg against TRAIN-PO. Inspect its actual received quantity and controls. The order cannot now use pre-receipt cancellation. Report how many kg the order records as received.",
        "Received goods have stock and obligation evidence. Cancelling an order is not a way to undo that receipt.",
        "If 5 kg was received, a supplier return must reference the received goods and its authorized reason. Deleting demand does not physically send them back.",
        "Use the authorized supplier-return or correction workflow for received goods. Preserve the linked receipt history.",
        "Should pre-receipt cancellation be used to undo goods already received? yes or no",route=ORDER,read=True),
]
