"""add warranty_amount field to Contract

Revision ID: 64a5f367b83d
Revises: 0a1a0e7df091
Create Date: 2025-03-17 14:26:21.393725

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '64a5f367b83d'
down_revision = '0a1a0e7df091'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('contracts', sa.Column('warranty_amount', sa.String(length=64), nullable=True))


def downgrade():
    op.drop_column('contracts', 'warranty_amount')
