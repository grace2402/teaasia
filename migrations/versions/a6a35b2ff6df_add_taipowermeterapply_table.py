"""Add TaipowermeterApply table

Revision ID: a6a35b2ff6df
Revises: eebc37f4263a
Create Date: 2025-06-03 15:41:33.966092

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a6a35b2ff6df'
down_revision = 'eebc37f4263a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'taipowermeter_applies',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('hems_no', sa.String(length=64), nullable=False),
        sa.Column('submitted_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )
    op.create_unique_constraint(
        'uq_taipowermeter_applies_hems_no',
        'taipowermeter_applies',
        ['hems_no']
    )


def downgrade():
    op.drop_table('taipowermeter_applies')
