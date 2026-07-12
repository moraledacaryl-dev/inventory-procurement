import csv, io
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from app.api.deps import require_permission
from app.core.config import settings
from app.db.session import get_db
from app.models.inventory import CountSession, Item, Location, StockBalance, StockDocument, StockMovement
from app.models.operations import BackupRecord, IntegrationEvent
from app.models.production import ProductionBatch
from app.models.user import User
from app.services.controls import add_audit

router=APIRouter(tags=['final-assurance'])
def now(): return datetime.now(timezone.utc)
def dec(value): return Decimal(str(value or 0))
def aware(value): return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)
MAPPED_ACCOUNTING_EVENTS={'inventory.stock_document.posted','inventory.receipt.posted','inventory.supplier_return.posted','inventory.production.completed','inventory.production.executed','inventory.pos_sale_consumed','inventory.pos_sale_reversed','inventory.master_data.snapshot'}

def snapshot(db:Session):
    db.execute(text('SELECT 1'))
    items={x.id:x for x in db.scalars(select(Item)).all()}; locations={x.id:x for x in db.scalars(select(Location)).all()}
    balance_rows=db.scalars(select(StockBalance)).all()
    movement_rows=db.execute(select(StockMovement.item_id,StockMovement.location_id,func.sum(StockMovement.quantity)).group_by(StockMovement.item_id,StockMovement.location_id)).all()
    ledger={(a,b):dec(c) for a,b,c in movement_rows}; balances={(x.item_id,x.location_id):dec(x.quantity) for x in balance_rows}
    mismatches=[]
    for item_id,location_id in sorted(set(ledger)|set(balances)):
        lq=ledger.get((item_id,location_id),Decimal('0')); bq=balances.get((item_id,location_id),Decimal('0'))
        if lq!=bq:
            item=items.get(item_id); location=locations.get(location_id)
            mismatches.append({'item_id':item_id,'item':item.sku if item else item_id,'location_id':location_id,'location':location.code if location else location_id,'ledger_quantity':str(lq),'balance_quantity':str(bq),'difference':str(bq-lq)})
    negative=[]
    for balance in balance_rows:
        item=items.get(balance.item_id)
        if item and dec(balance.quantity)<0 and not item.allow_negative_stock:
            location=locations.get(balance.location_id)
            negative.append({'item_id':item.id,'item':item.sku,'location_id':balance.location_id,'location':location.code if location else balance.location_id,'quantity':str(balance.quantity)})
    unclassified=[{'item_id':item.id,'sku':item.sku,'name':item.name,'primary_workspace_id':item.primary_workspace_id,'item_type_id':item.item_type_id,'record_class_id':item.record_class_id} for item in items.values() if not item.primary_workspace_id or not item.item_type_id or not item.record_class_id]
    movement_counts=dict(db.execute(select(StockMovement.document_id,func.count()).group_by(StockMovement.document_id)).all())
    empty=[{'id':doc.id,'document_number':doc.document_number,'document_type':doc.document_type} for doc in db.scalars(select(StockDocument).where(StockDocument.status=='posted')).all() if movement_counts.get(doc.id,0)==0]
    events=db.scalars(select(IntegrationEvent)).all(); failed=sum(x.status=='failed' for x in events); dead=sum(x.status=='dead_letter' for x in events); pending=sum(x.status in {'pending','processing'} for x in events)
    unresolved=sum(1 for e in events if e.event_type=='operations.request.submitted' and (e.payload or {}).get('workflow_status','submitted') in {'submitted','accepted'})
    unmapped=sum(1 for e in events if e.destination_system=='accounting' and e.event_type not in MAPPED_ACCOUNTING_EVENTS)
    open_counts=db.scalar(select(func.count()).select_from(CountSession).where(CountSession.status.in_(['open','submitted','pending_approval']))) or 0
    open_production=db.scalar(select(func.count()).select_from(ProductionBatch).where(ProductionBatch.status.in_(['planned','in_progress']))) or 0
    backup=db.scalar(select(BackupRecord).where(BackupRecord.status=='completed').order_by(BackupRecord.created_at.desc()))
    backup_age=(now()-aware(backup.created_at)).total_seconds()/3600 if backup else None
    backup_problem=0 if backup_age is not None and backup_age<=settings.backup_max_age_hours else 1
    controls=[
      ('database','Database connectivity','passed',0),
      ('stock_reconciliation','Stock ledger equals balances','passed' if not mismatches else 'failed',len(mismatches)),
      ('negative_stock','No unauthorized negative stock','passed' if not negative else 'failed',len(negative)),
      ('posted_documents','Posted documents contain movements','passed' if not empty else 'failed',len(empty)),
      ('item_classification','All active items have workspace, item type, and record class','passed' if not unclassified else 'attention',len(unclassified)),
      ('integration_failures','No failed or dead-letter integrations','passed' if failed==0 and dead==0 else 'failed',failed+dead),
      ('accounting_mapping','Accounting events are mapped','passed' if unmapped==0 else 'failed',unmapped),
      ('backup','Completed backup is within freshness limit','passed' if backup_problem==0 else 'failed',backup_problem),
      ('open_counts','No unfinished count sessions','passed' if open_counts==0 else 'attention',open_counts),
      ('open_production','No unfinished production batches','passed' if open_production==0 else 'attention',open_production),
      ('operational_requests','No unresolved Staff/Command Center requests','passed' if unresolved==0 else 'attention',unresolved),
    ]
    checks=[{'key':k,'label':label,'status':status,'count':count} for k,label,status,count in controls]
    failed_checks=sum(x['status']=='failed' for x in checks); attention=sum(x['status']=='attention' for x in checks)
    return {'generated_at':now().isoformat(),'overall_status':'critical' if failed_checks else 'attention' if attention else 'healthy','summary':{'failed_checks':failed_checks,'attention_checks':attention,'stock_mismatches':len(mismatches),'negative_stock_violations':len(negative),'empty_posted_documents':len(empty),'unclassified_items':len(unclassified),'pending_integrations':pending,'failed_integrations':failed,'dead_letter_integrations':dead,'unmapped_accounting_events':unmapped,'unresolved_operational_requests':unresolved,'open_count_sessions':open_counts,'open_production_batches':open_production},'checks':checks,'stock_mismatches':mismatches[:200],'negative_stock':negative[:200],'empty_documents':empty[:200],'unclassified_items':unclassified[:500],'latest_backup_at':backup.created_at.isoformat() if backup else None,'backup_age_hours':backup_age}

@router.get('/reports/final-assurance')
def report(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))): return snapshot(db)

@router.post('/reports/final-assurance/record')
def record(db:Session=Depends(get_db),user:User=Depends(require_permission('reports.read'))):
    data=snapshot(db); add_audit(db,actor_user_id=user.id,action='assurance.snapshot_recorded',entity_type='system_assurance',entity_id=data['generated_at'],details={'overall_status':data['overall_status'],'summary':data['summary'],'checks':data['checks']}); db.commit(); return data

@router.get('/reports/final-assurance.csv')
def export(db:Session=Depends(get_db),_:User=Depends(require_permission('reports.read'))):
    data=snapshot(db); out=io.StringIO(); writer=csv.writer(out); writer.writerow(['generated_at',data['generated_at']]); writer.writerow(['overall_status',data['overall_status']]); writer.writerow([]); writer.writerow(['check','label','status','count'])
    for check in data['checks']: writer.writerow([check['key'],check['label'],check['status'],check['count']])
    writer.writerow([]); writer.writerow(['item','location','ledger_quantity','balance_quantity','difference'])
    for row in data['stock_mismatches']: writer.writerow([row['item'],row['location'],row['ledger_quantity'],row['balance_quantity'],row['difference']])
    writer.writerow([]); writer.writerow(['unclassified_sku','name','workspace_id','item_type_id','record_class_id'])
    for row in data['unclassified_items']: writer.writerow([row['sku'],row['name'],row['primary_workspace_id'],row['item_type_id'],row['record_class_id']])
    return StreamingResponse(iter([out.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=hidden-oasis-final-assurance.csv'})
