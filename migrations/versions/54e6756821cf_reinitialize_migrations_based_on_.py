"""Reinitialize migrations based on current models

Revision ID: 54e6756821cf
Revises: f93adfaf9c9c
Create Date: 2025-03-06 09:54:32.850313
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '54e6756821cf'
down_revision = 'f93adfaf9c9c'
branch_labels = None
depends_on = None

def upgrade():
    # 針對 materials.id 欄位：同上，依是否為 Identity 進行調整
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

    # 針對 travel_records.id 欄位：同理
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'travel_records'
              AND column_name = 'id'
              AND is_identity = 'YES'
        ) THEN
            EXECUTE 'ALTER TABLE travel_records ALTER COLUMN id DROP IDENTITY';
        ELSE
            EXECUTE 'ALTER TABLE travel_records ALTER COLUMN id DROP DEFAULT';
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
    # Downgrade 內容視需求處理，此處略過
    pass
