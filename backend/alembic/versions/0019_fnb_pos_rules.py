"""add POS pricing roles and modifier groups

Revision ID: 0019_fnb_pos_rules
Revises: 0018_fnb_menu_management
"""
from alembic import op
import sqlalchemy as sa
revision="0019_fnb_pos_rules"
down_revision="0018_fnb_menu_management"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("menu_items",sa.Column("pricing_role",sa.String(24),nullable=False,server_default="standard"))
    op.add_column("menu_items",sa.Column("modifier_groups_json",sa.Text(),nullable=True))

def downgrade():
    op.drop_column("menu_items","modifier_groups_json")
    op.drop_column("menu_items","pricing_role")
