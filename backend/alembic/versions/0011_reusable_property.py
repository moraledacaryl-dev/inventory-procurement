"""pass 3 reusable property and hotel pars

Revision ID: 0011_reusable_property
Revises: 0010_operating_structure
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_reusable_property"
down_revision = "0010_operating_structure"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "property_balances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("location_id", sa.String(36), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("condition_id", sa.String(36), sa.ForeignKey("operational_dimensions.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("item_id", "location_id", "condition_id", name="uq_property_balance_bucket"),
    )
    for column in ("item_id", "location_id", "condition_id"):
        op.create_index(f"ix_property_balances_{column}", "property_balances", [column])

    op.create_table(
        "property_movements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("movement_number", sa.String(50), nullable=False, unique=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("source_location_id", sa.String(36), sa.ForeignKey("locations.id")),
        sa.Column("destination_location_id", sa.String(36), sa.ForeignKey("locations.id")),
        sa.Column("source_condition_id", sa.String(36), sa.ForeignKey("operational_dimensions.id")),
        sa.Column("destination_condition_id", sa.String(36), sa.ForeignKey("operational_dimensions.id")),
        sa.Column("movement_reason_id", sa.String(36), sa.ForeignKey("operational_dimensions.id")),
        sa.Column("assignee_user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("reference", sa.String(160)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("movement_number", "item_id", "source_location_id", "destination_location_id", "created_at"):
        op.create_index(f"ix_property_movements_{column}", "property_movements", [column])

    op.create_table(
        "hotel_par_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("profile_type", sa.String(40), nullable=False, server_default="room_type"),
        sa.Column("location_id", sa.String(36), sa.ForeignKey("locations.id")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_hotel_par_profiles_code", "hotel_par_profiles", ["code"])

    op.create_table(
        "hotel_par_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("hotel_par_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("par_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.UniqueConstraint("profile_id", "item_id", name="uq_hotel_par_line_item"),
    )
    op.create_index("ix_hotel_par_lines_profile_id", "hotel_par_lines", ["profile_id"])
    op.create_index("ix_hotel_par_lines_item_id", "hotel_par_lines", ["item_id"])


def downgrade():
    op.drop_table("hotel_par_lines")
    op.drop_table("hotel_par_profiles")
    op.drop_table("property_movements")
    op.drop_table("property_balances")
