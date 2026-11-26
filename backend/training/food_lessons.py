"""Recipe governance, preparation, staff costs and POS catalogue controls."""
from training.lesson_types import Lesson, Step, input_step as fill, select_step as choose, action_step as act

STOCK=("inventory_manager","owner")


def task(id,module,title,route,situation,concept,example,rule,question,steps,roles=STOCK,quantity=5):
    if isinstance(steps,Step):steps=(steps,)
    sources=("menu.py",) if module=="R" else ("staff_meals.py",) if module=="T" else ("production.py","recipe_costing.py","pos_sync.py")
    return Lesson(id,module,title,roles,route,"food_"+id,situation,concept,example,rule,question,"no",rule+" "+situation,sources,steps,quantity,global_access=module=="R")


LESSONS=[
    task("staff-meal-shortage","T","Stop an unprepared meal when ingredients are short","/fnb/staff-meals",
        "The kitchen is considering a meal for 4 people requiring {meal_shortage} kg of chicken, but only {base} kg physically exists at Training stockroom. Nothing has been cooked or taken. Enter the proposed requirement, preview it, and in this isolated exercise confirm that posting is also refused. Keep the original stock unchanged and ask the supervisor to revise the plan or arrange a real authorized supply movement.",
        "The source meal workflow refuses a quantity above physical stock when negative stock is prohibited. Servings do not create ingredients. Its preview uses physical balance, so separately check reservations before allocating supplies to another job.",
        "If 24 kg exists and a proposed meal requires 25 kg, the shortage is 1 kg. Do not invent a receipt or adjustment to make the meal pass.",
        "Resolve the actual supply or plan with the supervisor before cooking or recording consumption. Never pretend unavailable ingredients were used or restore stock from a meal people ate.",
        "Should an invented stock receipt be used to bypass a meal shortage? yes or no",(
            fill('[data-training="meal-name"]',"Name the proposed meal Training shortage check.","Training shortage check"),
            choose('[data-training="meal-location"]',"Check Training stockroom.","{store}"),
            fill('[data-training="meal-servings"]',"The proposed meal is for 4 people.","4"),
            choose('#ingredient-0',"Choose Chicken (kg).","{chicken}"),
            fill('#quantity-0',"Enter the proposed requirement {meal_shortage} kg; no ingredients have been used.","{meal_shortage}"),
            act('[data-training="meal-preview"]',"Read the actual shortage refusal from Preview cost.","/staff-meals/preview",409),
            act('[data-training="meal-post"]',"In this isolated check, verify that Post staff meal also refuses unavailable stock.","/staff-meals",409))),
    task("create-governed-recipe","P","Create a recipe with explicit units and preparation waste","/production",
        "Create draft TRAIN-TEST-RECIPE, named Training chicken portion, yielding 1 portion of Training Chicken Alfredo. Each portion requires 0.25 kg chicken before a 10% preparation allowance. Enter waste factor 0.1 and Notes {reference}. Leave the ingredient required. Do not approve your own formula.",
        "Recipe lines use the ingredient's base unit. The waste factor adds preparation allowance to the formula, not a second finished portion.",
        "250 g is 0.25 kg. At waste factor 0.1, the effective requirement is 0.25 × 1.1 = 0.275 kg, costing PHP 55 at PHP 200/kg.",
        "Convert quantities before entry, confirm the yield and allowance, and leave a new formula as a draft for independent approval.",
        "Should 250 g be entered as 250 on a kg recipe line? yes or no",(
            act('[data-training="recipe-create-open"]',"Open New recipe."),
            fill('[aria-label="Recipe code"]',"Use the unique code TRAIN-TEST-RECIPE.","TRAIN-TEST-RECIPE"),
            fill('[aria-label="Recipe name"]',"Name it Training chicken portion.","Training chicken portion"),
            choose('[aria-label="Recipe output item"]',"Choose Training Chicken Alfredo.",'{alfredo}'),
            fill('[aria-label="Recipe yield quantity"]',"This formula yields 1 portion.","1"),
            fill('[aria-label="Recipe notes"]',"Enter reference {reference}.","{reference}"),
            choose('[aria-label="Recipe ingredient 1"]',"Choose Chicken (kg).",'{chicken}'),
            fill('[aria-label="Recipe ingredient 1 quantity"]',"250 g is 0.25 kg. Enter 0.25.","0.25"),
            fill('[aria-label="Recipe ingredient 1 waste factor"]',"Enter 0.1 for a 10% preparation allowance.","0.1"),
            act('[data-training="recipe-create-save"]',"Leave Optional unchecked and save the formula as a draft.","/recipes"))),
    task("approve-colleague-recipe","P","Independently approve a checked formula","/production/recipes/{recipe}",
        "A colleague prepared TRAIN-ALFREDO as a draft. You verified its one-portion yield and 0.25 kg chicken requirement. Approve this checked version for production.",
        "Only an approved recipe can be selected for a new production batch or POS mapping. The creator must not be its approver.",
        "An independently checked 0.25 kg formula requires 3 kg for 12 portions, before any separately recorded actual waste.",
        "Check units, yield and ingredients before approval. Formula approval does not physically consume anything.",
        "Does approving a recipe deduct ingredients immediately? yes or no",(
            act('[data-training="recipe-approve"]',"Review the draft and choose Approve recipe."),
            act('[data-training="confirm"]',"Confirm independent approval of this checked formula.","/recipes/training-recipe/approve"))),
    task("recipe-self-approval","P","Keep recipe creation and approval independent","/production/recipes/{recipe}",
        "You created the draft TRAIN-ALFREDO. Try approving it in this isolated exercise and read the refusal. Keep it as a draft for another authorized person.",
        "A creator cannot independently check their own formula, even with an owner role.",
        "A misplaced decimal in your own formula needs another person's review before every sale uses it.",
        "Ask a different authorized person to approve. Never use another person's sign-in or change the creator.",
        "Can you independently approve a recipe you created yourself? yes or no",(
            act('[data-training="recipe-approve"]',"Try Approve recipe for your own draft."),
            act('[data-training="confirm"]',"Read the independent-approval refusal.","/recipes/training-recipe/approve",409))),
    task("retire-obsolete-recipe","P","Retire a formula without deleting history","/production/recipes/{recipe}",
        "TRAIN-ALFREDO is an obsolete approved formula, and the authorized recipe steward has confirmed retirement. Retire it while keeping its version and ingredient history.",
        "Retirement removes a formula from new production choices. It does not undo batches or restore ingredients already consumed.",
        "Retiring an old sauce formula does not put yesterday's chicken back in the stockroom.",
        "Check that retirement is authorized and review affected POS mappings. Ask the steward for a properly approved replacement.",
        "Does recipe retirement reverse earlier stock consumption? yes or no",(
            act('[data-training="recipe-retire"]',"Choose Retire recipe for the confirmed obsolete version."),
            act('[data-training="confirm"]',"Retain its history and retire this formula.","/recipes/training-recipe/retire"))),
    task("plan-production-batch","Q","Plan output before recording actual production","/production",
        "The kitchen plans {quantity} portions using approved TRAIN-ALFREDO at Training stockroom. Save the plan with Notes {reference}. Nothing has been cooked or issued yet.",
        "A production plan is an intention. Actual ingredient use, waste and finished output are recorded during execution.",
        "Planning 5 portions from a 0.25 kg formula suggests 1.25 kg chicken, but saving the plan does not deduct that amount.",
        "Choose an approved recipe and correct location. Do not report a plan as completed production.",
        "Does planning a batch prove that finished portions exist? yes or no",(
            choose('[aria-label="Batch approved recipe"]',"Choose TRAIN-ALFREDO.",'{recipe}'),
            choose('[aria-label="Batch location"]',"Choose Training stockroom.",'{store}'),
            fill('[aria-label="Batch planned output"]',"Plan {quantity} portions.","{quantity}"),
            fill('[aria-label="Batch notes"]',"Enter reference {reference}.","{reference}"),
            act('[data-training="batch-plan-save"]',"Save the production plan without executing it.","/production-batches"))),
    task("reverse-duplicate-staff-meal","T","Reverse a duplicate meal that never consumed stock","/fnb/staff-meals",
        "TRAIN-DUPLICATE was posted by mistake. No second meal was cooked and its {quantity} kg of chicken remains physically in storage. A supervisor approved reversing this duplicate. Reverse that posted record once; keep both the original and correction.",
        "Reversal restores the quantities from a mistaken staff-meal posting. It must not be used to restore food that people actually ate.",
        "If a 5 kg meal was accidentally posted twice, reverse the duplicate only. A genuine meal remains consumed.",
        "Verify the physical situation and approval. Reverse only the incorrect record and retain its linked correction.",
        "Should a meal that was actually eaten be reversed just to increase stock? yes or no",(
            act('[aria-label="Reverse staff meal TRAIN-DUPLICATE"]',"Reverse only TRAIN-DUPLICATE and confirm the approved correction.","/staff-meals/*/reverse"))),
    task("create-menu-with-modifier","R","Create a menu variant and a priced optional choice","/fnb/menu",
        "Your catalogue assignment allows menu maintenance. Add Training garden plate in category Training meals, prepared in Kitchen, with a Regular variant priced PHP 250. Add one single-choice group named Sauce with option Extra sauce | 20. Leave it available and shown in POS. This menu entry alone must not claim ingredient consumption is mapped.",
        "A variant has a base price. A modifier adds an optional choice and price; neither proves that the POS product has a recipe consumption mapping.",
        "A PHP 250 plate with PHP 20 extra sauce totals PHP 270 before any other applicable pricing rule.",
        "Check display name, station, variant and modifier price. Coordinate recipe mapping separately before relying on sale deductions.",
        "Does a visible menu entry alone prove its ingredients will be deducted? yes or no",(
            act('[data-training="menu-create-open"]',"Open Add item."),
            fill('[data-training="menu-name"]',"Name it Training garden plate.","Training garden plate"),
            fill('[data-training="menu-category"]',"Use category Training meals.","Training meals"),
            choose('[data-training="menu-station"]',"Choose Kitchen.","kitchen"),
            fill('[aria-label="Menu variant 1 name"]',"Name the variant Regular.","Regular"),
            fill('[aria-label="Menu variant 1 price"]',"Set the base price to PHP 250.","250"),
            act('[data-training="menu-modifier-add"]',"Add a modifier group."),
            fill('[aria-label="Modifier group 1 name"]',"Name the group Sauce.","Sauce"),
            choose('[aria-label="Modifier group 1 selection"]',"Allow only one choice.","single"),
            fill('[aria-label="Modifier group 1 options"]',"Enter Extra sauce | 20 for the optional PHP 20 choice.","Extra sauce | 20"),
            act('[data-training="menu-save"]',"Check availability and POS visibility, then add the menu item.","/fnb/menu"))),
    task("map-pos-product","S","Link a POS product to its approved recipe","/production",
        "As the authorized integration owner, map fictional POS product TRAIN-POS-PLATE from hidden-oasis-pos to approved TRAIN-ALFREDO at Training stockroom. This configures future consumption; no sale is being posted.",
        "A POS mapping links the external product identity to a recipe and consumption location. A wrong mapping deducts the wrong ingredients.",
        "A later sale of four mapped portions would use four times the approved 0.25 kg recipe, not four kg.",
        "Verify the exact external product, approved recipe and location. Mapping configuration does not itself consume stock.",
        "Does saving a POS mapping itself deduct a sale's ingredients? yes or no",(
            act('[data-training="pos-map-open"]',"Open POS product mapping."),
            fill('[aria-label="POS system"]',"Verify hidden-oasis-pos.","hidden-oasis-pos"),
            fill('[aria-label="POS external product ID"]',"Enter TRAIN-POS-PLATE.","TRAIN-POS-PLATE"),
            choose('[aria-label="POS mapped recipe"]',"Choose approved TRAIN-ALFREDO.",'{recipe}'),
            choose('[aria-label="POS consumption location"]',"Choose Training stockroom.",'{store}'),
            act('[data-training="pos-map-save"]',"Save the verified mapping without posting a sale.","/pos-mappings")),roles=("owner",)),
    task("disable-stale-pos-mapping","S","Stop a mapping that points to a retired formula","/integrations/pos",
        "TRAIN-POS-PLATE still points to retired TRAIN-ALFREDO. Deactivate this stale mapping and coordinate a valid replacement with the POS owner. No live POS system is connected in this training.",
        "A stale mapping must be reviewed before further consumption. Deactivation changes configuration and preserves past sale evidence.",
        "Disabling an old recipe link does not reverse yesterday's meals or automatically connect a replacement recipe.",
        "Deactivate the confirmed stale mapping and check the replacement before reactivation. Do not invent a stock receipt.",
        "Does deactivating a mapping restore ingredients used by past sales? yes or no",(
            act('[data-training="pos-mapping-toggle-training-pos-map"]',"Deactivate the mapping whose recipe is retired.","/pos-mappings/training-pos-map/deactivate")),roles=("owner",)),
]
