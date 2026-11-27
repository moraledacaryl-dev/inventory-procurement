"""Exercises for the deployed operational safeguards."""
from training.lesson_types import Lesson, Step, input_step as fill, select_step as choose, action_step as act


def task(id,module,title,roles,route,situation,concept,example,rule,steps,sources):
    return Lesson(id,module,title,roles,route,"safety_"+id,situation,concept,example,rule,
        "May you change or invent stock or accepted financial evidence to bypass this control? yes or no",
        "no",rule,sources,steps,global_access=module=="W")


LESSONS=[
    task("staff-meal-reserved-stock","T","Protect ingredients reserved for another job",("inventory_manager","owner"),"/fnb/staff-meals",
        "Training stockroom physically has {base} kg chicken, including 4 kg reserved for another job. The proposed four-person meal needs {meal_reserved_need} kg: physical stock is enough, but unreserved availability is short by 1 kg. Nothing has been cooked. Preview and, in this isolated exercise, verify that posting is also refused. Ask the supervisor to revise the plan or use the authorized reservation process.",
        "Physical stock and available stock differ. Preview subtracts active, unexpired reservations; posting checks them again while holding the stock locks. A preview is not a reservation.",
        "24 kg physically present minus 4 kg reserved leaves 20 kg available. A proposed 21 kg requirement must be refused without consuming another job's supplies.",
        "Preserve the reservation and physical stock. Never invent a receipt or remove a reservation merely to force a meal through.",(
            fill('[data-training="meal-name"]',"Name the proposed meal Training reserved-stock check.","Training reserved-stock check"),
            choose('[data-training="meal-location"]',"Check Training stockroom.","{store}"),
            fill('[data-training="meal-servings"]',"The proposed meal is for four people.","4"),
            choose('#ingredient-0',"Select Chicken (kg).","{chicken}"),
            fill('#quantity-0',"Enter {meal_reserved_need} kg; no ingredients have been used.","{meal_reserved_need}"),
            act('[data-training="meal-preview"]',"Read the unreserved-stock refusal.","/staff-meals/preview",409),
            act('[data-training="meal-post"]',"Verify posting also preserves the reserved ingredients.","/staff-meals",409)),("staff_meals.py",)),
]

for id,title,route,target,endpoint,accepted in [
    ("retry-reviewed-outbound-event","Requeue one eligible outbound delivery","/integrations","integration-retry-training-safety-event","/integration-events/training-safety-event/retry",False),
    ("refuse-accepted-accounting-generic","Protect accepted Accounting evidence in generic Retry","/integrations","integration-retry-training-safety-event","/integration-events/training-safety-event/retry",True),
    ("refuse-accepted-accounting-dedicated","Protect accepted evidence in Accounting Requeue","/integrations/accounting","accounting-requeue-training-safety-event","/integrations/accounting/events/training-safety-event/requeue",True),
]:
    LESSONS.append(task(id,"W",title,("owner",),route,
        "TRAIN-SAFETY is a historical delivery marked Failed even though its attached Accounting receipt says accepted. In this isolated exercise attempt the displayed retry and read the refusal. Preserve the accepted receipt, source amount and identity; ask the Accounting reviewer to reconcile the existing evidence." if accepted else
        "TRAIN-SAFETY is an outbound Operations alert that failed during a temporary receiver outage. The steward verified the original event and eligible failure. Retry that same event once. It becomes Pending locally, preserving its original payload and identity. No worker or external delivery runs.",
        "Both retry routes permit only eligible failed/dead-letter outbound events. Accounting retries also require integration administration permission and protect delivered, accepted or posted evidence.",
        "A Failed label cannot override an accepted Accounting receipt. Refusal preserves the original obligation." if accepted else "Retry changes delivery state, not the source stock transaction or original event identity.",
        "Check direction, status, authority and attached delivery evidence. Pending is not proof of a journal, payment or completed delivery.",
        (act('[data-training="'+target+'"]',"Read the protected refusal and keep the original accepted evidence." if accepted else "Requeue only the reviewed failed outbound TRAIN-SAFETY event.",endpoint,409 if accepted else None),),
        ("operations.py","accounting_integration.py")))
