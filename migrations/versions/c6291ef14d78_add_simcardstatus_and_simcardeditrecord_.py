"""Add SimCardStatus and SimCardEditRecord tables

Revision ID: c6291ef14d78
Revises: d06339d28099
Create Date: 2025-03-14 11:30:51.940252

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6291ef14d78'
down_revision = 'd06339d28099'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'sim_card_edit_record',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('original_pid', sa.String(length=64), nullable=False),
        sa.Column('original_iccid', sa.String(length=64), nullable=False),
        sa.Column('original_status', sa.String(length=30), nullable=False),
        sa.Column('original_group', sa.String(length=64), nullable=True),
        sa.Column('updated_by', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'sim_card_status',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pid', sa.String(length=64), nullable=False),
        sa.Column('iccid', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('group', sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('sim_card_status')
    op.drop_table('sim_card_edit_record')
