from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StaffMealLineIn(BaseModel):
    item_id: str
    quantity: Decimal = Field(gt=0)


class StaffMealCreate(BaseModel):
    meal_name: str = Field(min_length=1, max_length=180)
    meal_period: str | None = Field(default=None, max_length=40)
    servings: int = Field(ge=1, le=500)
    location_id: str
    lines: list[StaffMealLineIn] = Field(min_length=1)
    notes: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=100)


class StaffMealPreviewLine(BaseModel):
    item_id: str
    sku: str
    item_name: str
    quantity: Decimal
    available_quantity: Decimal
    unit_cost: Decimal
    line_cost: Decimal


class StaffMealPreview(BaseModel):
    servings: int
    total_cost: Decimal
    cost_per_serving: Decimal
    lines: list[StaffMealPreviewLine]


class StaffMealLineOut(ORMModel):
    id: str
    line_number: int
    item_id: str
    quantity: Decimal
    unit_cost: Decimal


class StaffMealOut(ORMModel):
    id: str
    meal_number: str
    meal_name: str
    meal_period: str | None
    servings: int
    location_id: str
    notes: str | None
    status: str
    posted_document_id: str
    reversal_document_id: str | None
    created_by_user_id: str
    reversed_by_user_id: str | None
    created_at: datetime
    reversed_at: datetime | None
    lines: list[StaffMealLineOut]
