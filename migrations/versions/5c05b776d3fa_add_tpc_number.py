"""Add tpc_number …

Revision ID: 5c05b776d3fa
Revises: a6a35b2ff6df
Create Date: 2025-06-04 10:24:27.695903

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '5c05b776d3fa'
down_revision = 'a6a35b2ff6df'
branch_labels = None
depends_on = None


def upgrade():
    # 只做「新增 tpc_number 欄位」的操作
    op.add_column(
        'taipowermeter_applies',
        sa.Column('tpc_number', sa.String(length=64), nullable=False)
    )


def downgrade():
    # 回滾時，刪除 tpc_number 欄位
    op.drop_column('taipowermeter_applies', 'tpc_number')
