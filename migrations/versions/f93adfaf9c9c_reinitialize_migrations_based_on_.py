"""Reinitialize migrations based on current models

Revision ID: f93adfaf9c9c
Revises: 
Create Date: 2025-03-06 09:53:48.033344
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f93adfaf9c9c'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # 對 materials.id 欄位，根據是否為 Identity 執行 DROP IDENTITY 或 DROP DEFAULT
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'materials'
              AND column_name = 'id'
              AND is_identity = 'YES'
        ) THEN
            EXECUTE 'ALTER TABLE materials ALTER COLUMN id DROP IDENTITY';
        ELSE
            EXECUTE 'ALTER TABLE materials ALTER COLUMN id DROP DEFAULT';
        END IF;
    END$$;
    """)

    op.alter_column('spots', 'site_name',
                    existing_type=sa.VARCHAR(length=128),
                    nullable=True,
                    existing_server_default=sa.text("'default_site_name'::character varying"))
    op.alter_column('spots', 'description',
                    existing_type=sa.VARCHAR(length=256),
                    nullable=True)
    op.alter_column('spots', 'longitude',
                    existing_type=sa.DOUBLE_PRECISION(precision=53),
                    nullable=True)
    op.alter_column('spots', 'latitude',
                    existing_type=sa.DOUBLE_PRECISION(precision=53),
                    nullable=True)
    op.alter_column('travel_records', 'id',
                    existing_type=sa.INTEGER(),
                    server_default=None,
                    existing_nullable=False,
                    autoincrement=True)

def downgrade():
    # Downgrade 內容視需求處理，這裡略過
    pass
