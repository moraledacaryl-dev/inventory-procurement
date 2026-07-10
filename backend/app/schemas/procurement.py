from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

class ORMModel(BaseModel): model_config = ConfigDict(from_attributes=True)
class SupplierCreate(BaseModel):
    code:str=Field(min_length=1,max_length=40); name:str=Field(min_length=1,max_length=180); contact_name:str|None=None; email:EmailStr|None=None; phone:str|None=None; address:str|None=None; payment_terms_days:int=Field(default=0,ge=0); tax_id:str|None=None
class SupplierOut(ORMModel):
    id:str; code:str; name:str; contact_name:str|None; email:str|None; phone:str|None; address:str|None; payment_terms_days:int; tax_id:str|None; is_active:bool
class SupplierItemCreate(BaseModel):
    item_id:str; supplier_sku:str|None=None; last_price:Decimal=Field(default=0,ge=0); lead_time_days:int=Field(default=0,ge=0); minimum_order_quantity:Decimal=Field(default=1,gt=0); is_preferred:bool=False
class SupplierItemOut(ORMModel):
    id:str; supplier_id:str; item_id:str; supplier_sku:str|None; last_price:Decimal; lead_time_days:int; minimum_order_quantity:Decimal; is_preferred:bool
class PRLineIn(BaseModel):
    item_id:str; quantity:Decimal=Field(gt=0); estimated_unit_cost:Decimal=Field(default=0,ge=0); notes:str|None=None
class PRCreate(BaseModel):
    department:str=Field(min_length=1,max_length=100); needed_by:date|None=None; justification:str|None=None; lines:list[PRLineIn]=Field(min_length=1)
class PRLineOut(ORMModel):
    id:str; item_id:str; quantity:Decimal; estimated_unit_cost:Decimal; notes:str|None
class PROut(ORMModel):
    id:str; requisition_number:str; department:str; needed_by:date|None; justification:str|None; status:str; requested_by_user_id:str; approved_by_user_id:str|None; approved_at:datetime|None; created_at:datetime; lines:list[PRLineOut]
class QuoteLineIn(BaseModel):
    item_id:str; quantity:Decimal=Field(gt=0); unit_price:Decimal=Field(gt=0)
class QuoteCreate(BaseModel):
    requisition_id:str; supplier_id:str; valid_until:date|None=None; delivery_days:int=Field(default=0,ge=0); payment_terms_days:int=Field(default=0,ge=0); notes:str|None=None; lines:list[QuoteLineIn]=Field(min_length=1)
class QuoteLineOut(ORMModel):
    id:str; item_id:str; quantity:Decimal; unit_price:Decimal
class QuoteOut(ORMModel):
    id:str; quotation_number:str; requisition_id:str; supplier_id:str; valid_until:date|None; delivery_days:int; payment_terms_days:int; notes:str|None; status:str; created_at:datetime; lines:list[QuoteLineOut]
class POLineIn(BaseModel):
    item_id:str; ordered_quantity:Decimal=Field(gt=0); unit_price:Decimal=Field(gt=0)
class POCreate(BaseModel):
    supplier_id:str; delivery_location_id:str; requisition_id:str|None=None; quotation_id:str|None=None; expected_delivery_date:date|None=None; notes:str|None=None; lines:list[POLineIn]=Field(min_length=1)
class POLineOut(ORMModel):
    id:str; item_id:str; ordered_quantity:Decimal; received_quantity:Decimal; returned_quantity:Decimal; unit_price:Decimal
class POOut(ORMModel):
    id:str; purchase_order_number:str; supplier_id:str; requisition_id:str|None; quotation_id:str|None; delivery_location_id:str; expected_delivery_date:date|None; status:str; notes:str|None; created_by_user_id:str; approved_by_user_id:str|None; approved_at:datetime|None; created_at:datetime; lines:list[POLineOut]
class ReceiptLineIn(BaseModel):
    purchase_order_line_id:str; received_quantity:Decimal=Field(gt=0); accepted_quantity:Decimal=Field(ge=0); rejected_quantity:Decimal=Field(default=0,ge=0)
    @model_validator(mode='after')
    def total_matches(self):
        if self.accepted_quantity+self.rejected_quantity!=self.received_quantity: raise ValueError('Accepted plus rejected must equal received')
        return self
class GoodsReceiptCreate(BaseModel):
    delivery_reference:str|None=None; notes:str|None=None; idempotency_key:str|None=None; lines:list[ReceiptLineIn]=Field(min_length=1)
class GoodsReceiptLineOut(ORMModel):
    id:str; purchase_order_line_id:str; item_id:str; received_quantity:Decimal; accepted_quantity:Decimal; rejected_quantity:Decimal; unit_cost:Decimal
class GoodsReceiptOut(ORMModel):
    id:str; goods_receipt_number:str; purchase_order_id:str; stock_document_id:str; delivery_reference:str|None; received_by_user_id:str; received_at:datetime; notes:str|None; lines:list[GoodsReceiptLineOut]
class ReturnLineIn(BaseModel):
    purchase_order_line_id:str; quantity:Decimal=Field(gt=0)
class ReturnCreate(BaseModel):
    reason:str=Field(min_length=1); idempotency_key:str|None=None; lines:list[ReturnLineIn]=Field(min_length=1)
class ReturnOut(ORMModel):
    id:str; return_number:str; purchase_order_id:str; stock_document_id:str; reason:str; created_by_user_id:str; created_at:datetime
class QuoteComparison(BaseModel):
    quotation_id:str; quotation_number:str; supplier_id:str; total:Decimal; delivery_days:int; payment_terms_days:int; status:str
