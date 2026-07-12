import csv, io
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.deps import require_permission
from app.db.session import get_db
from app.models.inventory import CountSession, Item, Location, StockBalance, StockDocument, StockMovement
from app.models.operations import BackupRecord, IntegrationEvent
from app.models.production import ProductionBatch
from app.models.user import User
from app.services.controls import add_audit

router=APIRouter(tags=['final-assurance'])
def now(): return datetime.now(timezone.utc)
def dec(value): return Decimal(str(value or 0))

def snapshot(db:Session):
    balance_rows=db.scalars(select(StockBalance)).all()
    movement_rows=db.execute(select(StockMovement.item_id,StockMovement.location_id,func.sum(StockMovement.quantity)).group_by(StockMovement.item_id,StockMovement.location_id)).all()
    ledger={(a,b):dec(c) for a,b,c in movement_rows}; balances={(x.item_id,x.location_id):dec(x.quantity) for x in balance_rows}
    mismatches=[]
    for item_id,location_id in sorted(set(ledger)|set(balances)):
        lq=ledger.get((item_id,location_id),Decimal('0')); bq=balances.get((item_id,location_id),Decimal('0'))
        if lq!=bq:
            item=db.get(Item,item_id); location=db.get(Location,location_id)
            mismatches.append({'item_id':item_id,'item':item.sku if item else item_id,'location_id':location_id,'location':location.code if location else location_id,'ledger_quantity':str(lq),'balance_quantity':str(bq),'difference':str(bq-lq)})
    negative=[]
    for balance in balance_rows:
        item=db.get(Item,balance.item_id)
        if item and dec(balance.quantity)<0 and not item.allow_negative_stock:
            location=db.get(Location,balance.location_id)
            negative.append({'item_id':item.id,'item':item.sku,'location_id':balance.location_id,'location':location.code if location else balance.location_id,'quantity':str(balance.quantity)})
    movement_counts=dict(db.execute(select(StockMovement.document_id,func.count()).group_by(StockMovement.document_id)).all())
    empty=[]
    for doc in db.scalars(select(StockDocument).where(StockDocument.status=='posted')).all():
        if movement_counts.get(doc.id,0)==0: empty.append({'id':doc.id,'document_number':doc.document_number,'document_type':doc.document_type})
    counts=dict(db.execute(select(IntegrationEvent.status,func.count()).group_by(IntegrationEvent.status)).all())
    failed=counts.get('failed',0); dead=counts.get('dead_letter',0); pending=counts.get('pending',0)+counts.get('processing',0)
    ops=db.scalars(select(IntegrationEvent).where(IntegrationEvent.event_type=='operations.request.submitted')).all()
    unresolved=sum(1 for e in ops if (e.payload or {}).get('workflow_status','submitted') in {'submitted','accepted'})
    mapped=['inventory.stock_document.posted','inventory.receipt.posted','inventory.supplier_return.posted','inventory.production.completed','inventory.production.executed','inventory.pos_sale_consumed','inventory.pos_sale_reversed','inventory.master_data.snapshot']
    unmapped=db.scalar(select(func.count()).select_from(IntegrationEvent).where(IntegrationEvent.destination_system=='accounting',IntegrationEvent.event_type.not_in(mapped))) or 0
    open_counts=db.scalar(select(func.count()).select_from(CountSession).where(CountSession.status.in_(['open','submitted','pending_approval']))) or 0
    open_production=db.scalar(select(func.count()).select_from(ProductionBatch).where(ProductionBatch.status.in_(['planned','in_progress']))) or 0
    backup=db.scalar(select(BackupRecord).order_by(BackupRecord.created_at.desc()))
    checks=[
      {'key':'stock_reconciliation','label':'Stock ledger equals balances','status':'passed' if not mismatches else 'failed','count':len(mismatches)},
      {'key':'negative_stock','label':'No unauthorized negative stock','status':'passed' if not negative else 'failed','count':len(negative)},
      {'key':'posted_documents','label':'Posted documents contain movements','status':'passed' if not empty else 'failed','count':len(empty)},
      {'key':'integration_failures','label':'No failed or dead-letter integrations','status':'passed' if failed==0 and dead==0 else 'failed','count':failed+dead},
      {'key':'accounting_mapping','label':'Accounting events are mapped','status':'passed' if unmapped==0 else 'failed','count':unmapped},
      {'key':'backup','label':'At least one backup record exists','status':'passed' if backup else 'attention','count':0 if backup else 1},
    ]
    failed_checks=sum(x['status']=='failed' for x in checks); attention=sum(x['status']=='attention' for x in checks)
    return {'generated_at':now().isoformat(),'overall_status':'critical' if failed_checks else 'attention' if attention else 'healthy','summary':{'failed_checks':failed_checks,'attention_checks':attention,'stock_mismatches':len(mismatches),'negative_stock_violations':len(negative),'empty_posted_documents':len(empty),'pending_integrations':pending,'failed_integrations':failed,'dead_letter_integrations':dead,'unmapped_accounting_events':unmapped,'unresolved_operational_requests':unresolved,'open_count_sessions':open_counts,'open_production_batches':open_production},'checks':checks,'stock_mismatches':mismatches[:200],'negative_stock':negative[:200],'empty_documents':empty[:200],'latest_backup_at':backup.created_at.isoformat() if backup else None}

@router.get('/reports/final-assurance')
def report(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))): return snapshot(db)

@router.post('/reports/final-assurance/record')
def record(db:Session=Depends(get_db),user:User=Depends(require_permission('reports.read'))):
    data=snapshot(db); add_audit(db,actor_user_id=user.id,action='assurance.snapshot_recorded',entity_type='system_assurance',entity_id=data['generated_at'],details={'overall_status':data['overall_status'],'summary':data['summary']}); db.commit(); return data

@router.get('/reports/final-assurance.csv')
def export(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    data=snapshot(db); out=io.StringIO(); writer=csv.writer(out); writer.writerow(['generated_at',data['generated_at']]); writer.writerow(['overall_status',data['overall_status']]); writer.writerow([]); writer.writerow(['check','label','status','count'])
    for check in data['checks']: writer.writerow([check['key'],check['label'],check['status'],check['count']])
    writer.writerow([]); writer.writerow(['item','location','ledger_quantity','balance_quantity','difference'])
    for row in data['stock_mismatches']: writer.writerow([row['item'],row['location'],row['ledger_quantity'],row['balance_quantity'],row['difference']])
    return StreamingResponse(iter([out.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=hidden-oasis-final-assurance.csv'})
