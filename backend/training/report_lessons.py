"""Interpret source reports by following real, unchanged sandbox evidence."""
from training.lesson_types import Lesson, Step, select_step as choose, input_step as fill
REPORT=("inventory_manager","procurement_officer","viewer","owner")
REVIEW=("inventory_manager","viewer","owner")

def read(id,module,title,route,situation,concept,example,rule,question,sources,roles=REPORT,steps=(),global_access=False,quantity=6):
    return Lesson(id,module,title,roles,route,"read_report",situation,concept,example,rule,question,"no",rule,sources,tuple(steps),quantity,global_access=global_access)

LESSONS=[
    read("interpret-stock-valuation","Y","Read stock value without mixing physical units","/inventory-operations",
        "Review Inventory value for the training stockroom. It contains chicken in kg and individual amenity kits. Report the weighted-average value in pesos, keeping both item units separate.",
        "Inventory value adds monetary amounts: each item's physical quantity times its weighted-average cost. Kilograms and individual kits cannot be added into one useful physical quantity.",
        "24 kg at PHP 200/kg is PHP 4,800; 24 kits at PHP 50 each is PHP 1,200. Total inventory value is PHP 6,000. This is neither sales nor profit.",
        "Compare the same location and cost basis. Investigate quantities and prices before interpreting a value change.",
        "Does inventory value mean the resort earned that amount as profit? yes or no",("inventory_operations.py",)),
    read("interpret-period-issues","D","Filter movement history and distinguish it from closing stock","/stock",
        "A fictional colleague recorded an earlier 2 kg issue on 18 November and a later {quantity} kg issue on 25 November 2026. In Stock ledger select Chicken, Training stockroom, Issue, From 24 November and To 26 November. Read Net quantity for that period; keep the opening stock and earlier issue outside those period totals.",
        "A period's net movement is the signed change during the selected dates. Running quantity includes earlier movements. Neither a selected period total nor a client-side text search is a separate closing-stock valuation.",
        "If opening stock is 24 kg, an earlier issue is 2 kg and this period issues 6 kg, period net movement is -6 kg; closing physical stock is 16 kg.",
        "Check item, location, type, dates and partial-results warnings. Increased issues require demand, yield and waste evidence; they do not alone prove theft.",
        "Does a period's net movement equal its closing physical stock? yes or no",("stock_ledger.py",),steps=(
            choose('[aria-label="Ledger item"]',"Filter to Chicken (kg).","{chicken}"),
            choose('[aria-label="Ledger location"]',"Filter to Training stockroom.","{store}"),
            choose('[aria-label="Ledger document type"]',"Select Issue.","issue"),
            fill('[aria-label="Ledger from date"]',"Start at 24 November 2026.","2026-11-24"),
            Step('[aria-label="Ledger to date"]',"End at 26 November 2026, then read the returned Net quantity.","2026-11-26","input","/stock/ledger",outcome_method="GET"))),
    read("interpret-waste-value","H","Trace the quantity and value of recorded waste","/stock",
        "A colleague recorded {quantity} kg of spoiled chicken with reference TRAIN-WASTE. Find that reference in Stock ledger. Read its signed Line value, not the header total for unrelated movements. Do not record the waste a second time.",
        "A waste movement removes unusable quantity and its carrying value. A report line is evidence of what was recorded; physical inspection and an accurate reason remain necessary.",
        "Six kg at PHP 200/kg produces a -6 kg movement and PHP -1,200 line value. It is not another supplier receipt or proof of cash payment.",
        "Follow the exact item, location and reference. Preserve the original posting and investigate the cause rather than hiding waste with a new receipt.",
        "Should an already recorded waste event be posted again merely to review its cost? yes or no",("controlled_inventory.py","stock_ledger.py")),
    read("interpret-posted-count","G","Read an independently posted count difference","/counts/{count}",
        "A fictional counter counted {quantity} kg in TRAIN-COUNT. A different authorized reviewer checked and posted it. Read the signed Variance on the posted historical count. Leave the original observation and adjustment unchanged.",
        "Variance is actual counted quantity less the snapshot. A posted count retains both the observation and independently approved adjustment. This review task is not an unfinished blind-count entry task.",
        "A verified 21 kg count against a 24 kg snapshot is -3 kg. The approved correction brings physical stock to 21 kg once.",
        "Check the original count and independent approval. Never edit an observed count just to remove a difference.",
        "Should a posted count difference be hidden by changing the original physical observation? yes or no",("guided_counts.py",),roles=REVIEW,quantity=21),
    read("interpret-supplier-acceptance","Y","Distinguish arrived goods from usable supplier delivery","/reports",
        "A colleague inspected a {quantity} kg chicken delivery for TRAIN-PO and rejected 2 kg. In Supplier performance read Training Valley Foods' Acceptance %. The current application counts arrived goods toward PO fulfillment, while usable stock receives accepted goods only.",
        "Acceptance percent divides accepted value by arrived value. A completed order can contain rejected goods; completion does not certify that all delivered goods were usable.",
        "Ten kg arrived and 2 kg was rejected at the same price: acceptance is 8/10 = 80%. Eight kg enters stock, even though ten kg counts as arrived.",
        "Review the underlying receipt, rejection reason and delivery timing. Do not infer quality from a completed-order count alone.",
        "Does a completed purchase order prove every arrived item was usable? yes or no",("procurement.py","receiving_workspace.py"),quantity=10),
    read("interpret-actual-yield-cost","Q","Follow actual production output to its posted cost","/production/batches/{batch}",
        "A fictional kitchen colleague planned 12 portions and actually used 3 kg of chicken at PHP 200/kg to produce {quantity} good portions. Open TRAIN-BATCH's stock document and read the output line's Unit cost for TRAIN-ALFREDO. The batch summary's planned cost per output unit remains a plan.",
        "The same PHP 600 material cost spread over fewer good portions increases actual cost per portion. Raw usage and finished output are linked in one source production document.",
        "PHP 600 divided by 10 good portions gives PHP 60 per portion, compared with PHP 50 for the planned twelve.",
        "Use the actual output line and its unit. Do not add raw kilograms and finished portions into one meaningful physical total or issue the raw ingredients again.",
        "Should the batch's planned unit cost replace its posted actual output unit cost? yes or no",("production_execution.py","stock_ledger.py"),roles=REVIEW,quantity=10,steps=(Step('[data-training="production-document"]',"Open the batch's actual stock document and inspect the TRAIN-ALFREDO output line.",event="read",outcome="/stock/documents/*"),)),
    read("interpret-assurance-evidence","Y","Separate stock reconciliation from recovery readiness","/reports/final-assurance",
        "Review Final assurance without recording a new snapshot. The synthetic ledger reconciles with balances, but this fresh sandbox has no completed backup record. Read the backup check's Status. A passing stock check does not establish recovery readiness.",
        "Assurance checks answer separate questions. Stock reconciliation compares the recorded ledger with balances, not with a physical count. Backup evidence needs an actual verified recovery process.",
        "Zero stock mismatches can coexist with a failed backup check. Neither recording an assurance snapshot nor inventing a backup row creates a recovery copy.",
        "Investigate each failed or attention check with its supporting evidence. Ask the qualified administrator for a tested recovery copy; never manufacture a green status.",
        "Does zero stock mismatch prove a backup can restore the training history? yes or no",("final_assurance.py",),global_access=True),
]
