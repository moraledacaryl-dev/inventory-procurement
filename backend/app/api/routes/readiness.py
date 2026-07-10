import csv, io
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.api.deps import require_permission
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.models.inventory import Category, UnitOfMeasure, Item, Location, StockBalance, StockMovement
from app.models.procurement import Supplier, PurchaseRequisition, PurchaseOrder, GoodsReceipt
from app.models.production import ProductionBatch
from app.models.operations import BackupRecord, IntegrationEvent
from app.models.readiness import DataImportJob, AcceptanceRun
from app.schemas.readiness import *
from app.services.controls import add_audit, next_document_number
from app.services.inventory import InventoryError, post_document

router=APIRouter(tags=['production-readiness'])
def now(): return datetime.now(timezone.utc)
def fail(code:int,message:str): raise HTTPException(code,message)
def aware(value:datetime)->datetime: return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
def decimal(value,default='0'):
    try: return Decimal(str(value or default))
    except Exception: raise ValueError(f'Invalid decimal value: {value}')

def validate_import(import_type:str,rows:list[dict],db:Session):
    normalized=[]; errors=[]; seen=set()
    for line,row in enumerate(rows,2):
        try:
            if import_type=='items':
                sku=(row.get('sku') or '').upper().strip(); name=(row.get('name') or '').strip(); category=(row.get('category') or '').strip(); unit=(row.get('unit') or '').upper().strip()
                if not sku or not name or not category or not unit: raise ValueError('sku, name, category, and unit are required')
                if sku in seen: raise ValueError('duplicate SKU in file')
                seen.add(sku); normalized.append({'sku':sku,'name':name,'category':category,'unit':unit,'minimum_stock':str(decimal(row.get('minimum_stock'))),'standard_cost':str(decimal(row.get('standard_cost')))})
            elif import_type=='suppliers':
                code=(row.get('code') or '').upper().strip(); name=(row.get('name') or '').strip()
                if not code or not name: raise ValueError('code and name are required')
                if code in seen: raise ValueError('duplicate supplier code in file')
                seen.add(code); normalized.append({'code':code,'name':name,'contact_name':(row.get('contact_name') or '').strip() or None,'email':(row.get('email') or '').strip() or None,'phone':(row.get('phone') or '').strip() or None,'payment_terms_days':int(row.get('payment_terms_days') or 0)})
            elif import_type=='opening_balances':
                sku=(row.get('sku') or '').upper().strip(); location=(row.get('location') or '').upper().strip(); quantity=decimal(row.get('quantity')); average_cost=decimal(row.get('average_cost'))
                if not sku or not location: raise ValueError('sku and location are required')
                if quantity<0 or average_cost<0: raise ValueError('quantity and average_cost cannot be negative')
                key=f'{sku}:{location}'
                if key in seen: raise ValueError('duplicate item/location opening balance')
                seen.add(key); normalized.append({'sku':sku,'location':location,'quantity':str(quantity),'average_cost':str(average_cost)})
            else: raise ValueError('Unsupported import type')
        except Exception as exc: errors.append({'line':line,'error':str(exc)})
    return normalized,errors

@router.post('/migration/imports/{import_type}/validate',response_model=ImportValidationOut,status_code=201)
async def validate_csv(import_type:str,file:UploadFile=File(...),db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    if not file.filename or not file.filename.lower().endswith('.csv'): fail(422,'CSV file required')
    try: content=(await file.read()).decode('utf-8-sig')
    except UnicodeDecodeError: fail(422,'CSV must be UTF-8 encoded')
    rows=list(csv.DictReader(io.StringIO(content))); normalized,errors=validate_import(import_type,rows,db)
    job=DataImportJob(import_type=import_type,filename=file.filename,status='invalid' if errors else 'validated',summary={'rows':normalized,'row_count':len(normalized)},errors=errors,created_by_user_id=user.id); db.add(job); db.flush(); add_audit(db,actor_user_id=user.id,action='migration.import_validated',entity_type='data_import_job',entity_id=job.id,details={'type':import_type,'rows':len(normalized),'errors':len(errors)}); db.commit()
    return ImportValidationOut(job_id=job.id,import_type=import_type,filename=file.filename,status=job.status,summary={'row_count':len(normalized)},errors=errors)

@router.get('/migration/imports',response_model=list[ImportJobOut])
def import_jobs(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))): return db.scalars(select(DataImportJob).order_by(DataImportJob.created_at.desc()).limit(100)).all()

@router.post('/migration/imports/{job_id}/apply',response_model=ImportApplyOut)
def apply_import(job_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    job=db.scalar(select(DataImportJob).where(DataImportJob.id==job_id).with_for_update())
    if not job: fail(404,'Import job not found')
    if job.status!='validated': fail(409,'Only validated imports can be applied')
    rows=job.summary.get('rows',[]); created=updated=0
    try:
        if job.import_type=='items':
            for row in rows:
                category=db.scalar(select(Category).where(func.lower(Category.name)==row['category'].lower()))
                if not category: category=Category(name=row['category']); db.add(category); db.flush()
                unit=db.scalar(select(UnitOfMeasure).where(UnitOfMeasure.code==row['unit']))
                if not unit: unit=UnitOfMeasure(code=row['unit'],name=row['unit']); db.add(unit); db.flush()
                item=db.scalar(select(Item).where(Item.sku==row['sku']))
                if item:
                    item.name=row['name']; item.category_id=category.id; item.base_unit_id=unit.id; item.minimum_stock=Decimal(row['minimum_stock']); item.standard_cost=Decimal(row['standard_cost']); updated+=1
                else: db.add(Item(sku=row['sku'],name=row['name'],category_id=category.id,base_unit_id=unit.id,minimum_stock=Decimal(row['minimum_stock']),standard_cost=Decimal(row['standard_cost']))); created+=1
        elif job.import_type=='suppliers':
            for row in rows:
                supplier=db.scalar(select(Supplier).where(Supplier.code==row['code']))
                if supplier:
                    for key in ['name','contact_name','email','phone','payment_terms_days']: setattr(supplier,key,row[key])
                    updated+=1
                else: db.add(Supplier(**row)); created+=1
        elif job.import_type=='opening_balances':
            if db.scalar(select(func.count()).select_from(StockMovement))>0: fail(409,'Opening balances can only be applied before stock movements exist')
            entries=[]
            for row in rows:
                item=db.scalar(select(Item).where(Item.sku==row['sku'])); location=db.scalar(select(Location).where(Location.code==row['location']))
                if not item or not location: fail(422,f"Unknown item or location: {row['sku']} / {row['location']}")
                if Decimal(row['quantity'])>0: entries.append({'item_id':item.id,'location_id':location.id,'quantity':Decimal(row['quantity']),'unit_cost':Decimal(row['average_cost']),'reason':'opening balance'})
            post_document(db,kind='opening_balance',actor_id=user.id,entries=entries,reference=job.id,idempotency_key=f'opening-balance:{job.id}',commit=False,allow_empty=True); created=len(entries)
        job.status='applied'; job.applied_at=now(); job.summary={**job.summary,'created':created,'updated':updated}; add_audit(db,actor_user_id=user.id,action='migration.import_applied',entity_type='data_import_job',entity_id=job.id,details={'created':created,'updated':updated}); db.commit(); return ImportApplyOut(job_id=job.id,status=job.status,summary={'created':created,'updated':updated},applied_at=job.applied_at)
    except InventoryError as exc: db.rollback(); fail(409,str(exc))
    except IntegrityError as exc: db.rollback(); fail(409,f'Import could not be applied: {exc.orig}')

@router.post('/requisitions/{document_id}/cancel')
def cancel_requisition(document_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('procurement.*'))):
    row=db.get(PurchaseRequisition,document_id)
    if not row: fail(404,'Requisition not found')
    if row.status not in {'submitted','approved'}: fail(409,'Requisition cannot be cancelled')
    if db.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.requisition_id==row.id,PurchaseOrder.status.not_in(['cancelled'])))>0: fail(409,'Requisition has an active purchase order')
    row.status='cancelled'; add_audit(db,actor_user_id=user.id,action='requisition.cancelled',entity_type='purchase_requisition',entity_id=row.id); db.commit(); return {'id':row.id,'status':row.status}

@router.post('/purchase-orders/{document_id}/cancel')
def cancel_po(document_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('procurement.*'))):
    row=db.get(PurchaseOrder,document_id)
    if not row: fail(404,'Purchase order not found')
    if row.status not in {'draft','approved'}: fail(409,'Purchase order cannot be cancelled')
    if db.scalar(select(func.count()).select_from(GoodsReceipt).where(GoodsReceipt.purchase_order_id==row.id))>0: fail(409,'Purchase order already has receipts')
    row.status='cancelled'; add_audit(db,actor_user_id=user.id,action='purchase_order.cancelled',entity_type='purchase_order',entity_id=row.id); db.commit(); return {'id':row.id,'status':row.status}

@router.post('/production-batches/{document_id}/cancel')
def cancel_batch(document_id:str,db:Session=Depends(get_db),user:User=Depends(require_permission('inventory.*'))):
    row=db.get(ProductionBatch,document_id)
    if not row: fail(404,'Production batch not found')
    if row.status!='planned': fail(409,'Only planned batches can be cancelled')
    row.status='cancelled'; add_audit(db,actor_user_id=user.id,action='production.cancelled',entity_type='production_batch',entity_id=row.id); db.commit(); return {'id':row.id,'status':row.status}

@router.get('/print/purchase-orders/{document_id}',response_model=PrintableDocumentOut)
def print_po(document_id:str,db:Session=Depends(get_db),_:User=Depends(require_permission('procurement.read'))):
    row=db.scalar(select(PurchaseOrder).where(PurchaseOrder.id==document_id).options(selectinload(PurchaseOrder.lines)))
    if not row: fail(404,'Purchase order not found')
    supplier=db.get(Supplier,row.supplier_id); location=db.get(Location,row.delivery_location_id); lines=[]; total=Decimal('0')
    for line in row.lines:
        item=db.get(Item,line.item_id); amount=Decimal(line.ordered_quantity)*Decimal(line.unit_price); total+=amount; lines.append({'sku':item.sku,'item':item.name,'quantity':str(line.ordered_quantity),'unit_price':str(line.unit_price),'amount':str(amount)})
    return PrintableDocumentOut(document_type='purchase_order',document_number=row.purchase_order_number,status=row.status,title='PURCHASE ORDER',header={'supplier':supplier.name,'delivery_location':location.name,'expected_delivery_date':str(row.expected_delivery_date or ''),'notes':row.notes or ''},lines=lines,totals={'grand_total':str(total)})

@router.get('/print/goods-receipts/{document_id}',response_model=PrintableDocumentOut)
def print_grn(document_id:str,db:Session=Depends(get_db),_:User=Depends(require_permission('receiving.read'))):
    row=db.scalar(select(GoodsReceipt).where(GoodsReceipt.id==document_id).options(selectinload(GoodsReceipt.lines)))
    if not row: fail(404,'Goods receipt not found')
    po=db.get(PurchaseOrder,row.purchase_order_id); lines=[]
    for line in row.lines:
        item=db.get(Item,line.item_id); lines.append({'sku':item.sku,'item':item.name,'received':str(line.received_quantity),'accepted':str(line.accepted_quantity),'rejected':str(line.rejected_quantity),'unit_cost':str(line.unit_cost)})
    return PrintableDocumentOut(document_type='goods_receipt',document_number=row.goods_receipt_number,status='posted',title='GOODS RECEIPT NOTE',header={'purchase_order':po.purchase_order_number,'delivery_reference':row.delivery_reference or '','received_at':row.received_at.isoformat(),'notes':row.notes or ''},lines=lines,totals={'accepted_quantity':str(sum((Decimal(x.accepted_quantity) for x in row.lines),Decimal('0'))),'rejected_quantity':str(sum((Decimal(x.rejected_quantity) for x in row.lines),Decimal('0')))})

@router.get('/deployment/status',response_model=DeploymentStatusOut)
def deployment_status(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    db.execute(text('SELECT 1')); pending=db.scalar(select(func.count()).select_from(IntegrationEvent).where(IntegrationEvent.status.in_(['pending','processing','failed']))) or 0; dead=db.scalar(select(func.count()).select_from(IntegrationEvent).where(IntegrationEvent.status=='dead_letter')) or 0; backup=db.scalar(select(BackupRecord).order_by(BackupRecord.created_at.desc()))
    age=(now()-aware(backup.created_at)).total_seconds()/3600 if backup else None; status='healthy' if dead==0 and pending<100 and age is not None and age<=settings.backup_max_age_hours else 'attention'
    return DeploymentStatusOut(environment=settings.app_env,database='ok',migrations='head',worker_backlog=pending,dead_letter_events=dead,latest_backup_at=backup.created_at if backup else None,backup_age_hours=age,status=status)

@router.post('/acceptance-runs',response_model=AcceptanceRunOut,status_code=201)
def run_acceptance(p:AcceptanceRunCreate,db:Session=Depends(get_db),user:User=Depends(require_permission('reports.read'))):
    run=AcceptanceRun(run_number=next_document_number(db,'UAT'),environment=p.environment,notes=p.notes,created_by_user_id=user.id); db.add(run); db.flush(); checks={}
    try:
        db.execute(text('SELECT 1')); checks['database']={'passed':True}; mismatches=[]
        movement_rows=db.execute(select(StockMovement.item_id,StockMovement.location_id,func.sum(StockMovement.quantity)).group_by(StockMovement.item_id,StockMovement.location_id)).all(); movement_map={(a,b):Decimal(c or 0) for a,b,c in movement_rows}
        for balance in db.scalars(select(StockBalance)).all():
            ledger=movement_map.get((balance.item_id,balance.location_id),Decimal('0'))
            if ledger!=Decimal(balance.quantity): mismatches.append({'item_id':balance.item_id,'location_id':balance.location_id,'ledger':str(ledger),'balance':str(balance.quantity)})
        checks['stock_reconciliation']={'passed':not mismatches,'mismatches':mismatches[:50]}
        dead=db.scalar(select(func.count()).select_from(IntegrationEvent).where(IntegrationEvent.status=='dead_letter')) or 0; checks['integrations']={'passed':dead==0,'dead_letter_events':dead}
        backup=db.scalar(select(BackupRecord).order_by(BackupRecord.created_at.desc())); checks['backup']={'passed':backup is not None,'latest':backup.created_at.isoformat() if backup else None}
        run.results=checks; run.status='passed' if all(x.get('passed') for x in checks.values()) else 'failed'; run.completed_at=now(); add_audit(db,actor_user_id=user.id,action='acceptance.completed',entity_type='acceptance_run',entity_id=run.id,details={'status':run.status}); db.commit(); db.refresh(run); return run
    except Exception as exc:
        run.status='failed'; run.results={**checks,'error':str(exc)}; run.completed_at=now(); db.commit(); db.refresh(run); return run

@router.get('/acceptance-runs',response_model=list[AcceptanceRunOut])
def acceptance_runs(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))): return db.scalars(select(AcceptanceRun).order_by(AcceptanceRun.created_at.desc()).limit(50)).all()
