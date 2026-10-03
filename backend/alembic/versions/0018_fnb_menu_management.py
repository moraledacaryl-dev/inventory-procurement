"""F&B menu management"""
from alembic import op
import sqlalchemy as sa
revision="0018_fnb_menu_management"
down_revision="0017_staff_identity"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("menu_items",sa.Column("id",sa.String(36),primary_key=True),sa.Column("name",sa.String(180),nullable=False),sa.Column("display_name",sa.String(180),nullable=False),sa.Column("category",sa.String(100),nullable=False),sa.Column("description",sa.Text(),nullable=True),sa.Column("prep_station",sa.String(40),nullable=False,server_default="bar"),sa.Column("sort_order",sa.Integer(),nullable=False,server_default="0"),sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("pos_visible",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_menu_items_name","menu_items",["name"]);op.create_index("ix_menu_items_category","menu_items",["category"])
    op.create_table("menu_variants",sa.Column("id",sa.String(36),primary_key=True),sa.Column("menu_item_id",sa.String(36),sa.ForeignKey("menu_items.id",ondelete="CASCADE"),nullable=False),sa.Column("name",sa.String(120),nullable=False,server_default="Regular"),sa.Column("sku",sa.String(80),nullable=False),sa.Column("barcode",sa.String(100),nullable=False),sa.Column("price",sa.Numeric(12,2),nullable=False),sa.Column("with_drink_price",sa.Numeric(12,2),nullable=True),sa.Column("recipe_id",sa.String(36),sa.ForeignKey("recipes.id"),nullable=True),sa.Column("inventory_item_id",sa.String(36),sa.ForeignKey("items.id"),nullable=True),sa.Column("sort_order",sa.Integer(),nullable=False,server_default="0"),sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),sa.UniqueConstraint("sku",name="uq_menu_variant_sku"),sa.UniqueConstraint("barcode",name="uq_menu_variant_barcode"))
    op.create_index("ix_menu_variants_menu_item_id","menu_variants",["menu_item_id"]);op.create_index("ix_menu_variants_recipe_id","menu_variants",["recipe_id"]);op.create_index("ix_menu_variants_inventory_item_id","menu_variants",["inventory_item_id"])
def downgrade():
    op.drop_table("menu_variants");op.drop_table("menu_items")
