from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class ORMModel(BaseModel): model_config=ConfigDict(from_attributes=True)
class BarcodeCreate(BaseModel): barcode:str=Field(min_length=3,max_length=100); barcode_type:str='EAN13'; is_primary:bool=False
class BarcodeOut(ORMModel): id:str; item_id:str; barcode:str; barcode_type:str; is_primary:bool
class ConversionCreate(BaseModel): from_unit_id:str; to_unit_id:str; multiplier:Decimal=Field(gt=0)
class ConversionOut(ORMModel): id:str; item_id:str; from_unit_id:str; to_unit_id:str; multiplier:Decimal; is_active:bool
class LocationSettingCreate(BaseModel):
    item_id:str; location_id:str; minimum_stock:Decimal=Field(default=0,ge=0); reorder_quantity:Decimal=Field(default=0,ge=0); maximum_stock:Decimal|None=Field(default=None,ge=0); preferred_supplier_id:str|None=None; cycle_count_days:int=Field(default=30,ge=1,le=3650)
class LocationSettingOut(ORMModel):
    id:str; item_id:str; location_id:str; minimum_stock:Decimal; reorder_quantity:Decimal; maximum_stock:Decimal|None; preferred_supplier_id:str|None; cycle_count_days:int; is_active:bool
class LotCreate(BaseModel): item_id:str; lot_number:str=Field(min_length=1,max_length=100); manufactured_date:date|None=None; expiry_date:date|None=None; supplier_id:str|None=None
class LotOut(ORMModel): id:str; item_id:str; lot_number:str; manufactured_date:date|None; expiry_date:date|None; supplier_id:str|None; status:str; created_at:datetime
class LotTransactionCreate(BaseModel):
    lot_id:str; location_id:str; quantity:Decimal=Field(gt=0); unit_cost:Decimal=Field(default=0,ge=0); transaction_type:str=Field(pattern='^(receipt|issue|waste|damage)$'); reason:str|None=None; idempotency_key:str|None=None
class LotBalanceOut(BaseModel): lot_id:str; item_id:str; lot_number:str; location_id:str; quantity:Decimal; expiry_date:date|None; status:str
class ReservationCreate(BaseModel): item_id:str; location_id:str; quantity:Decimal=Field(gt=0); reference_type:str; reference_id:str; expires_at:datetime|None=None
class ReservationOut(ORMModel): id:str; reservation_number:str; item_id:str; location_id:str; quantity:Decimal; reference_type:str; reference_id:str; status:str; expires_at:datetime|None; created_at:datetime
class AvailabilityOut(BaseModel): item_id:str; location_id:str; physical_quantity:Decimal; reserved_quantity:Decimal; available_quantity:Decimal
class TransferLineIn(BaseModel): item_id:str; quantity:Decimal=Field(gt=0)
class TransferOrderCreate(BaseModel): source_location_id:str; destination_location_id:str; notes:str|None=None; lines:list[TransferLineIn]=Field(min_length=1)
class TransferOrderLineOut(ORMModel): id:str; item_id:str; quantity:Decimal
class TransferOrderOut(ORMModel):
    id:str; transfer_number:str; source_location_id:str; destination_location_id:str; status:str; notes:str|None; created_at:datetime; dispatched_at:datetime|None; received_at:datetime|None; stock_document_id:str|None; lines:list[TransferOrderLineOut]
class CycleScheduleCreate(BaseModel): item_id:str; location_id:str; frequency_days:int=Field(default=30,ge=1,le=3650); next_count_date:date
class CycleScheduleOut(ORMModel): id:str; item_id:str; location_id:str; frequency_days:int; next_count_date:date; last_count_date:date|None; is_active:bool
class ValuationRow(BaseModel): item_id:str; location_id:str; quantity:Decimal; average_cost:Decimal; inventory_value:Decimal
class AgingRow(BaseModel): item_id:str; location_id:str; last_movement_at:datetime|None; days_since_movement:int|None; quantity:Decimal; classification:str
class ExpiryRow(BaseModel): lot_id:str; item_id:str; lot_number:str; location_id:str; quantity:Decimal; expiry_date:date; days_to_expiry:int; status:str
class WasteSummaryRow(BaseModel): item_id:str; quantity:Decimal; value:Decimal
