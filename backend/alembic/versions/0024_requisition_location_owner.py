"""Add authoritative optional requisition location with no silent backfill.

Revision ID: 0024_requisition_location_owner
Revises: 0023_stock_book_value_delta

Historical requisitions remain unassigned (NULL) pending human validation.
Never infer ownership from editable notes, department, or a downstream PO.
"""
from alembic import op
import sqlalchemy as sa

revision = "0024_requisition_location_owner"
down_revision = "0023_stock_book_value_delta"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_context().dialect.name == "sqlite":
        # SQLite allows a nullable column with inline REFERENCES. It does not
        # support ALTER TABLE ADD CONSTRAINT, including Alembic --sql mode.
        # The existing NULL rows remain untouched with an actual FK constraint.
        op.execute(
            "ALTER TABLE purchase_requisitions "
            "ADD COLUMN location_id VARCHAR(36) "
            "REFERENCES locations(id)"
        )
    else:
        op.add_column(
            "purchase_requisitions",
            sa.Column("location_id", sa.String(length=36), nullable=True),
        )
        op.create_foreign_key(
            "fk_purchase_requisitions_location_id",
            "purchase_requisitions", "locations", ["location_id"], ["id"],
        )
    op.create_index(
        "ix_purchase_requisitions_location_id",
        "purchase_requisitions", ["location_id"],
    )


def downgrade():
    op.drop_index("ix_purchase_requisitions_location_id", table_name="purchase_requisitions")
    if op.get_context().dialect.name != "sqlite":
        op.drop_constraint(
            "fk_purchase_requisitions_location_id",
            "purchase_requisitions", type_="foreignkey",
        )
    op.drop_column("purchase_requisitions", "location_id")
