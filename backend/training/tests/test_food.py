"""Food authoring/governance and exact stock-correction checks."""
import pytest
from conftest import begin
from training.food_lessons import LESSONS


def perform(client,lesson,v):
    id=lesson.id
    if id=="staff-meal-shortage":
        payload={"meal_name":"Training shortage check","location_id":v["store"],"servings":4,"lines":[{"item_id":v["chicken"],"quantity":v["meal_shortage"]}]}
        assert client.post("/api/v1/staff-meals/preview",json=payload).status_code==409
        return client.post("/api/v1/staff-meals",json=payload)
    if id=="create-governed-recipe":return client.post("/api/v1/recipes",json={"code":"TRAIN-TEST-RECIPE","name":"Training chicken portion","output_item_id":v["alfredo"],"yield_quantity":1,"notes":v["reference"],"lines":[{"ingredient_item_id":v["chicken"],"quantity":"0.25","waste_factor":"0.1","optional":False}]})
    if id in {"approve-colleague-recipe","recipe-self-approval","retire-obsolete-recipe"}:return client.post("/api/v1/recipes/training-recipe/"+("retire" if id=="retire-obsolete-recipe" else "approve"))
    if id=="plan-production-batch":return client.post("/api/v1/production-batches",json={"recipe_id":v["recipe"],"location_id":v["store"],"planned_quantity":v["quantity"],"notes":v["reference"]})
    if id=="reverse-duplicate-staff-meal":
        meal=client.get("/api/v1/staff-meals").json()[0]
        return client.post(f"/api/v1/staff-meals/{meal['id']}/reverse")
    if id=="create-menu-with-modifier":return client.post("/api/v1/fnb/menu",json={"name":"Training garden plate","display_name":"Training garden plate","category":"Training meals","prep_station":"kitchen","pricing_role":"standard","is_active":True,"pos_visible":True,"variants":[{"name":"Regular","price":250}],"modifier_groups":[{"id":"training-sauce","label":"Sauce","mode":"single","options":[{"label":"Extra sauce","price_delta":20}]}]})
    if id=="map-pos-product":return client.post("/api/v1/pos-mappings",json={"pos_system":"hidden-oasis-pos","external_product_id":"TRAIN-POS-PLATE","recipe_id":v["recipe"],"location_id":v["store"]})
    if id=="disable-stale-pos-mapping":return client.post("/api/v1/pos-mappings/training-pos-map/deactivate")


@pytest.mark.parametrize("lesson",LESSONS,ids=lambda lesson:lesson.id)
def test_food_real_outcomes_all_modes(learner,lesson):
    from training.scenarios import values
    for mode in ("guided","assisted","independent"):
        if mode=="guided":begin(learner,lesson.id,lesson.roles[0])
        else:
            response=learner.post("/api/v1/training/start",json={"lesson_id":lesson.id,"mode":mode})
            assert response.status_code==200,response.text
            learner.headers["X-Training-Attempt"]=response.json()["attempt_id"]
        assert not learner.post("/api/v1/training/check",json={"answer":"no"}).json()["passed"]
        response=perform(learner,lesson,values(lesson,mode))
        expected=409 if lesson.id in {"recipe-self-approval","staff-meal-shortage"} else 201 if lesson.id in {"create-governed-recipe","plan-production-batch","create-menu-with-modifier","map-pos-product"} else 200
        assert response.status_code==expected,response.text
        result=learner.post("/api/v1/training/check",json={"answer":"no"}).json()
        assert result["passed"],result
        assert learner.get("/api/v1/training/me").json()["attempt"]["checkpoint"]==len(lesson.steps)


def test_recipe_wrong_base_unit_quantity_cannot_pass(learner):
    begin(learner,"create-governed-recipe","inventory_manager")
    response=learner.post("/api/v1/recipes",json={"code":"TRAIN-TEST-RECIPE","name":"Training chicken portion","output_item_id":"training-alfredo","yield_quantity":1,"notes":"TRAIN-CREATE-GOVERNED-RECIPE-GUIDED","lines":[{"ingredient_item_id":"training-chicken","quantity":250,"waste_factor":"0.1"}]})
    assert response.status_code==201,response.text
    result=learner.post("/api/v1/training/check",json={"answer":"no"}).json()
    assert not result["passed"]
    assert "0.25 kg" in result["message"]


def test_staff_meal_reversal_is_idempotent_and_retains_original(learner):
    from training.curriculum import BY_ID
    from training.scenarios import values
    lesson=BY_ID["reverse-duplicate-staff-meal"]
    begin(learner,lesson.id,"inventory_manager")
    first=perform(learner,lesson,values(lesson,"guided"))
    second=perform(learner,lesson,values(lesson,"guided"))
    assert first.status_code==second.status_code==200
    assert first.json()["reversal_document_id"]==second.json()["reversal_document_id"]
    assert learner.post("/api/v1/training/check",json={"answer":"no"}).json()["passed"]
