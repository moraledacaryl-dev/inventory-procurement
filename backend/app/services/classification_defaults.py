from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.classification import OperationalDimension


DEFAULT_DIMENSIONS = [
    {"id": "f19a0bb1-d94a-5bd4-aefd-e2e6051548fb", "dimension_type": "workspace", "code": "fnb", "name": "F&B", "behavior_key": "fnb", "sort_order": 10},
    {"id": "d9d5b27f-b988-514e-b8dd-d5b0cce35035", "dimension_type": "workspace", "code": "hotel", "name": "Hotel", "behavior_key": "hotel", "sort_order": 20},
    {"id": "a1ac8d31-96fc-51ac-9211-d6366f6737dd", "dimension_type": "workspace", "code": "assets-property", "name": "Assets & Property", "behavior_key": "assets", "sort_order": 30},
    {"id": "f0cbfd3a-85ce-545e-8856-aa5e85027d1a", "dimension_type": "workspace", "code": "shared-operations", "name": "Shared Operations", "behavior_key": "shared", "sort_order": 40},
    {"id": "056d0a00-d73f-5579-aaff-176b6f6bd16e", "dimension_type": "record_class", "code": "consumable", "name": "Consumable inventory", "behavior_key": "stock_consumable", "sort_order": 10},
    {"id": "23c7af9e-de1b-598f-9406-443c2b88c937", "dimension_type": "record_class", "code": "reusable-property", "name": "Reusable operating property", "behavior_key": "reusable_property", "sort_order": 20},
    {"id": "2628221d-0583-55ae-bc59-828b5aca1c71", "dimension_type": "record_class", "code": "fixed-asset", "name": "Fixed asset", "behavior_key": "fixed_asset", "sort_order": 30},
    {"id": "f4e313dd-c7d6-554c-bb8f-66622f43eaed", "dimension_type": "record_class", "code": "service-expense", "name": "Non-stock expense or service", "behavior_key": "service_expense", "sort_order": 40},
    {"id": "ac69261c-c552-5779-a80f-8d2e72dcb602", "dimension_type": "item_type", "code": "ingredient", "name": "Ingredient", "behavior_key": "ingredient", "parent_id": "056d0a00-d73f-5579-aaff-176b6f6bd16e", "workspace_id": "f19a0bb1-d94a-5bd4-aefd-e2e6051548fb", "sort_order": 10},
    {"id": "20c126f7-76c1-593a-886f-86cb30154cf5", "dimension_type": "item_type", "code": "beverage-ingredient", "name": "Beverage ingredient", "behavior_key": "ingredient", "parent_id": "056d0a00-d73f-5579-aaff-176b6f6bd16e", "workspace_id": "f19a0bb1-d94a-5bd4-aefd-e2e6051548fb", "sort_order": 20},
    {"id": "6b9566d5-fe47-5bbb-9afa-ebfdc2dde0ab", "dimension_type": "item_type", "code": "prep-item", "name": "Prep or sub-recipe item", "behavior_key": "recipe_output", "parent_id": "056d0a00-d73f-5579-aaff-176b6f6bd16e", "workspace_id": "f19a0bb1-d94a-5bd4-aefd-e2e6051548fb", "sort_order": 30},
    {"id": "bc3b124d-b37a-5ca3-ac34-c15d450a318a", "dimension_type": "item_type", "code": "finished-fnb-product", "name": "Finished F&B product", "behavior_key": "recipe_output", "parent_id": "056d0a00-d73f-5579-aaff-176b6f6bd16e", "workspace_id": "f19a0bb1-d94a-5bd4-aefd-e2e6051548fb", "sort_order": 40},
    {"id": "d4f9f1ad-6448-529d-a11e-4fbf38c37535", "dimension_type": "item_type", "code": "recipe-packaging", "name": "Recipe packaging", "behavior_key": "recipe_packaging", "parent_id": "056d0a00-d73f-5579-aaff-176b6f6bd16e", "workspace_id": "f19a0bb1-d94a-5bd4-aefd-e2e6051548fb", "sort_order": 50},
    {"id": "d23cccac-3a05-5d51-b61e-60f37b0776e5", "dimension_type": "item_type", "code": "guest-amenity", "name": "Guest amenity", "behavior_key": "hotel_consumable", "parent_id": "056d0a00-d73f-5579-aaff-176b6f6bd16e", "workspace_id": "d9d5b27f-b988-514e-b8dd-d5b0cce35035", "sort_order": 10},
    {"id": "745a580c-c962-59e1-8fe4-9443026b5681", "dimension_type": "item_type", "code": "housekeeping-supply", "name": "Housekeeping supply", "behavior_key": "hotel_consumable", "parent_id": "056d0a00-d73f-5579-aaff-176b6f6bd16e", "workspace_id": "d9d5b27f-b988-514e-b8dd-d5b0cce35035", "sort_order": 20},
    {"id": "6cd1c0fa-7878-5198-91f7-8c05785e7043", "dimension_type": "item_type", "code": "linen", "name": "Linen", "behavior_key": "reusable_property", "parent_id": "23c7af9e-de1b-598f-9406-443c2b88c937", "workspace_id": "d9d5b27f-b988-514e-b8dd-d5b0cce35035", "sort_order": 30},
    {"id": "8fe51424-2c6c-53e8-ac3f-b0b603064b4c", "dimension_type": "item_type", "code": "maintenance-supply", "name": "Maintenance supply", "behavior_key": "stock_consumable", "parent_id": "056d0a00-d73f-5579-aaff-176b6f6bd16e", "workspace_id": "f0cbfd3a-85ce-545e-8856-aa5e85027d1a", "sort_order": 10},
    {"id": "edc0841b-341c-5c86-9c06-ce7f5ede33e6", "dimension_type": "item_type", "code": "equipment", "name": "Equipment", "behavior_key": "fixed_asset", "parent_id": "2628221d-0583-55ae-bc59-828b5aca1c71", "workspace_id": "a1ac8d31-96fc-51ac-9211-d6366f6737dd", "sort_order": 10},
    {"id": "7ef58b61-c15f-51d2-b015-b459683fe3fb", "dimension_type": "item_type", "code": "general-consumable", "name": "General consumable", "behavior_key": "stock_consumable", "parent_id": "056d0a00-d73f-5579-aaff-176b6f6bd16e", "workspace_id": "f0cbfd3a-85ce-545e-8856-aa5e85027d1a", "sort_order": 20},
    {"id": "94ff9486-85b7-534c-b05a-fdbf73e17d2b", "dimension_type": "item_type", "code": "service", "name": "Service or direct expense", "behavior_key": "service_expense", "parent_id": "f4e313dd-c7d6-554c-bb8f-66622f43eaed", "workspace_id": "f0cbfd3a-85ce-545e-8856-aa5e85027d1a", "sort_order": 30},
    # Editable condition buckets used by reusable property and linen circulation.
    {"id": "10000000-0000-5000-8000-000000000001", "dimension_type": "condition_status", "code": "available", "name": "Available / clean", "behavior_key": "available", "sort_order": 10},
    {"id": "10000000-0000-5000-8000-000000000002", "dimension_type": "condition_status", "code": "in-use", "name": "In use", "behavior_key": "in_use", "sort_order": 20},
    {"id": "10000000-0000-5000-8000-000000000003", "dimension_type": "condition_status", "code": "in-laundry", "name": "In laundry", "behavior_key": "laundry", "sort_order": 30},
    {"id": "10000000-0000-5000-8000-000000000004", "dimension_type": "condition_status", "code": "in-repair", "name": "In repair", "behavior_key": "repair", "sort_order": 40},
    {"id": "10000000-0000-5000-8000-000000000005", "dimension_type": "condition_status", "code": "damaged", "name": "Damaged", "behavior_key": "damaged", "sort_order": 50},
    {"id": "10000000-0000-5000-8000-000000000006", "dimension_type": "condition_status", "code": "lost", "name": "Lost", "behavior_key": "lost", "sort_order": 60},
    {"id": "10000000-0000-5000-8000-000000000007", "dimension_type": "condition_status", "code": "retired", "name": "Retired", "behavior_key": "retired", "sort_order": 70},
    # Editable movement reasons; behavior stays protected while labels may change.
    {"id": "20000000-0000-5000-8000-000000000001", "dimension_type": "movement_reason", "code": "receipt", "name": "New receipt", "behavior_key": "receipt", "sort_order": 10},
    {"id": "20000000-0000-5000-8000-000000000002", "dimension_type": "movement_reason", "code": "issue", "name": "Issue to room or department", "behavior_key": "issue", "sort_order": 20},
    {"id": "20000000-0000-5000-8000-000000000003", "dimension_type": "movement_reason", "code": "laundry", "name": "Laundry circulation", "behavior_key": "laundry", "sort_order": 30},
    {"id": "20000000-0000-5000-8000-000000000004", "dimension_type": "movement_reason", "code": "repair", "name": "Repair circulation", "behavior_key": "repair", "sort_order": 40},
    {"id": "20000000-0000-5000-8000-000000000005", "dimension_type": "movement_reason", "code": "damage", "name": "Damage", "behavior_key": "damage", "sort_order": 50},
    {"id": "20000000-0000-5000-8000-000000000006", "dimension_type": "movement_reason", "code": "loss", "name": "Loss", "behavior_key": "loss", "sort_order": 60},
    {"id": "20000000-0000-5000-8000-000000000007", "dimension_type": "movement_reason", "code": "retirement", "name": "Retirement", "behavior_key": "retirement", "sort_order": 70},
]


def ensure_operating_structure_defaults(db: Session) -> int:
    """Insert missing system defaults without overwriting administrator edits."""
    existing = set(db.scalars(select(OperationalDimension.id)).all())
    inserted = 0
    for definition in DEFAULT_DIMENSIONS:
        if definition["id"] in existing:
            continue
        db.add(OperationalDimension(**definition, is_system=True, is_active=True, settings={}))
        inserted += 1
    if inserted:
        db.flush()
    return inserted
