"""pass 5 maintenance, purchase treatment, and accounting mappings

Revision ID: 0013_maintenance
Revises: 0012_fixed_assets
"""
from alembic import op
import sqlalchemy as sa

revision='0013_maintenance'
down_revision='0012_fixed_assets'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('accounting_mappings',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('event_key',sa.String(100),nullable=False),
        sa.Column('dimension_id',sa.String(36),sa.ForeignKey('operational_dimensions.id')),
        sa.Column('debit_account',sa.String(80),nullable=False),sa.Column('credit_account',sa.String(80),nullable=False),
        sa.Column('description',sa.String(240)),sa.Column('is_active',sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('event_key','dimension_id',name='uq_accounting_mapping_event_dimension'))
    op.create_index('ix_accounting_mappings_event_key','accounting_mappings',['event_key'])
    op.create_table('maintenance_plans',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('code',sa.String(60),nullable=False,unique=True),
        sa.Column('name',sa.String(160),nullable=False),sa.Column('asset_id',sa.String(36),sa.ForeignKey('fixed_assets.id'),nullable=False),
        sa.Column('interval_days',sa.Integer(),nullable=False,server_default='30'),sa.Column('checklist',sa.Text()),
        sa.Column('assigned_user_id',sa.String(36),sa.ForeignKey('users.id')),sa.Column('next_due_date',sa.Date(),nullable=False),
        sa.Column('is_active',sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_maintenance_plans_asset_id','maintenance_plans',['asset_id'])
    op.create_index('ix_maintenance_plans_next_due_date','maintenance_plans',['next_due_date'])
    op.create_table('maintenance_work_orders',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('work_order_number',sa.String(60),nullable=False,unique=True),
        sa.Column('asset_id',sa.String(36),sa.ForeignKey('fixed_assets.id'),nullable=False),sa.Column('plan_id',sa.String(36),sa.ForeignKey('maintenance_plans.id')),
        sa.Column('title',sa.String(180),nullable=False),sa.Column('description',sa.Text()),sa.Column('priority',sa.String(20),nullable=False,server_default='normal'),
        sa.Column('status',sa.String(30),nullable=False,server_default='open'),sa.Column('assigned_user_id',sa.String(36),sa.ForeignKey('users.id')),
        sa.Column('contractor',sa.String(180)),sa.Column('scheduled_date',sa.Date()),sa.Column('started_at',sa.DateTime(timezone=True)),sa.Column('completed_at',sa.DateTime(timezone=True)),
        sa.Column('labor_cost',sa.Numeric(18,2),nullable=False,server_default='0'),sa.Column('external_cost',sa.Numeric(18,2),nullable=False,server_default='0'),
        sa.Column('downtime_hours',sa.Numeric(12,2),nullable=False,server_default='0'),sa.Column('completion_notes',sa.Text()),
        sa.Column('created_by_user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    for c in ('asset_id','plan_id','status'): op.create_index(f'ix_maintenance_work_orders_{c}','maintenance_work_orders',[c])
    op.create_table('maintenance_work_order_parts',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('work_order_id',sa.String(36),sa.ForeignKey('maintenance_work_orders.id',ondelete='CASCADE'),nullable=False),
        sa.Column('item_id',sa.String(36),sa.ForeignKey('items.id'),nullable=False),sa.Column('quantity',sa.Numeric(18,6),nullable=False),sa.Column('unit_cost',sa.Numeric(18,4),nullable=False,server_default='0'))
    op.create_index('ix_maintenance_work_order_parts_work_order_id','maintenance_work_order_parts',['work_order_id'])
    op.create_table('purchase_line_treatments',
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('source_type',sa.String(30),nullable=False),sa.Column('source_line_id',sa.String(36),nullable=False),
        sa.Column('treatment',sa.String(30),nullable=False),sa.Column('workspace_id',sa.String(36),sa.ForeignKey('operational_dimensions.id')),
        sa.Column('department_id',sa.String(36),sa.ForeignKey('operational_dimensions.id')),sa.Column('cost_center_id',sa.String(36),sa.ForeignKey('operational_dimensions.id')),
        sa.Column('intended_location_id',sa.String(36),sa.ForeignKey('locations.id')),sa.Column('asset_class_id',sa.String(36),sa.ForeignKey('operational_dimensions.id')),
        sa.Column('accounting_mapping_id',sa.String(36),sa.ForeignKey('accounting_mappings.id')),sa.Column('project_reference',sa.String(120)),sa.Column('notes',sa.Text()),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint('source_type','source_line_id',name='uq_purchase_line_treatment_source'))
    op.create_index('ix_purchase_line_treatments_source','purchase_line_treatments',['source_type','source_line_id'])

def downgrade():
    op.drop_table('purchase_line_treatments'); op.drop_table('maintenance_work_order_parts'); op.drop_table('maintenance_work_orders'); op.drop_table('maintenance_plans'); op.drop_table('accounting_mappings')