from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location, StockBalance
from app.models.production import Recipe, RecipeLine
from app.models.user import User
from app.services.controls import add_audit

router = APIRouter(tags=["recipe-costing"])


class RecipeLineUpdate(BaseModel):
    ingredient_item_id: str
    quantity: Decimal = Field(gt=0)
    waste_factor: Decimal = Field(default=0, ge=0, le=1)
    optional: bool = False


class RecipeRevisionCreate(BaseModel):
    name: str | None = Field(default=None, max_length=180)
    yield_quantity: Decimal = Field(gt=0)
    notes: str | None = None
    lines: list[RecipeLineUpdate] = Field(min_length=1)


class MarginScenario(BaseModel):
    location_id: str
    selling_price: Decimal = Field(gt=0)


def fail(status: int, message: str):
    raise HTTPException(status_code=status, detail=message)


def load_recipe(db: Session, recipe_id: str):
    return db.scalar(select(Recipe).where(Recipe.id == recipe_id).options(selectinload(Recipe.lines)))


def ingredient_cost(db: Session, item_id: str, location_id: str) -> Decimal:
    balance = db.scalar(select(StockBalance).where(StockBalance.item_id == item_id, StockBalance.location_id == location_id))
    if balance and Decimal(balance.average_cost) > 0:
        return Decimal(balance.average_cost)
    item = db.get(Item, item_id)
    return Decimal(item.standard_cost or 0) if item else Decimal("0")


def costing_payload(db: Session, recipe: Recipe, location_id: str):
    location = db.get(Location, location_id)
    if not location:
        fail(404, "Location not found")
    item_ids = {line.ingredient_item_id for line in recipe.lines} | {recipe.output_item_id}
    items = {row.id: row for row in db.scalars(select(Item).where(Item.id.in_(item_ids))).all()}
    total = Decimal("0")
    possible: list[Decimal] = []
    lines: list[dict] = []
    for line in recipe.lines:
        required = Decimal(line.quantity) * (Decimal("1") + Decimal(line.waste_factor))
        unit_cost = ingredient_cost(db, line.ingredient_item_id, location_id)
        line_cost = required * unit_cost
        total += line_cost
        balance = db.scalar(select(StockBalance).where(StockBalance.item_id == line.ingredient_item_id, StockBalance.location_id == location_id))
        available = Decimal(balance.quantity) if balance else Decimal("0")
        if not line.optional and required > 0:
            possible.append(available / required * Decimal(recipe.yield_quantity))
        item = items.get(line.ingredient_item_id)
        lines.append({
            "id": line.id,
            "ingredient_item_id": line.ingredient_item_id,
            "sku": item.sku if item else line.ingredient_item_id,
            "item_name": item.name if item else "Unknown item",
            "base_quantity": str(line.quantity),
            "waste_factor": str(line.waste_factor),
            "effective_quantity": str(required),
            "optional": line.optional,
            "available_quantity": str(available),
            "unit_cost": str(unit_cost),
            "line_cost": str(line_cost),
            "cost_share_percent": "0",
        })
    for line in lines:
        line_cost = Decimal(line["line_cost"])
        line["cost_share_percent"] = str((line_cost / total * 100).quantize(Decimal("0.01")) if total else Decimal("0"))
    output = items.get(recipe.output_item_id)
    unit_cost = total / Decimal(recipe.yield_quantity)
    return {
        "recipe": {
            "id": recipe.id,
            "code": recipe.code,
            "name": recipe.name,
            "output_item_id": recipe.output_item_id,
            "output_sku": output.sku if output else recipe.output_item_id,
            "output_name": output.name if output else "Unknown output",
            "yield_quantity": str(recipe.yield_quantity),
            "version": recipe.version,
            "status": recipe.status,
            "notes": recipe.notes,
            "created_by_user_id": recipe.created_by_user_id,
            "approved_by_user_id": recipe.approved_by_user_id,
            "created_at": recipe.created_at.isoformat(),
            "approved_at": recipe.approved_at.isoformat() if recipe.approved_at else None,
        },
        "location": {"id": location.id, "code": location.code, "name": location.name},
        "summary": {
            "ingredient_count": len(lines),
            "total_batch_cost": str(total),
            "cost_per_output_unit": str(unit_cost),
            "available_output_quantity": str(min(possible) if possible else Decimal("0")),
            "missing_cost_lines": sum(1 for line in lines if Decimal(line["unit_cost"]) == 0),
            "constrained_lines": sum(1 for line in lines if not line["optional"] and Decimal(line["available_quantity"]) < Decimal(line["effective_quantity"])),
        },
        "lines": lines,
    }


@router.get("/recipes/costing/workspace")
def recipe_costing_workspace(location_id: str, db: Session = Depends(get_db), _: User = Depends(require_permission("reports.read"))):
    recipes = db.scalars(select(Recipe).options(selectinload(Recipe.lines)).order_by(Recipe.code, Recipe.version.desc())).unique().all()
    rows = []
    for recipe in recipes:
        payload = costing_payload(db, recipe, location_id)
        rows.append({**payload["recipe"], **payload["summary"]})
    return {"location_id": location_id, "recipes": rows}


@router.get("/recipes/{recipe_id}/costing-detail")
def recipe_costing_detail(recipe_id: str, location_id: str, db: Session = Depends(get_db), _: User = Depends(require_permission("reports.read"))):
    recipe = load_recipe(db, recipe_id)
    if not recipe:
        fail(404, "Recipe not found")
    return costing_payload(db, recipe, location_id)


@router.post("/recipes/{recipe_id}/margin-scenario")
def recipe_margin(recipe_id: str, payload: MarginScenario, db: Session = Depends(get_db), _: User = Depends(require_permission("reports.read"))):
    recipe = load_recipe(db, recipe_id)
    if not recipe:
        fail(404, "Recipe not found")
    costing = costing_payload(db, recipe, payload.location_id)
    cost = Decimal(costing["summary"]["cost_per_output_unit"])
    gross_profit = payload.selling_price - cost
    return {
        "selling_price": str(payload.selling_price),
        "cost_per_output_unit": str(cost),
        "gross_profit_per_unit": str(gross_profit),
        "food_cost_percent": str((cost / payload.selling_price * 100).quantize(Decimal("0.01"))),
        "gross_margin_percent": str((gross_profit / payload.selling_price * 100).quantize(Decimal("0.01"))),
    }


@router.post("/recipes/{recipe_id}/revise", status_code=201)
def revise_recipe(recipe_id: str, payload: RecipeRevisionCreate, db: Session = Depends(get_db), user: User = Depends(require_permission("inventory.*"))):
    current = load_recipe(db, recipe_id)
    if not current:
        fail(404, "Recipe not found")
    ids = [line.ingredient_item_id for line in payload.lines]
    if len(ids) != len(set(ids)) or current.output_item_id in ids:
        fail(422, "Ingredients must be unique and cannot equal the output item")
    for item_id in ids:
        if not db.get(Item, item_id):
            fail(422, "Ingredient item not found")
    version = current.version + 1
    base_code = current.code.rsplit("-V", 1)[0] if "-V" in current.code else current.code
    row = Recipe(
        code=f"{base_code}-V{version}",
        name=(payload.name or current.name).strip(),
        output_item_id=current.output_item_id,
        yield_quantity=payload.yield_quantity,
        version=version,
        status="draft",
        notes=payload.notes,
        created_by_user_id=user.id,
    )
    row.lines = [RecipeLine(**line.model_dump()) for line in payload.lines]
    try:
        db.add(row)
        db.flush()
        add_audit(db, actor_user_id=user.id, action="recipe.revised", entity_type="recipe", entity_id=row.id, details={"source_recipe_id": current.id, "source_version": current.version, "new_version": version})
        db.commit()
        revised = load_recipe(db, row.id)
        return {
            "recipe": {
                "id": revised.id,
                "code": revised.code,
                "name": revised.name,
                "output_item_id": revised.output_item_id,
                "yield_quantity": str(revised.yield_quantity),
                "version": revised.version,
                "status": revised.status,
                "notes": revised.notes,
            },
            "source_recipe_id": current.id,
        }
    except IntegrityError:
        db.rollback()
        fail(409, "Recipe revision could not be created")


@router.post("/recipes/{recipe_id}/retire")
def retire_recipe(recipe_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("inventory.*"))):
    recipe = load_recipe(db, recipe_id)
    if not recipe:
        fail(404, "Recipe not found")
    if recipe.status == "retired":
        return {"id": recipe.id, "status": recipe.status}
    recipe.status = "retired"
    add_audit(db, actor_user_id=user.id, action="recipe.retired", entity_type="recipe", entity_id=recipe.id)
    db.commit()
    return {"id": recipe.id, "status": recipe.status}
