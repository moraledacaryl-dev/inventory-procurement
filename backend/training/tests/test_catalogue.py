"""Real API transactions and refusal evidence for the expanded curriculum."""
import pytest
from conftest import begin
from training.catalogue_lessons import LESSONS


def transaction(id,v):
    item="/api/v1/items/training-chicken"
    supplier="/api/v1/suppliers/training-supplier"
    return {
        "create-item":("POST","/api/v1/items",{"sku":"TRAIN-OIL","name":"Training cooking oil","category_id":v["category"],"base_unit_id":v["litre"],"primary_workspace_id":v["fnb"],"item_type_id":v["ingredient"],"default_location_id":v["store"],"minimum_stock":v["quantity"],"standard_cost":150},201),
        "edit-item-reorder":("PATCH",item,{"minimum_stock":v["quantity"]},200),
        "add-item-barcode":("POST",item+"/barcodes",{"barcode":v["barcode"],"barcode_type":"INTERNAL"},201),
        "remove-item-barcode":("DELETE",item+"/barcodes/training-old-barcode",None,204),
        "define-unit-conversion":("POST",item+"/conversions",{"from_unit_id":v["conversion_from"],"to_unit_id":v["conversion_to"],"multiplier":v["conversion_multiplier"]},201),
        "set-location-policy":("POST","/api/v1/item-location-settings",{"item_id":v["chicken"],"location_id":v["store"],"minimum_stock":v["quantity"],"reorder_quantity":20,"maximum_stock":60,"cycle_count_days":7},201),
        "deactivate-empty-item":("PATCH","/api/v1/items/training-retired",{"is_active":False},200),
        "reactivate-item":("PATCH","/api/v1/items/training-retired",{"is_active":True},200),
        "stock-blocks-deactivation":("PATCH",item,{"is_active":False},409),
        "catalogue-scope-required":("PATCH",item,{"minimum_stock":v["quantity"]},403),
        "create-supplier":("POST","/api/v1/suppliers",{"code":"TRAIN-GARDEN","name":"Training Garden Supplies","contact_name":"Training contact","email":"garden@example.com","payment_terms_days":v["terms"]},201),
        "edit-supplier-terms":("PATCH",supplier,{"contact_name":"Training purchasing contact","payment_terms_days":v["terms"]},200),
        "link-supplier-item":("POST",supplier+"/items",{"item_id":v["amenities"],"supplier_sku":"TRAIN-KIT","last_price":50,"lead_time_days":3,"minimum_order_quantity":2,"is_preferred":True},201),
        "deactivate-unused-supplier":("PATCH","/api/v1/suppliers/training-unused-supplier",{"is_active":False},200),
        "reactivate-supplier":("PATCH","/api/v1/suppliers/training-unused-supplier",{"is_active":True},200),
        "open-orders-block-deactivation":("PATCH",supplier,{"is_active":False},409),
    }[id]


@pytest.mark.parametrize("lesson",LESSONS,ids=lambda lesson:lesson.id)
def test_catalogue_guided_assisted_and_independent_real_outcomes(learner,lesson):
    from training.scenarios import values
    for mode in ("guided","assisted","independent"):
        if mode=="guided": begin(learner,lesson.id,lesson.roles[0])
        else:
            response=learner.post("/api/v1/training/start",json={"lesson_id":lesson.id,"mode":mode})
            assert response.status_code==200,response.text
            learner.headers["X-Training-Attempt"]=response.json()["attempt_id"]
        assert not learner.post("/api/v1/training/check",json={"answer":lesson.answer}).json()["passed"]
        method,path,payload,status=transaction(lesson.id,values(lesson,mode))
        before=learner.get("/api/v1/training/me").json()["attempt"]["mistakes"]
        response=learner.request(method,path,**({"json":payload} if payload is not None else {}))
        assert response.status_code==status,response.text
        if status>=400:
            assert learner.get("/api/v1/training/me").json()["attempt"]["mistakes"]==before
        result=learner.post("/api/v1/training/check",json={"answer":lesson.answer}).json()
        assert result["passed"],result
        assert result["evidence"]["stock_unchanged"]
        assert learner.get("/api/v1/training/me").json()["attempt"]["checkpoint"]==len(lesson.steps)


def test_wrong_conversion_direction_does_not_pass(learner):
    begin(learner,"define-unit-conversion","inventory_manager")
    response=learner.post("/api/v1/items/training-chicken/conversions",json={"from_unit_id":"training-gram","to_unit_id":"training-kg","multiplier":1000})
    assert response.status_code==201,response.text
    result=learner.post("/api/v1/training/check",json={"answer":"1000"}).json()
    assert not result["passed"]
    assert "1 kilogram = 1,000 grams" in result["message"]


def test_catalogue_task_cannot_pass_after_unrelated_stock_posting(learner):
    begin(learner,"edit-item-reorder","inventory_manager")
    assert learner.patch("/api/v1/items/training-chicken",json={"minimum_stock":12}).status_code==200
    assert learner.post("/api/v1/stock/issues",json={"location_id":"training-store","lines":[{"item_id":"training-amenities","quantity":1}]}).status_code==201
    result=learner.post("/api/v1/training/check",json={"answer":"no"}).json()
    assert not result["passed"] and not result["evidence"]["stock_unchanged"]
