"""Record true per-movement book-value deltas without rewriting historical stock.

Revision ID: 0023_stock_book_value_delta
Revises: 0022_stock_request_fingerprint
"""
from alembic import op
import sqlalchemy as sa

revision = "0023_stock_book_value_delta"
down_revision = "0022_stock_request_fingerprint"
branch_labels = None
depends_on = None


def upgrade():
    # Past weighted-average costs cannot be reconstructed losslessly from
    # signed quantity × unit_cost after short stock crosses back positive.
    # Do NOT backfill legacy movements with potentially fictitious values.
    op.add_column("stock_movements", sa.Column("book_value_delta", sa.Numeric(28, 8), nullable=True))


def downgrade():
    op.drop_column("stock_movements", "book_value_delta")
