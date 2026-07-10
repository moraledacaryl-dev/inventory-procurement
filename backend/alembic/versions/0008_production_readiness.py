"""pass 9 production readiness"""
from alembic import op
import sqlalchemy as sa
revision='0008_production_readiness'; down_revision='0007_recipes_production_pos'; branch_labels=None; depends_on=None

def upgrade():
    op.create_table('data_import_jobs',sa.Column('id',sa.String(36),primary_key=True),sa.Column('import_type',sa.String(60),nullable=False),sa.Column('filename',sa.String(240),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('summary',sa.JSON(),nullable=False),sa.Column('errors',sa.JSON(),nullable=False),sa.Column('created_by_user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('applied_at',sa.DateTime(timezone=True))); op.create_index('ix_data_import_jobs_import_type','data_import_jobs',['import_type']); op.create_index('ix_data_import_jobs_status','data_import_jobs',['status']); op.create_index('ix_data_import_jobs_created_at','data_import_jobs',['created_at'])
    op.create_table('acceptance_runs',sa.Column('id',sa.String(36),primary_key=True),sa.Column('run_number',sa.String(60),nullable=False,unique=True),sa.Column('environment',sa.String(60),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('results',sa.JSON(),nullable=False),sa.Column('notes',sa.Text()),sa.Column('created_by_user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('completed_at',sa.DateTime(timezone=True))); op.create_index('ix_acceptance_runs_run_number','acceptance_runs',['run_number']); op.create_index('ix_acceptance_runs_status','acceptance_runs',['status']); op.create_index('ix_acceptance_runs_created_at','acceptance_runs',['created_at'])

def downgrade():
    op.drop_table('acceptance_runs'); op.drop_table('data_import_jobs')
