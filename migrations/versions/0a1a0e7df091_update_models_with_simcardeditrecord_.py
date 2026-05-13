"""Update models with SimCardEditRecord sim_card_status_id

Revision ID: 0a1a0e7df091
Revises: c6291ef14d78
Create Date: 2025-03-14 15:18:59.685922

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0a1a0e7df091'
down_revision = 'c6291ef14d78'
branch_labels = None
depends_on = None

def upgrade():
    # 新增 sim_card_status_id 欄位至 sim_card_edit_record，暫時允許 NULL
    op.add_column('sim_card_edit_record', sa.Column('sim_card_status_id', sa.Integer(), nullable=True))
    
    conn = op.get_bind()
    # 使用 sa.text() 包裝 SQL 查詢，取得 sim_card_status 表中任一 id
    result = conn.execute(sa.text("SELECT id FROM sim_card_status LIMIT 1"))
    dummy = result.fetchone()
    if dummy is None:
        result = conn.execute(sa.text(
            "INSERT INTO sim_card_status (pid, iccid, status, \"group\") VALUES ('dummy','dummy','dummy','dummy') RETURNING id"
        ))
        dummy_id = result.fetchone()[0]
    else:
        dummy_id = dummy[0]
    
    # 將 sim_card_edit_record 中所有 NULL sim_card_status_id 更新為 dummy_id
    op.execute(sa.text(f"UPDATE sim_card_edit_record SET sim_card_status_id = {dummy_id} WHERE sim_card_status_id IS NULL"))
    
    # 修改欄位為 non-null 並建立外鍵約束
    op.alter_column('sim_card_edit_record', 'sim_card_status_id', nullable=False)
    op.create_foreign_key(None, 'sim_card_edit_record', 'sim_card_status', ['sim_card_status_id'], ['id'])
    
    # 移除所有針對 materials 表的修改（這部分已移除）

def downgrade():
    op.drop_constraint(None, 'sim_card_edit_record', type_='foreignkey')
    op.drop_column('sim_card_edit_record', 'sim_card_status_id')
