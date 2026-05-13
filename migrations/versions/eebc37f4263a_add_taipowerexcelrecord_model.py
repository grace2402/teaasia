"""Add TaipowerExcelRecord model

Revision ID: eebc37f4263a
Revises: 64a5f367b83d
Create Date: 2025-04-23 11:16:38.424570

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'eebc37f4263a'
down_revision = '64a5f367b83d'
branch_labels = None
depends_on = None


def upgrade():
    # Create TaipowerExcelRecord table
    op.create_table(
        'taipower_excel_records',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column('TPC_number', sa.String(length=64), nullable=True),
        sa.Column('username', sa.String(length=128), nullable=True),
        sa.Column('case_number', sa.String(length=64), nullable=True),
        sa.Column('guk_h', sa.String(length=64), nullable=True),
        sa.Column('ak_h', sa.String(length=64), nullable=True),
        sa.Column('meter_brand', sa.String(length=64), nullable=True),
        sa.Column('meter_number', sa.String(length=64), nullable=True),
        sa.Column('multiplier', sa.String(length=32), nullable=True),
        sa.Column('full_meter_number', sa.String(length=128), nullable=True),
        sa.Column('request_date', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False)
    )


def downgrade():
    # Drop TaipowerExcelRecord table
    op.drop_table('taipower_excel_records')
