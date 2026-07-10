from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class ORMModel(BaseModel): model_config=ConfigDict(from_attributes=True)
class RecipeLineIn(BaseModel): ingredient_item_id:str; quantity:Decimal=Field(gt=0); waste_factor:Decimal=Field(default=0,ge=0,le=1); optional:bool=False
class RecipeCreate(BaseModel): code:str=Field(min_length=1,max_length=60); name:str=Field(min_length=1,max_length=180); output_item_id:str; yield_quantity:Decimal=Field(gt=0); notes:str|None=None; lines:list[RecipeLineIn]=Field(min_length=1)
class RecipeLineOut(ORMModel): id:str; ingredient_item_id:str; quantity:Decimal; waste_factor:Decimal; optional:bool
class RecipeOut(ORMModel): id:str; code:str; name:str; output_item_id:str; yield_quantity:Decimal; version:int; status:str; notes:str|None; created_by_user_id:str; approved_by_user_id:str|None; created_at:datetime; approved_at:datetime|None; lines:list[RecipeLineOut]
class RecipeCostOut(BaseModel): recipe_id:str; yield_quantity:Decimal; total_cost:Decimal; cost_per_output_unit:Decimal; available_output_quantity:Decimal
class ProductionCreate(BaseModel): recipe_id:str; location_id:str; planned_quantity:Decimal=Field(gt=0); notes:str|None=None
class ProductionComplete(BaseModel): actual_quantity:Decimal=Field(gt=0)
class ProductionOut(ORMModel): id:str; batch_number:str; recipe_id:str; location_id:str; planned_quantity:Decimal; actual_quantity:Decimal|None; status:str; notes:str|None; stock_document_id:str|None; created_at:datetime; completed_at:datetime|None
class PosMappingCreate(BaseModel): pos_system:str='hidden-oasis-pos'; external_product_id:str; recipe_id:str; location_id:str
class PosMappingOut(ORMModel): id:str; pos_system:str; external_product_id:str; recipe_id:str; location_id:str; is_active:bool
class PosSaleLine(BaseModel): external_product_id:str; quantity:Decimal=Field(gt=0)
class PosSaleEventIn(BaseModel): external_event_id:str; external_sale_id:str; pos_system:str='hidden-oasis-pos'; event_type:str=Field(pattern='^(sale_completed|sale_voided|sale_refunded)$'); lines:list[PosSaleLine]=Field(min_length=1)
class PosSaleEventOut(ORMModel): id:str; external_event_id:str; event_type:str; external_sale_id:str; pos_system:str; status:str; stock_document_id:str|None; reversal_of_event_id:str|None; error:str|None; processed_at:datetime
class ReconciliationOut(BaseModel): pending_events:int; failed_events:int; dead_letter_events:int; unprocessed_pos_events:int; latest_pos_event_at:datetime|None
