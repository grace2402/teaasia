"""empty message

Revision ID: 981e3ae4a9af
Revises: 54e6756821cf
Create Date: 2025-03-06 14:46:15.314910
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '981e3ae4a9af'
down_revision = '54e6756821cf'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('contracts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('warranty_start', sa.String(length=64), nullable=True),
        sa.Column('warranty_end', sa.String(length=64), nullable=True),
        sa.Column('maintenance_start', sa.String(length=64), nullable=True),
        sa.Column('maintenance_end', sa.String(length=64), nullable=True),
        sa.Column('spot_id', sa.Integer(), nullable=False),
        sa.Column('site_name', sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(['spot_id'], ['spots.id']),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('contracts')
