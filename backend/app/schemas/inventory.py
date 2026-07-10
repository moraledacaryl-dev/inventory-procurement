from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict

class ORMModel(BaseModel): model_config = ConfigDict(from_attributes=True)
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120); description: str | None = None
class CategoryOut(ORMModel):
    id: str; name: str; description: str | None; is_active: bool
class UnitCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20); name: str = Field(min_length=1, max_length=80); precision: int = Field(default=3, ge=0, le=6)
class UnitOut(ORMModel):
    id: str; code: str; name: str; precision: int; is_active: bool
class LocationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40); name: str = Field(min_length=1, max_length=120); location_type: str = "storeroom"; parent_id: str | None = None
class LocationOut(ORMModel):
    id: str; code: str; name: str; location_type: str; parent_id: str | None; is_active: bool
class ItemCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=80); name: str = Field(min_length=1, max_length=180); description: str | None = None; category_id: str; base_unit_id: str; track_stock: bool = True; allow_negative_stock: bool = False; minimum_stock: Decimal = Field(default=0, ge=0); standard_cost: Decimal = Field(default=0, ge=0)
class ItemOut(ORMModel):
    id: str; sku: str; name: str; description: str | None; category_id: str; base_unit_id: str; track_stock: bool; allow_negative_stock: bool; minimum_stock: Decimal; standard_cost: Decimal; is_active: bool
class StockLineIn(BaseModel):
    item_id: str; quantity: Decimal = Field(gt=0); unit_cost: Decimal = Field(default=0, ge=0); reason: str | None = None
class ReceiptCreate(BaseModel):
    location_id: str; lines: list[StockLineIn] = Field(min_length=1); reference: str | None = None; notes: str | None = None; idempotency_key: str | None = None
class IssueCreate(ReceiptCreate): pass
class TransferCreate(BaseModel):
    source_location_id: str; destination_location_id: str; lines: list[StockLineIn] = Field(min_length=1); reference: str | None = None; notes: str | None = None; idempotency_key: str | None = None
class AdjustmentLineIn(BaseModel):
    item_id: str; quantity_delta: Decimal; unit_cost: Decimal = Field(default=0, ge=0); reason: str = Field(min_length=1)
class AdjustmentCreate(BaseModel):
    location_id: str; lines: list[AdjustmentLineIn] = Field(min_length=1); reference: str | None = None; notes: str | None = None; idempotency_key: str | None = None
class MovementOut(ORMModel):
    id: str; line_number: int; item_id: str; location_id: str; quantity: Decimal; unit_cost: Decimal; reason: str | None; created_at: datetime
class DocumentOut(ORMModel):
    id: str; document_number: str; document_type: str; status: str; reference: str | None; notes: str | None; posted_at: datetime; movements: list[MovementOut]
class BalanceOut(ORMModel):
    item_id: str; location_id: str; quantity: Decimal; average_cost: Decimal; updated_at: datetime
class CountCreate(BaseModel):
    location_id: str; notes: str | None = None
class CountEntry(BaseModel):
    item_id: str; counted_quantity: Decimal = Field(ge=0); note: str | None = None
class CountSubmit(BaseModel): lines: list[CountEntry] = Field(min_length=1)
class CountLineOut(ORMModel):
    id: str; item_id: str; system_quantity: Decimal; counted_quantity: Decimal | None; note: str | None
class CountOut(ORMModel):
    id: str; count_number: str; location_id: str; status: str; notes: str | None; created_at: datetime; posted_document_id: str | None; lines: list[CountLineOut]
