"""Restricted real controls and local operational follow-up."""
from training.lesson_types import Lesson, Step, input_step as fill, select_step as choose, action_step as act
OWNER=("owner",)


def task(id,module,title,route,situation,concept,example,rule,steps,sources,roles=OWNER,global_access=True,question="Does completing this practice grant production permissions? yes or no"):
    questions={
        "assign-location-approval-scope":"Does a stockroom-only scope authorize work at another location? yes or no",
        "create-operating-department":"Does creating a department grant employee access? yes or no",
        "retire-unused-classification":"Does deactivating a department automatically reclassify existing items? yes or no",
        "classify-legacy-ingredient":"Does classifying this item create another item or opening balance? yes or no",
        "resolve-verified-feedback":"Should feedback be marked resolved before its fix is verified? yes or no",
        "resolve-verified-incident":"Does clicking Resolve itself restore lost data? yes or no",
    }
    question=questions.get(id,question)
    if isinstance(steps,Step):steps=(steps,)
    return Lesson(id,module,title,roles,route,"admin_"+id,situation,concept,example,rule,question,"no",rule+" "+situation,sources,tuple(steps),global_access=global_access)


LESSONS=[
    task("assign-location-approval-scope","Z","Assign a bounded location and approval limit","/settings/access-scopes",
        "The authorized administrator approved Training purchasing colleague for Training stockroom only, with a PHP {scope_limit} approval limit. Add that exact scope. Leave workspace, department and record class at All; the location still limits this assignment.",
        "Role permission, operational location and monetary approval limit all apply. A scope does not change the assigned role or permit self-approval.",
        "A purchasing role with a PHP 1,000 stockroom limit cannot approve a PHP 2,000 order or act in another department just because it can open Purchasing.",
        "Assign only the approved person, location and limit. Check existing assignments first because another active scope can broaden access.",(
            choose('[aria-label="Scope user"]',"Choose Training purchasing colleague.",'{purchaser}'),
            choose('[aria-label="Scope location"]',"Restrict the scope to Training stockroom.",'{store}'),
            fill('[aria-label="Scope approval limit"]',"Use the approved limit PHP {scope_limit}.",'{scope_limit}'),
            act('[data-training="scope-save"]',"Review the bounded assignment and add this scope.","/access-scopes")),("pass6_controls.py",)),
    task("create-operating-department","Z","Add an approved department classification","/settings/classification",
        "Add an authorized department with stable code train-cafe, name Training café outlet and workspace F&B. Leave behavior key, parent and description blank and sort order zero. This classification does not move stock or grant anyone access.",
        "Departments describe operational responsibility. Stable codes support references; system behavior keys have protected machine meanings.",
        "A café department can classify its supplies without creating a new stockroom or a staff permission assignment.",
        "Check for an existing department before creating another. Keep system behavior meanings unchanged.",(
            act('[data-training="classification-tab-department"]',"Choose Departments & outlets."),
            fill('#dimension-code',"Use stable code train-cafe.","train-cafe"),
            fill('#dimension-name',"Name it Training café outlet.","Training café outlet"),
            choose('#dimension-workspace',"Choose F&B.",'{fnb}'),
            act('[data-training="classification-create"]',"Add the approved department without changing system behavior.","/classification/dimensions")),("classification.py",)),
    task("retire-unused-classification","Z","Retire an unused department without deleting it","/settings/classification",
        "Training old outlet is an unused non-system department. The administrator confirmed no active assignments need it. Deactivate that exact row while retaining its code and history.",
        "Inactive classification remains historical evidence. Deactivation does not reclassify items, remove stock or revoke every related access assignment automatically.",
        "An old outlet label may be retired only after affected assignments and records are reviewed.",
        "Verify dependencies and authorization before deactivation; preserve protected behavior keys and historical records.",(
            act('[data-training="classification-tab-department"]',"Choose Departments & outlets."),
            act('[data-training="classification-toggle-training-old-department"]',"Deactivate only Training old outlet.","/classification/dimensions/training-old-department")),("classification.py",)),
    task("classify-legacy-ingredient","Z","Classify an existing ingredient deliberately","/settings/classification",
        "TRAIN-CHICKEN is an existing unclassified stock item. Assign workspace F&B and item type Ingredient. Leave optional department and cost center blank. Save only this item. The item type derives its record class; do not change its kg base unit or existing stock.",
        "Workspace and item type control behavior. Classifying an existing record does not create another item or another opening balance.",
        "A chicken ingredient remains the same kg stock record after classification. Its old receipts and costs must remain traceable.",
        "Check the existing SKU and intended behavior, then classify the original record without duplicating it.",(
            choose('[aria-label="Workspace for Chicken (kg)"]',"Assign F&B to the existing chicken item.",'{fnb}'),
            choose('[aria-label="Item type for Chicken (kg)"]',"Choose Ingredient; its record class is derived.",'{ingredient}'),
            act('[data-training="classification-save-training-chicken"]',"Save only TRAIN-CHICKEN's approved classification.","/classification/items/training-chicken")),("classification.py",)),
    task("create-accounting-mapping","W","Record a reviewer-approved Accounting mapping","/assets/maintenance",
        "The fictional Accounting reviewer approved event inventory.stock_document.posted with debit TRAIN-INVENTORY and credit TRAIN-CLEARING. Add that mapping with description Training reviewer-approved mapping. These are practice account references, not the production chart of accounts.",
        "A mapping describes intended debit and credit treatment. It is separate from event delivery, acceptance, journal posting, financial reconciliation and payment.",
        "A saved mapping can support review of an inventory movement; it does not prove an external journal exists.",
        "Use only reviewer-approved account references and dimensions. Verify the separate Accounting acceptance and posted journal before reporting reconciliation.",(
            fill('[aria-label="Accounting mapping event"]',"Use event inventory.stock_document.posted.","inventory.stock_document.posted"),
            fill('[aria-label="Accounting mapping debit"]',"Use approved practice debit TRAIN-INVENTORY.","TRAIN-INVENTORY"),
            fill('[aria-label="Accounting mapping credit"]',"Use approved practice credit TRAIN-CLEARING.","TRAIN-CLEARING"),
            fill('[aria-label="Accounting mapping description"]',"Retain the review reference Training reviewer-approved mapping.","Training reviewer-approved mapping"),
            act('[data-training="accounting-mapping-save"]',"Save the reviewed intent without posting any journal.","/accounting-mappings")),("pass5_operations.py",),question="Does saving this mapping prove a General Ledger journal was posted? yes or no"),
    task("save-report-scope","Y","Save the intended report scope","/reports/operations",
        "Select workspace F&B and save view Training F&B review. Leave Default unchecked. Read the resulting scope; this saves your own report definition without changing stock or financial values.",
        "A report filter changes what is included. A saved view stores a definition; it is not transaction evidence or a physical inventory adjustment.",
        "Reviewing café supplies under the whole-resort scope can produce a different value than reviewing only F&B. Check scope before comparing periods.",
        "Check the workspace, period and included records before interpreting a total. The current Saved views table lists definitions; it does not provide an Apply shortcut.",(
            choose('[aria-label="Operating report workspace"]',"Choose F&B before saving the definition.",'{fnb}'),
            fill('[aria-label="Saved report view name"]',"Name the view Training F&B review.","Training F&B review"),
            act('[data-training="report-view-save"]',"Leave Default unchecked and save your report scope.","/saved-views")),("pass6_controls.py",),question="Does saving a report view change physical stock? yes or no"),
    task("acknowledge-operational-alert","X","Read an alert without treating it as completed work","/stock",
        "Open Notifications and read TRAIN-REVIEW-ALERT. The message asks the supervisor to investigate a stock discrepancy. Marking it read acknowledges the message; the investigation and any authorized business correction are separate.",
        "Notifications bring work to your attention. Reading one does not accept a purchase, correct stock or complete an Operations request.",
        "An unread variance alert becomes Read after acknowledgement, while the count and stock records remain unchanged.",
        "Read the message, find the underlying document and follow the assigned responsibility. Never use Read as evidence that the actual issue was resolved.",(
            act('[data-training="notifications-open"]',"Open Notifications."),
            act('[data-training="notification-training-review-alert"]',"Read and acknowledge TRAIN-REVIEW-ALERT.","/notifications/training-review-alert/read")),("operations.py",),roles=("inventory_manager","owner"),global_access=False,question="Does marking an alert read correct its underlying stock discrepancy? yes or no"),
    task("submit-workflow-feedback","X","Report a specific workflow problem","/rollout",
        "A count observation was difficult to enter on a phone. Submit category Usability, severity Normal, page /counts, with details Training: count field difficult to read on phone. No real employee or customer information is needed.",
        "Specific feedback describes the page, actual difficulty and impact. It does not replace recording physical quantities or reporting an urgent operational incident to the supervisor.",
        "A normal usability issue can say which field was hard to read; a genuine missing delivery or food-safety concern needs its operational escalation too.",
        "Describe the observed problem accurately and include no passwords or unnecessary personal details. Do not repeat stock postings to test a complaint.",(
            choose('[aria-label="Feedback category"]',"Choose Usability.","usability"),
            choose('[aria-label="Feedback severity"]',"Choose Normal for this readability concern.","normal"),
            fill('[aria-label="Feedback workflow"]',"Identify the page /counts.","/counts"),
            fill('[aria-label="Feedback details"]',"Describe Training: count field difficult to read on phone.","Training: count field difficult to read on phone"),
            act('[data-training="feedback-submit"]',"Submit the specific concern without posting another stock transaction.","/feedback")),("stabilization.py",),roles=("inventory_manager","owner"),global_access=False,question="Does submitting feedback itself correct stock or complete the count? yes or no"),
    task("resolve-verified-feedback","Z","Close feedback only after its fix is verified","/rollout",
        "Training verified readability fix describes a concern whose correction was already checked by the reporting colleague. Resolve that exact feedback row. Other open work must remain open.",
        "Resolved is a reviewed follow-up state. Clicking Resolve is not proof that an untested complaint was fixed.",
        "The colleague verifies the count field can be read before an administrator closes the feedback record.",
        "Verify the real resolution first, then update only the matching feedback. Preserve its original message and reporter.",(
            act('[data-training="feedback-resolve-training-feedback"]',"Resolve only Training verified readability fix.","/feedback/training-feedback")),("stabilization.py",)),
    task("resolve-verified-incident","Z","Close an operational incident with verified recovery","/rollout",
        "TRAIN-INCIDENT records a practice workstation interruption. The authorized colleague reconnected and verified that the original practice documents still load. Resolve only that incident. This action does not perform a restore or certify production recovery.",
        "An incident records operational impact and follow-up. Resolution follows verified recovery; it does not itself repair data or create a backup.",
        "After a connection interruption, compare known transaction references before changing the incident state.",
        "Keep recovery restricted to qualified administrators and isolated copies. Retain incident details, original references and verification evidence.",(
            act('[data-training="incident-resolve-training-incident"]',"Resolve only TRAIN-INCIDENT after the stated recovery verification.","/incidents/training-incident")),("stabilization.py",)),
    task("record-assurance-review","Z","Record an honest assurance snapshot","/reports/final-assurance",
        "Review the practice assurance report, then Record snapshot. Stock should reconcile, but no completed backup exists and integrations remain local. Preserve these exceptions; do not mark the practice environment ready for production.",
        "An assurance snapshot records current checks in the audit trail. A green stock reconciliation check does not make missing backup evidence or unresolved work disappear.",
        "Zero ledger mismatches can coexist with a critical overall state caused by a missing completed backup.",
        "Record the actual results and investigate each failed or attention check. A snapshot is evidence, not approval to deploy.",(
            act('[data-training="assurance-record"]',"Read the failures, then record this exact assurance snapshot.","/reports/final-assurance/record")),("final_assurance.py",),question="Does a recorded snapshot with missing backup evidence authorize production rollout? yes or no"),
    task("run-isolated-acceptance","Z","Record acceptance failures without hiding them","/readiness",
        "Run acceptance checks in this isolated practice database. No backup record exists, so the run must fail its backup check. The inherited production-candidate label is only a record label here; the button does not deploy anything.",
        "Acceptance checks test specific controls. Missing recovery evidence must remain a failure even when database connectivity and ledger reconciliation pass.",
        "A reachable database is not enough for release: a tested recovery copy and the separate deployment controls still matter.",
        "Read and retain failed checks. Do not fabricate a completed backup, change production settings or start external workers to make practice green.",(
            act('[data-training="acceptance-run"]',"Run and retain the isolated acceptance result with its missing-backup failure.","/acceptance-runs")),("readiness.py",),question="Does passing database connectivity alone mean all acceptance checks passed? yes or no"),
    task("check-isolated-rollout","Z","Interpret a diagnostic test alongside rollout gates","/rollout",
        "Run the operational smoke test. The training stock ledger reconciles, but backup evidence is absent. Keep the failed backup result and read the separate rollout gates; a GO summary alone is insufficient.",
        "The GO summary checks high-priority feedback, critical incidents and dead letters. It does not itself prove backups, acceptance, physical counts or all deployment controls are ready.",
        "A summary can show GO while a backup check fails. The full release decision still requires every applicable gate and independent evidence.",
        "Use the full checks together and escalate missing evidence. Never change real configuration or fabricate backup records during training.",(
            act('[data-training="rollout-smoke"]',"Run the diagnostic and read its failed backup check.","/rollout/smoke-test")),("stabilization.py",),question="Is the GO summary alone sufficient when the backup diagnostic failed? yes or no"),
]
