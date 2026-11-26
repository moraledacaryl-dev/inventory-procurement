"""Versioned exam blueprints and explicit scoring, separate from HTTP/storage.

A final combines a knowledge check with new source-backed independent attempts.
Public blueprints deliberately omit answer keys; completed grading retains the
specific questions/objectives to revisit rather than a generic failure label.
"""
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from training.curriculum import BY_ID, VERSION
from training.paths import BY_PATH

ASSESSMENT_VERSION="2026.11.26.3"


@dataclass(frozen=True)
class Question:
    id: str
    prompt: str
    answer: str
    correction: str
    critical: bool = False


def q(id,prompt,answer,correction,critical=False):return Question(id,prompt,str(answer),correction,critical)


FOUNDATION=(
    q("available","There are 24 kg physically present and 4 kg reserved. How many kg are available for another job?",20,"Available stock is physical stock less active reservations: 24 − 4 = 20 kg."),
    q("unit","A recipe line uses kg. How many kg is 250 g?","0.25","1,000 g is 1 kg, so 250 g is 0.25 kg.",True),
    q("value","Five units cost PHP 100 each. What is the total cost in pesos?",500,"Multiply quantity by the unit cost: 5 × PHP 100 = PHP 500."),
    q("authority","Does passing this training grant production permissions? yes or no","no","Production permissions, locations and approval limits require separate authorization.",True),
)
# Three contextual questions per module; common units/availability/authority
# remain relevant across all hospitality work. These are not the practical exam.
TOPICS={
 "A":(("physical","Does reserving 4 kg physically consume it? yes or no","no","Reservation reduces availability; consumption needs an actual movement."),("movement","Should a real supply handover be recorded? yes or no","yes","A handover changes custody and must have an accurate movement."),("shortage","Available stock is 3 kg and the task needs 5 kg. How many kg is the shortage?",2,"The unmet requirement is 5 − 3 = 2 kg.")),
 "B":(("restricted","Should you use a colleague's sign-in to open a restricted screen? yes or no","no","Ask the authorized colleague; do not use their identity."),("location","Should a report's location and date filters be checked before using its totals? yes or no","yes","A different location or period can explain a different total."),("history","Should an existing posted transaction be found before repeating a slow submission? yes or no","yes","Check the saved record before risking a duplicate.")),
 "C":(("case","One case contains 24 cans. How many individual cans are in 3 cases?",72,"3 × 24 = 72 cans; confirm the item's configured base unit."),("conversion","Should 250 g be entered as 250 on a kg line? yes or no","no","Convert to 0.25 kg before entering it."),("deactivate","Should an item with stock be deleted to hide that stock? yes or no","no","Preserve stock and history; use the authorized lifecycle controls.")),
 "D":(("opening","Does an opening receipt increase physical stock? yes or no","yes","An actual opening receipt adds its accepted opening quantity."),("cost","Should unit cost contain the full line total? yes or no","no","Unit cost is the price for one base unit."),("duplicate","Should the same opening balance be posted twice? yes or no","no","Check the original posted record; a second receipt invents stock.")),
 "E":(("issue","There are 12 kg before an actual 5 kg issue. How many kg remain?",7,"12 − 5 = 7 kg remain."),("destination","Should the correct item and storage location be checked before posting? yes or no","yes","An issue must deduct the item from the location that actually supplied it."),("reservation","Does a reservation replace the later actual issue? yes or no","no","The actual issue still needs its own stock movement.")),
 "F":(("transit","Does dispatch alone prove the destination accepted the goods? yes or no","no","Goods can still be in transit; record actual destination receipt."),("variance","Dispatch was 8 units but only 7 were accepted at destination. How many units differ?",1,"8 − 7 = 1 unit needs documented follow-up."),("scope","Can a location-scoped employee bypass an unauthorized transit location? yes or no","no","Ask the properly authorized colleague; do not change custody to evade a scope.")),
 "G":(("truth","You physically count 8 bottles while a colleague says the system has 10. What physical quantity must you enter?",8,"Enter the 8 bottles actually observed."),("zero","Is a blank physical count the same as a counted zero? yes or no","no","Zero means counted and none found; blank means unfinished."),("approval","Can the creator independently approve their own count difference? yes or no","no","A different authorized person must independently review it.")),
 "H":(("waste","Does recording discarded food reduce usable stock? yes or no","yes","Discarded stock leaves usable inventory."),("correction","Should a stock adjustment be used to conceal a supplier return? yes or no","no","Use the source-linked return or authorized correction process."),("signed","A verified opening correction removes 3 units. Is its signed quantity change -3 or 3?","-3","A removal is a negative quantity change.")),
 "I":(("terms","Payment terms of 14 days describe the delivery lead time. yes or no","no","Payment timing and delivery lead time describe different obligations."),("preferred","Does linking a preferred supplier create a purchase order? yes or no","no","A supplier link is configuration, not a commercial order."),("orders","Should a supplier with active open orders be silently deleted? yes or no","no","Preserve existing commercial obligations and history.")),
 "J":(("request","Does approving a purchase request prove goods arrived? yes or no","no","Approval accepts the need; receiving is separate."),("duplicate","Should existing approved orders be checked before requesting the same demand? yes or no","yes","Check supply already on order to avoid duplicates."),("independent","May a requester independently approve their own requisition? yes or no","no","Another authorized person must approve.")),
 "K":(("deadline","Supplies are needed in two days. One offer delivers in 1 day and another in 8 days. Which delivery time meets the need?",1,"The one-day offer meets the two-day deadline."),("award","Does awarding a quotation physically receive the order? yes or no","no","Awarding creates a linked draft order; approval and receipt are separate."),("linked","Should an already awarded offer be copied into a second manual order? yes or no","no","Follow the existing linked order and avoid duplicate commitments.")),
 "L":(("limit","Your approval limit is PHP 100. May you approve PHP 1,000 by splitting it to evade that limit? yes or no","no","Ask an authorized approver; do not evade monetary limits."),("draft","Can an approved order be silently changed through a draft amendment? yes or no","no","Approval fixes terms; use the controlled follow-on process."),("receipt","Should pre-receipt cancellation undo goods already received? yes or no","no","Preserve receipts and use an authorized return or correction.")),
 "M":(("accepted","Eight kg arrived and 2 kg is rejected. How many kg enter usable stock?",6,"Arrived less rejected is accepted: 8 − 2 = 6 kg."),("arrived","The order was 10 kg but only 8 kg arrived. What arrived quantity must be entered?",8,"Record the actual 8 kg, not the ordered amount."),("rejection","Does the current application count rejected arrived goods toward PO received quantity? yes or no","yes","PO fulfillment counts arrived goods including rejections; only accepted goods enter stock.")),
 "N":(("return","Should a later supplier return reference the original order? yes or no","yes","Retain the source order and accepted-stock evidence."),("usable","Six kg was accepted and 1 kg is later returned. What net kg remains from this delivery?",5,"6 accepted − 1 returned = 5 kg net."),("new","Is a supplier return another new receipt? yes or no","no","A return removes previously accepted stock.")),
 "O":(("expiry","Should expired stock be issued as usable food? yes or no","no","Inspect expiry and follow authorized disposal controls."),("lot","Does creating a lot label itself add stock? yes or no","no","Metadata needs a separate actual tracked receipt."),("trace","Should the actual issued batch be recorded when lot tracking applies? yes or no","yes","The selected batch preserves traceability and its own balance.")),
 "P":(("yield","A one-portion recipe requires 0.25 kg. How many kg are planned for 12 portions with no allowance?",3,"12 × 0.25 kg = 3 kg."),("allowance","A 0.25 kg ingredient has waste factor 0.1. What effective kg does the formula require?","0.275","0.25 × 1.1 = 0.275 kg."),("approve","May a formula creator independently approve their own recipe? yes or no","no","A different authorized person checks the formula.")),
 "Q":(("plan","Does saving a production plan consume ingredients? yes or no","no","Actual execution posts actual usage and usable output."),("usable","Total output is 12 portions and 2 are rejected. How many usable portions should enter stock?",10,"12 total − 2 rejected = 10 good portions."),("actual","Should planned ingredient quantities replace measured actual use just to match the plan? yes or no","no","Record actual material use and explain variances.")),
 "R":(("modifier","A PHP 250 plate has a PHP 20 modifier. What is its total before other pricing rules?",270,"250 + 20 = PHP 270."),("mapping","Does a visible menu item alone prove recipe consumption is mapped? yes or no","no","Verify the separate POS product/recipe/location mapping."),("permission","Should an employee change approved menu prices without the relevant assignment? yes or no","no","Menu maintenance needs its own authorized responsibility.")),
 "S":(("raw","Should POS consume raw chicken again when preparation already converted it into the mapped prepared portions? yes or no","no","A serving recipe must consume its actual prepared ingredient."),("retry","Should retrying the same sale deduct its ingredients twice? yes or no","no","The same sale/event identity must remain idempotent."),("refund","Does a financial refund prove cooked food became usable raw ingredients again? yes or no","no","Money and physical disposition are separate; cooked ingredients cannot be reconstructed.")),
 "T":(("meal","Should actual staff meals deduct their consumed ingredients? yes or no","yes","A posted meal records actual consumption and cost."),("servings","A PHP 500 meal serves 10 people. What is the cost per serving in pesos?",50,"500 ÷ 10 = PHP 50 per serving."),("reverse","Should an actually eaten meal be reversed only to increase stock? yes or no","no","Reverse a verified mistake, not real consumption.")),
 "U":(("property","Does issuing a reusable towel mean the resort no longer owns it? yes or no","no","The towel changes custody and condition, not ownership."),("laundry","Is unfinished laundry already clean available stock? yes or no","no","Only inspected accepted clean returns enter the clean bucket."),("rooms","Two rooms need two towels each. How many towels does that standard require?",4,"2 rooms × 2 towels = 4 towels; check actual availability separately.")),
 "V":(("start","Does starting an asset work order certify completion? yes or no","no","Starting records work in progress; completion follows the actual work."),("costs","Should a repair with outside charges use the screen's zero-cost Complete action to hide those charges? yes or no","no","Use the supported authorized cost-capture process."),("depreciation","A PHP 6,000 asset has zero residual and a 60-month straight-line life. What monthly amount in pesos applies?",100,"6,000 ÷ 60 = PHP 100 per month.")),
 "W":(("delivery","Does successful event delivery alone prove a General Ledger journal was posted? yes or no","no","Delivery, acceptance, journal posting and reconciliation are separate evidence."),("retry","Does requeueing an eligible event create another purchase order? yes or no","no","It preserves the existing source event and obligation."),("accepted","Should an already accepted Accounting event be requeued as a new obligation? yes or no","no","Preserve accepted evidence; investigate through the authorized reconciliation process.")),
 "X":(("assignee","Does accepted connected work need an accountable active assignee? yes or no","yes","Accountability requires a canonical active person."),("handover","Does accepting a stock request physically issue its supplies? yes or no","no","The actual stock handover needs its own business evidence."),("duplicate","Should completing follow-up deduct already issued supplies again? yes or no","no","Complete the existing work without duplicating its movement.")),
 "Y":(("cause","Does higher purchasing spend alone prove theft? yes or no","no","Check demand, prices, stock, waste and timing before drawing conclusions."),("basis","Should periods and locations match before comparing report totals? yes or no","yes","Compare the same scope and dates."),("review","Does a report replace missing transaction evidence? yes or no","no","Follow the underlying documents and investigate missing evidence.")),
 "Z":(("scope","Can a general role permission override the employee's assigned location limit? yes or no","no","Location and financial scope still apply."),("identity","Should a trainer use one employee's session to impersonate another? yes or no","no","Separate employee sessions and preserve participant history."),("backup","Should a verified recovery copy preserve transaction and assessment history? yes or no","yes","Recovery must preserve evidence and be tested in the isolated environment.")),
}


def questions(module,path_id):
    if module is None:
        path=BY_PATH[path_id]
        modules=list(dict.fromkeys([BY_ID[id].module for id in path.final_tasks]+[BY_ID[id].module for id in path.lessons]))
        # Sample the assigned course, beginning with its practical final's
        # responsibilities. A viewer must not be examined on an untaught POS
        # or Accounting integration course merely because the owner takes it.
        contextual=[]
        for index in range(3):
            for letter in modules:
                row=TOPICS[letter][index]
                contextual.append(q("final-"+letter+"-"+row[0],*row[1:],critical=True))
                if len(contextual)==5:return FOUNDATION+tuple(contextual)
        return FOUNDATION+tuple(contextual)
    return FOUNDATION+tuple(q(module+"-"+row[0],*row[1:],critical=row[0] in {"truth","approval","independent","limit","raw","refund","laundry","accepted","scope"}) for row in TOPICS[module])


def blueprint(path_id,module=None):
    path=BY_PATH[path_id]
    if module is not None and module not in {BY_ID[id].module for id in path.lessons}:raise ValueError("This module is outside the chosen course")
    applicable=tuple(id for id in path.lessons if module is None or BY_ID[id].module==module)
    if module is None:practical=path.final_tasks
    else:
        # The linked exercise covers the module's complete chain where one is
        # available; otherwise sample an actual action and a distinct control.
        caps=[id for id in applicable if BY_ID[id].workflow.startswith("capstone_")]
        actions=[id for id in applicable if not BY_ID[id].workflow.startswith("read_")]
        refusals=[id for id in actions if any(step.outcome_status for step in BY_ID[id].steps)]
        chosen=(caps[:1] or actions[:1] or list(applicable[:1]))+refusals[:1]
        evidence={"Y":"interpret-supplier-acceptance","S":"sale-consumption","Q":"interpret-actual-yield-cost"}.get(module)
        if evidence in applicable:chosen.append(evidence)
        practical=tuple(dict.fromkeys(chosen))
    return {"path_id":path_id,"path_title":path.title,"module":module,"title":(f"Module {module} final" if module else path.title+" final"),"version":VERSION,"assessment_version":ASSESSMENT_VERSION,"lessons":applicable,"practical_lessons":practical,"questions":questions(module,path_id),"thresholds":{"knowledge":85,"practical":90,"critical":100}}


def public_blueprint(row):
    return {**row,"questions":[{key:value for key,value in asdict(question).items() if key not in {"answer","correction"}} for question in row["questions"]]}


def normalize(value):
    clean=" ".join(str(value).lower().strip().replace(",","").split())
    try:
        number=Decimal(clean)
        if number.is_finite():return str(number.normalize())
    except InvalidOperation:pass
    return clean


def grade_knowledge(row,answers):
    checked=[{"id":question.id,"prompt":question.prompt,"passed":normalize(answers.get(question.id,""))==normalize(question.answer),"critical":question.critical,"correction":question.correction} for question in row["questions"]]
    return {"score":round(100*sum(question["passed"] for question in checked)/len(checked),2),"critical_pass":all(question["passed"] for question in checked if question["critical"]),"questions":checked}


def prerequisites(row,history,module_results=()):
    def passed(id,modes):
        actual={attempt["mode"] for attempt in history if attempt["lesson_id"]==id and attempt["role"]==BY_PATH[row["path_id"]].role and attempt["curriculum_version"]==VERSION and attempt["status"]=="passed"}
        return modes<=actual
    modes={"guided","assisted"} if row["module"] else {"guided","assisted","independent"}
    missing=[id for id in row["lessons"] if not passed(id,modes)]
    missing_modules=[]
    if row["module"] is None:
        required={BY_ID[id].module for id in row["lessons"]}
        completed={exam["module"] for exam in module_results if exam["path_id"]==row["path_id"] and exam["curriculum_version"]==VERSION and exam["assessment_version"]==ASSESSMENT_VERSION and exam["status"]=="passed"}
        missing_modules=sorted(required-completed)
    return {"ready":not missing and not missing_modules,"missing_lessons":missing,"missing_module_finals":missing_modules}


def grade_practical(tasks):
    if not tasks:return {"score":0,"critical_pass":False,"passed":False}
    score=round(sum(task["score"] for task in tasks)/len(tasks),2)
    critical=all(task["critical_pass"] for task in tasks)
    return {"score":score,"critical_pass":critical,"passed":score>=90 and critical}
