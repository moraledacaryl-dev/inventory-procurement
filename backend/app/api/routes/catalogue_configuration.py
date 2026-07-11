from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import Item, Location, UnitOfMeasure
from app.models.inventory_operations import ItemBarcode, ItemLocationSetting, UnitConversion
from app.models.procurement import Supplier, SupplierItem
from app.models.user import User
from app.services.controls import add_audit

router = APIRouter(tags=["catalogue-configuration"])


class SupplierItemUpdate(BaseModel):
    supplier_sku: str | None = Field(default=None, max_length=100)
    last_price: Decimal = Field(default=0, ge=0)
    lead_time_days: int = Field(default=0, ge=0, le=3650)
    minimum_order_quantity: Decimal = Field(default=1, gt=0)
    is_preferred: bool = False


class BarcodeUpdate(BaseModel):
    barcode: str = Field(min_length=3, max_length=100)
    barcode_type: str = Field(default="EAN13", max_length=30)
    is_primary: bool = False


class ConversionUpdate(BaseModel):
    from_unit_id: str
    to_unit_id: str
    multiplier: Decimal = Field(gt=0)
    is_active: bool = True


class LocationSettingUpdate(BaseModel):
    minimum_stock: Decimal = Field(default=0, ge=0)
    reorder_quantity: Decimal = Field(default=0, ge=0)
    maximum_stock: Decimal | None = Field(default=None, ge=0)
    preferred_supplier_id: str | None = None
    cycle_count_days: int = Field(default=30, ge=1, le=3650)
    is_active: bool = True


def fail(status: int, message: str):
    raise HTTPException(status, message)


def commit(db: Session, action: str, entity_type: str, entity_id: str, user: User, details: dict):
    try:
        add_audit(db, actor_user_id=user.id, action=action, entity_type=entity_type, entity_id=entity_id, details=details)
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, "Duplicate or invalid configuration")


@router.get("/items/{item_id}/configuration")
def item_configuration(
    item_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("items.read")),
):
    item = db.get(Item, item_id)
    if not item:
        fail(404, "Item not found")

    units = {row.id: row for row in db.scalars(select(UnitOfMeasure)).all()}
    suppliers = {row.id: row for row in db.scalars(select(Supplier)).all()}
    locations = {row.id: row for row in db.scalars(select(Location)).all()}
    barcodes = db.scalars(select(ItemBarcode).where(ItemBarcode.item_id == item_id).order_by(ItemBarcode.is_primary.desc(), ItemBarcode.barcode)).all()
    conversions = db.scalars(select(UnitConversion).where(UnitConversion.item_id == item_id).order_by(UnitConversion.is_active.desc())).all()
    supplier_items = db.scalars(select(SupplierItem).where(SupplierItem.item_id == item_id).order_by(SupplierItem.is_preferred.desc())).all()
    settings = db.scalars(select(ItemLocationSetting).where(ItemLocationSetting.item_id == item_id).order_by(ItemLocationSetting.is_active.desc())).all()

    return {
        "barcodes": [
            {"id": row.id, "barcode": row.barcode, "barcode_type": row.barcode_type, "is_primary": row.is_primary}
            for row in barcodes
        ],
        "conversions": [
            {
                "id": row.id,
                "from_unit_id": row.from_unit_id,
                "from_unit_code": units[row.from_unit_id].code,
                "to_unit_id": row.to_unit_id,
                "to_unit_code": units[row.to_unit_id].code,
                "multiplier": str(row.multiplier),
                "is_active": row.is_active,
            }
            for row in conversions
        ],
        "supplier_items": [
            {
                "id": row.id,
                "supplier_id": row.supplier_id,
                "supplier_code": suppliers[row.supplier_id].code,
                "supplier_name": suppliers[row.supplier_id].name,
                "supplier_sku": row.supplier_sku,
                "last_price": str(row.last_price),
                "lead_time_days": row.lead_time_days,
                "minimum_order_quantity": str(row.minimum_order_quantity),
                "is_preferred": row.is_preferred,
            }
            for row in supplier_items
        ],
        "location_settings": [
            {
                "id": row.id,
                "location_id": row.location_id,
                "location_code": locations[row.location_id].code,
                "location_name": locations[row.location_id].name,
                "minimum_stock": str(row.minimum_stock),
                "reorder_quantity": str(row.reorder_quantity),
                "maximum_stock": str(row.maximum_stock) if row.maximum_stock is not None else None,
                "preferred_supplier_id": row.preferred_supplier_id,
                "preferred_supplier_name": suppliers[row.preferred_supplier_id].name if row.preferred_supplier_id else None,
                "cycle_count_days": row.cycle_count_days,
                "is_active": row.is_active,
            }
            for row in settings
        ],
    }


@router.patch("/supplier-items/{link_id}")
def update_supplier_item(link_id: str, payload: SupplierItemUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("suppliers.*"))):
    row = db.get(SupplierItem, link_id)
    if not row:
        fail(404, "Supplier-item link not found")
    if payload.is_preferred:
        for old in db.scalars(select(SupplierItem).where(SupplierItem.item_id == row.item_id, SupplierItem.is_preferred.is_(True), SupplierItem.id != row.id)).all():
            old.is_preferred = False
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    commit(db, "supplier.item_updated", "supplier_item", row.id, user, {"preferred": row.is_preferred})
    db.refresh(row)
    return row


@router.delete("/supplier-items/{link_id}", status_code=204)
def delete_supplier_item(link_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("suppliers.*"))):
    row = db.get(SupplierItem, link_id)
    if not row:
        fail(404, "Supplier-item link not found")
    item_id, supplier_id = row.item_id, row.supplier_id
    db.delete(row)
    commit(db, "supplier.item_unlinked", "supplier_item", link_id, user, {"item_id": item_id, "supplier_id": supplier_id})


@router.patch("/items/{item_id}/barcodes/{barcode_id}")
def update_barcode(item_id: str, barcode_id: str, payload: BarcodeUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("items.*"))):
    row = db.get(ItemBarcode, barcode_id)
    if not row or row.item_id != item_id:
        fail(404, "Barcode not found")
    if payload.is_primary:
        for old in db.scalars(select(ItemBarcode).where(ItemBarcode.item_id == item_id, ItemBarcode.is_primary.is_(True), ItemBarcode.id != row.id)).all():
            old.is_primary = False
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    commit(db, "item.barcode_updated", "item", item_id, user, {"barcode_id": barcode_id})
    db.refresh(row)
    return row


@router.delete("/items/{item_id}/barcodes/{barcode_id}", status_code=204)
def delete_barcode(item_id: str, barcode_id: str, db: Session = Depends(get_db), user: User = Depends(require_permission("items.*"))):
    row = db.get(ItemBarcode, barcode_id)
    if not row or row.item_id != item_id:
        fail(404, "Barcode not found")
    db.delete(row)
    commit(db, "item.barcode_removed", "item", item_id, user, {"barcode_id": barcode_id})


@router.patch("/items/{item_id}/conversions/{conversion_id}")
def update_conversion(item_id: str, conversion_id: str, payload: ConversionUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("items.*"))):
    row = db.get(UnitConversion, conversion_id)
    if not row or row.item_id != item_id:
        fail(404, "Conversion not found")
    if payload.from_unit_id == payload.to_unit_id:
        fail(422, "Conversion units must differ")
    if not db.get(UnitOfMeasure, payload.from_unit_id) or not db.get(UnitOfMeasure, payload.to_unit_id):
        fail(422, "Unit not found")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    commit(db, "item.conversion_updated", "item", item_id, user, {"conversion_id": conversion_id})
    db.refresh(row)
    return row


@router.patch("/item-location-settings/{setting_id}")
def update_location_setting(setting_id: str, payload: LocationSettingUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission("inventory.*"))):
    row = db.get(ItemLocationSetting, setting_id)
    if not row:
        fail(404, "Item-location setting not found")
    if payload.maximum_stock is not None and payload.maximum_stock < payload.minimum_stock:
        fail(422, "Maximum stock cannot be below minimum stock")
    if payload.preferred_supplier_id and not db.get(Supplier, payload.preferred_supplier_id):
        fail(422, "Supplier not found")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    commit(db, "inventory.location_setting_updated", "item_location_setting", row.id, user, {"item_id": row.item_id, "location_id": row.location_id})
    db.refresh(row)
    return row
