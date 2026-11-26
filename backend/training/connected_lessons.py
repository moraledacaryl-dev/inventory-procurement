"""Exact local integration decisions; transport and service intake stay disabled."""
from training.lesson_types import Lesson, input_step as fill, select_step as choose, action_step as act


def task(id,module,title,situation,concept,example,rule,question,steps,route="/integrations/operations"):
    return Lesson(id,module,title,("owner",),route,"connected_"+id,situation,concept,example,rule,question,"no",rule+" "+situation,
        ("accounting_integration.py",) if module=="W" else ("operational_integrations.py","shared_master_data.py"),steps,5)


LESSONS=[
    task("accept-accountable-operations-work","X","Accept connected work with an accountable assignee",
        "Training weekend supplies is a valid stock request from the fictional Staff colleague. Accept it and assign Fictional colleague. Record decision notes verified need. This accepts responsibility; it does not issue stock. Every notification and status handoff remains inside this training.",
        "Accepted work needs an accountable person. The canonical identity is the same fictional person used in the request and assignment records.",
        "Accepting a kitchen request lets a colleague follow it up. Supplies still need their own authorized stock or purchasing transaction.",
        "Verify the request and assignee, record the decision and follow the actual supply workflow. A status is not a stock movement.",
        "Does accepting an Operations request itself issue the supplies? yes or no",(
            choose('[aria-label="Assign Training weekend supplies"]',"Assign the active Fictional colleague.","{colleague}"),
            act('[data-training="operations-accepted-training-connected-request"]',"Choose Accept for the verified request."),
            fill('[aria-label="Operational decision notes"]',"Record verified need.","verified need"),
            act('[data-training="confirm"]',"Confirm acceptance and its accountable assignee.","/integrations/operations/requests/training-connected-request/decision"))),
    task("reject-duplicate-operations-work","X","Reject a connected request without inventing a transaction",
        "Training weekend supplies duplicates an existing request and needs no further stock or purchase. Reject this submitted duplicate with notes duplicate demand. Retain its history and the local status handoff.",
        "Rejecting work records the review decision. It does not cancel a separate purchase order or erase a movement from another workflow.",
        "A duplicate reminder should not become a second delivery, issue or purchasing commitment.",
        "Verify the duplicate, explain the rejection and preserve the source identity. Handle separate business records through their own controls.",
        "Does rejecting a reminder automatically reverse a separate stock issue? yes or no",(
            act('[data-training="operations-rejected-training-connected-request"]',"Reject the verified duplicate request."),
            fill('[aria-label="Operational decision notes"]',"Explain duplicate demand.","duplicate demand"),
            act('[data-training="confirm"]',"Confirm the recorded rejection without a stock transaction.","/integrations/operations/requests/training-connected-request/decision"))),
    task("complete-evidenced-operations-work","X","Complete work after its real handover",
        "A colleague already accepted Training weekend supplies and posted its linked issue of {quantity} kg chicken. The handover is confirmed. Mark this accepted request complete with notes handover confirmed. Do not issue the same goods again.",
        "Completion follows the actual work and evidence. A completed status cannot replace a required stock movement.",
        "When the linked issue already deducted 5 kg, completing follow-up must leave stock at that same quantity, not deduct another 5 kg.",
        "Check the handover and linked evidence, complete the follow-up and keep the original stock transaction intact.",
        "Should supplies already issued be deducted again when completing follow-up? yes or no",(
            act('[data-training="operations-completed-training-connected-request"]',"Complete the accepted request after checking its confirmed handover."),
            fill('[aria-label="Operational decision notes"]',"Record handover confirmed.","handover confirmed"),
            act('[data-training="confirm"]',"Confirm completion while preserving the existing issue.","/integrations/operations/requests/training-connected-request/decision"))),
    task("requeue-failed-accounting-handoff","W","Retry a failed handoff without claiming a posted journal",
        "The fictional TRAIN-RETRY Accounting event failed because its receiver was temporarily unavailable. The underlying approved order is valid and no accepted Accounting receipt exists. Requeue the same event after the issue has been reviewed. It must remain pending locally; no Accounting service is connected.",
        "Requeue resets an eligible failed event for another delivery attempt. It does not create a second order, mark delivery complete or verify a journal.",
        "A pending PHP 1,000 order-approval event still needs delivery and Accounting review. Requeue does not add PHP 1,000 of stock or prove a payment.",
        "Check the failure and source event before retrying. Keep its identity, amount and idempotency key; verify final Accounting evidence separately.",
        "Does requeueing prove that Accounting posted a General Ledger journal? yes or no",(
            act('[data-training="accounting-requeue-training-retry"]',"Requeue the reviewed failed TRAIN-RETRY event once.","/integrations/accounting/events/training-retry/requeue"),),route="/integrations/accounting"),
]
