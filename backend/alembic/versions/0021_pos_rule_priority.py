"""add deterministic POS pricing rule priority

Revision ID: 0021_pos_rule_priority
Revises: 0020_generic_pos_rules
"""
from alembic import op
import sqlalchemy as sa

revision="0021_pos_rule_priority"
down_revision="0020_generic_pos_rules"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("pos_pricing_rules",sa.Column("priority",sa.Integer(),nullable=False,server_default="100"))

def downgrade():
    op.drop_column("pos_pricing_rules","priority")
