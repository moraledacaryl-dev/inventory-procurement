"""pass 4 fixed assets and depreciation

Revision ID: 0012_fixed_assets
Revises: 0011_reusable_property
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_fixed_assets"
down_revision = "0011_reusable_property"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fixed_assets",
        sa.Column("asset_tag", sa.String(80), nullable=False, unique=True),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("asset_class_id", sa.String(36), sa.ForeignKey("operational_dimensions.id"), nullable=False),
        sa.Column("depreciation_method_id", sa.String(36), sa.ForeignKey("operational_dimensions.id"), nullable=False),
        sa.Column("location_id", sa.String(36), sa.ForeignKey("locations.id")),
        sa.Column("department_id", sa.String(36), sa.ForeignKey("operational_dimensions.id")),
        sa.Column("cost_center_id", sa.String(36), sa.ForeignKey("operational_dimensions.id")),
        sa.Column("custodian_user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id")),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("purchase_orders.id")),
        sa.Column("goods_receipt_id", sa.String(36), sa.ForeignKey("goods_receipts.id")),
        sa.Column("serial_number", sa.String(160)), sa.Column("model_number", sa.String(160)),
        sa.Column("acquisition_date", sa.Date(), nullable=False), sa.Column("placed_in_service_date", sa.Date()),
        sa.Column("acquisition_cost", sa.Numeric(18,2), nullable=False), sa.Column("capitalized_cost", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("residual_value", sa.Numeric(18,2), nullable=False, server_default="0"), sa.Column("useful_life_months", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("accumulated_depreciation", sa.Numeric(18,2), nullable=False, server_default="0"), sa.Column("impairment_loss", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(40), nullable=False, server_default="candidate"), sa.Column("condition", sa.String(40), nullable=False, server_default="good"),
        sa.Column("warranty_expiry", sa.Date()), sa.Column("disposal_date", sa.Date()), sa.Column("disposal_proceeds", sa.Numeric(18,2)), sa.Column("notes", sa.Text()),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for c in ("asset_tag","item_id","asset_class_id","depreciation_method_id","location_id","department_id","cost_center_id","custodian_user_id","serial_number","status"):
        op.create_index(f"ix_fixed_assets_{c}", "fixed_assets", [c])
    op.create_table("depreciation_runs", sa.Column("id",sa.String(36),primary_key=True),sa.Column("period",sa.String(7),nullable=False),sa.Column("status",sa.String(30),nullable=False,server_default="draft"),sa.Column("total_amount",sa.Numeric(18,2),nullable=False,server_default="0"),sa.Column("created_by_user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("posted_by_user_id",sa.String(36),sa.ForeignKey("users.id")),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("posted_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("period",name="uq_depreciation_run_period"))
    op.create_index("ix_depreciation_runs_period","depreciation_runs",["period"])
    op.create_table("depreciation_lines",sa.Column("id",sa.String(36),primary_key=True),sa.Column("run_id",sa.String(36),sa.ForeignKey("depreciation_runs.id",ondelete="CASCADE"),nullable=False),sa.Column("asset_id",sa.String(36),sa.ForeignKey("fixed_assets.id"),nullable=False),sa.Column("amount",sa.Numeric(18,2),nullable=False),sa.Column("opening_accumulated",sa.Numeric(18,2),nullable=False),sa.Column("closing_accumulated",sa.Numeric(18,2),nullable=False),sa.Column("closing_net_book_value",sa.Numeric(18,2),nullable=False),sa.UniqueConstraint("run_id","asset_id",name="uq_depreciation_line_asset"))
    op.create_index("ix_depreciation_lines_run_id","depreciation_lines",["run_id"]); op.create_index("ix_depreciation_lines_asset_id","depreciation_lines",["asset_id"])
    op.create_table("asset_events",sa.Column("id",sa.String(36),primary_key=True),sa.Column("asset_id",sa.String(36),sa.ForeignKey("fixed_assets.id"),nullable=False),sa.Column("event_type",sa.String(40),nullable=False),sa.Column("event_date",sa.Date(),nullable=False),sa.Column("from_location_id",sa.String(36),sa.ForeignKey("locations.id")),sa.Column("to_location_id",sa.String(36),sa.ForeignKey("locations.id")),sa.Column("amount",sa.Numeric(18,2)),sa.Column("notes",sa.Text()),sa.Column("created_by_user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index("ix_asset_events_asset_id","asset_events",["asset_id"]); op.create_index("ix_asset_events_event_type","asset_events",["event_type"])


def downgrade():
    op.drop_table("asset_events"); op.drop_table("depreciation_lines"); op.drop_table("depreciation_runs"); op.drop_table("fixed_assets")
