"""add Staff identity projection

Revision ID: 0017_staff_identity
Revises: 0016_staff_meals
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_staff_identity"
down_revision = "0016_staff_meals"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "staff_identities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_staff_id", sa.Integer(), nullable=False),
        sa.Column("employee_code", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("position", sa.String(length=120), nullable=True),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.Column("primary_department", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("source_version", sa.String(length=180), nullable=False),
        sa.Column("last_external_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_staff_id"),
        sa.UniqueConstraint("employee_code"),
    )
    op.create_index("ix_staff_identities_source_staff_id", "staff_identities", ["source_staff_id"], unique=True)
    op.create_index("ix_staff_identities_employee_code", "staff_identities", ["employee_code"], unique=True)


def downgrade():
    op.drop_index("ix_staff_identities_employee_code", table_name="staff_identities")
    op.drop_index("ix_staff_identities_source_staff_id", table_name="staff_identities")
    op.drop_table("staff_identities")
