"""Reopen received orders whose rejected deliveries still need replacement.

Revision ID: 0025_rejected_delivery_followup
Revises: 0024_requisition_location_owner
"""
from alembic import op
import sqlalchemy as sa

revision = "0025_rejected_delivery_followup"
down_revision = "0024_requisition_location_owner"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_goods_receipt_lines_purchase_order_line_id", "goods_receipt_lines", ["purchase_order_line_id"])
    # Preserve every delivery, stock movement and financial document. Only
    # previously received POs with unfulfilled accepted quantity reopen.
    op.execute(sa.text("""
        UPDATE purchase_orders SET status = 'partially_received'
        WHERE status = 'received' AND EXISTS (
            SELECT 1 FROM purchase_order_lines AS pol
            WHERE pol.purchase_order_id = purchase_orders.id
              AND pol.ordered_quantity > pol.received_quantity - COALESCE((
                  SELECT SUM(grl.rejected_quantity) FROM goods_receipt_lines AS grl
                  WHERE grl.purchase_order_line_id = pol.id
              ), 0)
        )
    """))


def downgrade():
    # Do not silently close replacement obligations on a code rollback.
    op.drop_index("ix_goods_receipt_lines_purchase_order_line_id", table_name="goods_receipt_lines")
