"""pass 1 configurable operating structure

Revision ID: 0010_operating_structure
Revises: 0009_stabilization_rollout
"""
from alembic import op
import sqlalchemy as sa

from app.services.classification_defaults import DEFAULT_DIMENSIONS

revision = "0010_operating_structure"
down_revision = "0009_stabilization_rollout"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "operational_dimensions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dimension_type", sa.String(50), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("behavior_key", sa.String(80)),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("operational_dimensions.id")),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("operational_dimensions.id")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settings", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("dimension_type", "code", name="uq_operational_dimension_type_code"),
    )
    for column in ("dimension_type", "code", "name", "behavior_key", "parent_id", "workspace_id"):
        op.create_index(f"ix_operational_dimensions_{column}", "operational_dimensions", [column])

    op.create_table(
        "item_workspace_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("operational_dimensions.id"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("item_id", "workspace_id", name="uq_item_workspace_assignment"),
    )
    op.create_index("ix_item_workspace_assignments_item_id", "item_workspace_assignments", ["item_id"])
    op.create_index("ix_item_workspace_assignments_workspace_id", "item_workspace_assignments", ["workspace_id"])

    dialect = op.get_context().dialect.name
    op.add_column("categories", sa.Column("parent_id", sa.String(36), nullable=True))
    op.add_column("categories", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
    if dialect != "sqlite":
        op.create_foreign_key("fk_categories_parent_id", "categories", "categories", ["parent_id"], ["id"])
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])

    for name in ("record_class_id", "item_type_id", "primary_workspace_id", "department_id", "cost_center_id"):
        op.add_column("items", sa.Column(name, sa.String(36), nullable=True))
        if dialect != "sqlite":
            op.create_foreign_key(f"fk_items_{name}", "items", "operational_dimensions", [name], ["id"])
        op.create_index(f"ix_items_{name}", "items", [name])
    op.add_column("items", sa.Column("default_location_id", sa.String(36), nullable=True))
    if dialect != "sqlite":
        op.create_foreign_key("fk_items_default_location_id", "items", "locations", ["default_location_id"], ["id"])
    op.create_index("ix_items_default_location_id", "items", ["default_location_id"])

    seed_table = sa.table(
        "operational_dimensions",
        sa.column("id", sa.String),
        sa.column("dimension_type", sa.String),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("behavior_key", sa.String),
        sa.column("parent_id", sa.String),
        sa.column("workspace_id", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("is_system", sa.Boolean),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(seed_table, [
        {
            "id": row["id"],
            "dimension_type": row["dimension_type"],
            "code": row["code"],
            "name": row["name"],
            "behavior_key": row.get("behavior_key"),
            "parent_id": row.get("parent_id"),
            "workspace_id": row.get("workspace_id"),
            "sort_order": row.get("sort_order", 0),
            "is_system": True,
            "is_active": True,
        }
        for row in DEFAULT_DIMENSIONS
    ])


def downgrade():
    dialect = op.get_context().dialect.name
    op.drop_index("ix_items_default_location_id", table_name="items")
    if dialect != "sqlite":
        op.drop_constraint("fk_items_default_location_id", "items", type_="foreignkey")
    op.drop_column("items", "default_location_id")
    for name in reversed(("record_class_id", "item_type_id", "primary_workspace_id", "department_id", "cost_center_id")):
        op.drop_index(f"ix_items_{name}", table_name="items")
        if dialect != "sqlite":
            op.drop_constraint(f"fk_items_{name}", "items", type_="foreignkey")
        op.drop_column("items", name)
    op.drop_index("ix_categories_parent_id", table_name="categories")
    if dialect != "sqlite":
        op.drop_constraint("fk_categories_parent_id", "categories", type_="foreignkey")
    op.drop_column("categories", "sort_order")
    op.drop_column("categories", "parent_id")
    op.drop_table("item_workspace_assignments")
    op.drop_table("operational_dimensions")
