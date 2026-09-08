"""add staff meal consumption workflow

Revision ID: 0016_staff_meals
Revises: 0015_pos_sale_lifecycle
"""
from alembic import op
import sqlalchemy as sa


revision = "0016_staff_meals"
down_revision = "0015_pos_sale_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "staff_meals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("meal_number", sa.String(length=60), nullable=False),
        sa.Column("meal_name", sa.String(length=180), nullable=False),
        sa.Column("meal_period", sa.String(length=40), nullable=True),
        sa.Column("servings", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("posted_document_id", sa.String(length=36), nullable=False),
        sa.Column("reversal_document_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("reversed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["posted_document_id"], ["stock_documents.id"]),
        sa.ForeignKeyConstraint(["reversal_document_id"], ["stock_documents.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reversed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meal_number"),
        sa.UniqueConstraint("posted_document_id"),
        sa.UniqueConstraint("reversal_document_id"),
    )
    op.create_index("ix_staff_meals_meal_number", "staff_meals", ["meal_number"])
    op.create_index("ix_staff_meals_location_id", "staff_meals", ["location_id"])
    op.create_index("ix_staff_meals_status", "staff_meals", ["status"])
    op.create_index("ix_staff_meals_created_at", "staff_meals", ["created_at"])

    op.create_table(
        "staff_meal_lines",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("staff_meal_id", sa.String(length=36), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.ForeignKeyConstraint(["staff_meal_id"], ["staff_meals.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("staff_meal_id", "line_number", name="uq_staff_meal_line"),
    )
    op.create_index("ix_staff_meal_lines_staff_meal_id", "staff_meal_lines", ["staff_meal_id"])
    op.create_index("ix_staff_meal_lines_item_id", "staff_meal_lines", ["item_id"])


def downgrade():
    op.drop_index("ix_staff_meal_lines_item_id", table_name="staff_meal_lines")
    op.drop_index("ix_staff_meal_lines_staff_meal_id", table_name="staff_meal_lines")
    op.drop_table("staff_meal_lines")
    op.drop_index("ix_staff_meals_created_at", table_name="staff_meals")
    op.drop_index("ix_staff_meals_status", table_name="staff_meals")
    op.drop_index("ix_staff_meals_location_id", table_name="staff_meals")
    op.drop_index("ix_staff_meals_meal_number", table_name="staff_meals")
    op.drop_table("staff_meals")
