"""pass 5 integrations and controls"""
from alembic import op
import sqlalchemy as sa
revision='0005_integrations_controls'; down_revision='0004_operations_hardening'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('notification_reads',sa.Column('id',sa.String(36),primary_key=True),sa.Column('notification_id',sa.String(36),sa.ForeignKey('notifications.id',ondelete='CASCADE'),nullable=False),sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),sa.Column('read_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('notification_id','user_id',name='uq_notification_read_user'))
    op.create_index('ix_notification_reads_notification_id','notification_reads',['notification_id']); op.create_index('ix_notification_reads_user_id','notification_reads',['user_id'])
    op.add_column('integration_events',sa.Column('max_attempts',sa.Integer(),nullable=False,server_default='8'))
    op.add_column('integration_events',sa.Column('locked_at',sa.DateTime(timezone=True)))
    op.add_column('integration_events',sa.Column('locked_by',sa.String(100)))
    op.create_index('ix_integration_events_available_at','integration_events',['available_at'])
    op.create_table('document_sequences',sa.Column('prefix',sa.String(20),primary_key=True),sa.Column('next_value',sa.Integer(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.drop_index('ix_notifications_is_read',table_name='notifications')
    op.drop_column('notifications','is_read')

def downgrade():
    op.add_column('notifications',sa.Column('is_read',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.create_index('ix_notifications_is_read','notifications',['is_read'])
    op.drop_table('document_sequences')
    op.drop_index('ix_integration_events_available_at',table_name='integration_events')
    op.drop_column('integration_events','locked_by'); op.drop_column('integration_events','locked_at'); op.drop_column('integration_events','max_attempts')
    op.drop_table('notification_reads')
