"""enforce POS sale lifecycle uniqueness

Revision ID: 0015_pos_sale_lifecycle
Revises: 0014_final_controls
"""
from alembic import op
import sqlalchemy as sa

revision='0015_pos_sale_lifecycle'
down_revision='0014_final_controls'
branch_labels=None
depends_on=None


def upgrade():
    op.create_index(
        'uq_pos_sale_completed_lifecycle',
        'pos_sale_events',
        ['pos_system','external_sale_id'],
        unique=True,
        sqlite_where=sa.text("event_type = 'sale_completed'"),
        postgresql_where=sa.text("event_type = 'sale_completed'"),
    )
    op.create_index(
        'uq_pos_sale_reversal_lifecycle',
        'pos_sale_events',
        ['pos_system','external_sale_id'],
        unique=True,
        sqlite_where=sa.text("event_type IN ('sale_voided','sale_refunded')"),
        postgresql_where=sa.text("event_type IN ('sale_voided','sale_refunded')"),
    )


def downgrade():
    op.drop_index('uq_pos_sale_reversal_lifecycle',table_name='pos_sale_events')
    op.drop_index('uq_pos_sale_completed_lifecycle',table_name='pos_sale_events')
