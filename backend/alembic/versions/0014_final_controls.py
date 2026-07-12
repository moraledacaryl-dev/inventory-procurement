"""pass 6 final controls

Revision ID: 0014_final_controls
Revises: 0013_maintenance
"""
from alembic import op
import sqlalchemy as sa

revision='0014_final_controls'
down_revision='0013_maintenance'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table(
        'operational_access_scopes',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('workspace_id',sa.String(36),sa.ForeignKey('operational_dimensions.id')),
        sa.Column('department_id',sa.String(36),sa.ForeignKey('operational_dimensions.id')),
        sa.Column('location_id',sa.String(36),sa.ForeignKey('locations.id')),
        sa.Column('record_class_id',sa.String(36),sa.ForeignKey('operational_dimensions.id')),
        sa.Column('approval_limit',sa.Numeric(18,2),nullable=False,server_default='0'),
        sa.Column('is_active',sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('user_id','workspace_id','department_id','location_id','record_class_id',name='uq_operational_access_scope'),
    )
    for column in ('user_id','workspace_id','department_id','location_id','record_class_id'):
        op.create_index(f'ix_operational_access_scopes_{column}','operational_access_scopes',[column])
    op.create_table(
        'saved_views',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('module_key',sa.String(80),nullable=False),
        sa.Column('name',sa.String(120),nullable=False),
        sa.Column('filters',sa.JSON(),nullable=False),
        sa.Column('columns',sa.JSON(),nullable=False),
        sa.Column('is_default',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('user_id','module_key','name',name='uq_saved_view_user_module_name'),
    )
    op.create_index('ix_saved_views_user_id','saved_views',['user_id'])
    op.create_index('ix_saved_views_module_key','saved_views',['module_key'])


def downgrade():
    op.drop_table('saved_views')
    op.drop_table('operational_access_scopes')