"""Read-only migration assessment against actual source import jobs/documents."""
import csv, io
from decimal import Decimal
from sqlalchemy import select
from app.models import Item, Supplier, StockBalance, StockDocument, AuditLog, UnitOfMeasure, Category
from app.models.readiness import DataImportJob
from training.csv_fixtures import practice_csv


def matches_input(db,row,lesson,v):
    from app.api.routes.readiness import validate_import
    fixture=practice_csv(lesson.id,v)
    expected,errors=validate_import(fixture['import_type'],list(csv.DictReader(io.StringIO(fixture['content']))),db)
    return row.filename==fixture['filename'] and row.import_type==fixture['import_type'] and row.summary.get('row_count')==len(expected) and row.summary.get('rows')==expected and row.errors==errors


def recover_migration_checkpoint(db,lesson,v):
    rows=list(db.scalars(select(DataImportJob).where(DataImportJob.created_by_user_id==v['actor'])))
    if len(rows)==1 and matches_input(db,rows[0],lesson,v) and rows[0].status in {'validated','invalid'}:return 3
    return 0


def verify_migration(db,lesson,v,actions):
    fixture=practice_csv(lesson.id,v)
    rows=list(db.scalars(select(DataImportJob).where(DataImportJob.created_by_user_id==v['actor'])))
    docs=list(db.scalars(select(StockDocument).where(StockDocument.posted_by_user_id==v['actor'])))
    def balance(item):return db.scalar(select(StockBalance.quantity).where(StockBalance.item_id==item,StockBalance.location_id==v['store'])) or Decimal(0)
    unchanged=not docs and balance(v['chicken'])==v['base'] and balance(v['amenities'])==v['base'] and balance(v['alfredo'])==0
    ok=False
    if len(rows)==1:
        row=rows[0]
        header_ok=matches_input(db,row,lesson,v)
        if lesson.id=='import-item-catalogue':
            item=db.scalar(select(Item).where(Item.sku=='TRAIN-MILK'))
            ok=header_ok and row.status=='applied' and row.applied_at is not None and row.summary.get('created')==1 and item and item.name=='Training milk cartons' and item.minimum_stock==12 and item.standard_cost==75 and db.get(UnitOfMeasure,item.base_unit_id).code=='TRAIN-EACH' and db.get(Category,item.category_id).name=='Training drinks' and not db.scalar(select(StockBalance.id).where(StockBalance.item_id==item.id))
        elif lesson.id=='import-supplier-catalogue':
            supplier=db.scalar(select(Supplier).where(Supplier.code=='TRAIN-FARM'))
            ok=header_ok and row.status=='applied' and row.applied_at is not None and row.summary.get('created')==1 and supplier and supplier.name=='Training Farm Supplies' and supplier.contact_name=='Training contact' and supplier.email=='farm@example.com' and supplier.payment_terms_days==21
        elif lesson.id=='reject-invalid-csv':
            first=(row.summary.get('rows') or [{}])[0]
            ok=header_ok and row.status=='invalid' and row.applied_at is None and len(row.errors)==1 and row.errors[0]['line']==3 and 'duplicate SKU' in row.errors[0]['error'] and first.get('sku')=='TRAIN-MILK' and first.get('name')=='Training milk cartons' and Decimal(first.get('standard_cost',0))==75 and not db.scalar(select(Item.id).where(Item.sku=='TRAIN-MILK'))
        elif lesson.id=='refuse-duplicate-opening-import':
            normalized=row.summary.get('rows') or []
            ok=header_ok and row.status=='validated' and row.applied_at is None and not row.errors and len(normalized)==1 and normalized[0].get('sku')=='TRAIN-CHICKEN' and normalized[0].get('location')=='TRAIN-STORE' and Decimal(normalized[0].get('quantity',0))==v['quantity'] and Decimal(normalized[0].get('average_cost',0))==200 and any(action.get('path')==f'/api/v1/migration/imports/{row.id}/apply' and action.get('status')==409 for action in actions)
        elif lesson.id=='import-initial-balances':
            unchanged=balance(v['amenities'])==0 and balance(v['alfredo'])==0
            ok=header_ok and row.status=='applied' and row.applied_at is not None and len(docs)==1 and docs[0].document_type=='opening_balance' and docs[0].reference==row.id and len(docs[0].movements)==1 and docs[0].movements[0].item_id==v['chicken'] and docs[0].movements[0].location_id==v['store'] and docs[0].movements[0].quantity==v['quantity'] and docs[0].movements[0].unit_cost==200 and balance(v['chicken'])==v['quantity'] and len(list(db.scalars(select(StockDocument))))==1
        if lesson.id!='reject-invalid-csv' and lesson.id!='refuse-duplicate-opening-import':
            ok=ok and db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==v['actor'],AuditLog.action=='migration.import_applied',AuditLog.entity_id==row.id)) is not None
        ok=ok and db.scalar(select(AuditLog.id).where(AuditLog.actor_user_id==v['actor'],AuditLog.action=='migration.import_validated',AuditLog.entity_id==row.id)) is not None
    passed=bool(ok and unchanged)
    return passed,{'workflow':lesson.workflow,'passed':passed,'stock_integrity':bool(unchanged),'correction':lesson.situation.format(**v)+' Check the complete validation result and actual job status. Do not repeat an applied opening or bypass an invalid row. Reset this practice if an unintended import was already applied.'}
