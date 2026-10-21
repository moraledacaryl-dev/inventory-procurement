"""Bind stock document idempotency keys to a canonical request fingerprint.

Revision ID: 0022_stock_request_fingerprint
Revises: 0021_pos_rule_priority
"""
from alembic import op
import sqlalchemy as sa

revision = "0022_stock_request_fingerprint"
down_revision = "0021_pos_rule_priority"
branch_labels = None
depends_on = None


def upgrade():
    # Historical documents remain nullable and are validated by their movement
    # lineage when an old idempotency key is replayed.
    op.add_column("stock_documents", sa.Column("request_fingerprint", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("stock_documents", "request_fingerprint")
