"""pass 4 operations hardening"""
from alembic import op
import sqlalchemy as sa
revision='0004_operations_hardening'; down_revision='0003_procurement'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('notifications',sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id')),sa.Column('title',sa.String(180),nullable=False),sa.Column('message',sa.Text(),nullable=False),sa.Column('severity',sa.String(20),nullable=False),sa.Column('is_read',sa.Boolean(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_notifications_user_id','notifications',['user_id']); op.create_index('ix_notifications_is_read','notifications',['is_read']); op.create_index('ix_notifications_created_at','notifications',['created_at'])
    op.create_table('integration_events',sa.Column('id',sa.String(36),primary_key=True),sa.Column('direction',sa.String(10),nullable=False),sa.Column('source_system',sa.String(60),nullable=False),sa.Column('destination_system',sa.String(60),nullable=False),sa.Column('event_type',sa.String(120),nullable=False),sa.Column('aggregate_type',sa.String(80),nullable=False),sa.Column('aggregate_id',sa.String(100),nullable=False),sa.Column('idempotency_key',sa.String(120),nullable=False,unique=True),sa.Column('payload',sa.JSON(),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('last_error',sa.Text()),sa.Column('available_at',sa.DateTime(timezone=True),nullable=False),sa.Column('processed_at',sa.DateTime(timezone=True)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_integration_events_status','integration_events',['status']); op.create_index('ix_integration_events_event_type','integration_events',['event_type']); op.create_index('ix_integration_events_aggregate_id','integration_events',['aggregate_id']); op.create_index('ix_integration_events_created_at','integration_events',['created_at'])
    op.create_table('backup_records',sa.Column('id',sa.String(36),primary_key=True),sa.Column('filename',sa.String(240),nullable=False,unique=True),sa.Column('status',sa.String(30),nullable=False),sa.Column('size_bytes',sa.Integer(),nullable=False),sa.Column('checksum_sha256',sa.String(64)),sa.Column('created_by_user_id',sa.String(36),sa.ForeignKey('users.id')),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_backup_records_created_at','backup_records',['created_at'])

def downgrade():
    op.drop_table('backup_records'); op.drop_table('integration_events'); op.drop_table('notifications')
