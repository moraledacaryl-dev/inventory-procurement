"""Fixed fictional practice inputs; never reads an arbitrary filesystem path."""
CSV_FILES={
 "import-item-catalogue":("training-items.csv","items"),
 "import-supplier-catalogue":("training-suppliers.csv","suppliers"),
 "reject-invalid-csv":("training-invalid-items.csv","items"),
 "import-initial-balances":("training-opening.csv","opening_balances"),
 "refuse-duplicate-opening-import":("training-opening.csv","opening_balances"),
}


def practice_csv(id,v):
    if id not in CSV_FILES:return None
    filename,type=CSV_FILES[id]
    if type=="items":
        content="sku,name,category,unit,minimum_stock,standard_cost\nTRAIN-MILK,Training milk cartons,Training drinks,TRAIN-EACH,12,75\n"
        if id=="reject-invalid-csv":content+="TRAIN-MILK,Duplicate milk cartons,Training drinks,TRAIN-EACH,12,75\n"
    elif type=="suppliers":
        content="code,name,contact_name,email,payment_terms_days\nTRAIN-FARM,Training Farm Supplies,Training contact,farm@example.com,21\n"
    else:content=f"sku,location,quantity,average_cost\nTRAIN-CHICKEN,TRAIN-STORE,{v['quantity']},200\n"
    return {"filename":filename,"content":content,"import_type":type}
