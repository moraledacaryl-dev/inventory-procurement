"""generic POS pricing rules and reusable modifiers

Revision ID: 0020_generic_pos_rules
Revises: 0019_fnb_pos_rules
"""
from alembic import op
import sqlalchemy as sa

revision="0020_generic_pos_rules"
down_revision="0019_fnb_pos_rules"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("menu_items",sa.Column("pricing_tags_json",sa.Text(),nullable=True))
    op.add_column("menu_items",sa.Column("modifier_template_ids_json",sa.Text(),nullable=True))
    op.add_column("menu_variants",sa.Column("conditional_prices_json",sa.Text(),nullable=True))
    op.create_table(
        "pos_pricing_rules",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("name",sa.String(180),nullable=False),
        sa.Column("qualifier_tag",sa.String(80),nullable=False),
        sa.Column("target_tag",sa.String(80),nullable=False),
        sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("name",name="uq_pos_pricing_rule_name"),
    )
    op.create_table(
        "pos_modifier_templates",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("name",sa.String(180),nullable=False),
        sa.Column("config_json",sa.Text(),nullable=False),
        sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("name",name="uq_pos_modifier_template_name"),
    )

def downgrade():
    op.drop_table("pos_modifier_templates")
    op.drop_table("pos_pricing_rules")
    op.drop_column("menu_variants","conditional_prices_json")
    op.drop_column("menu_items","modifier_template_ids_json")
    op.drop_column("menu_items","pricing_tags_json")
