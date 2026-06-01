"""Add stl_decomposition column to drift_thresholds.

Revision ID: 002_add_stl
Revises: 001_initial_schema
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002_add_stl"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "drift_thresholds",
        sa.Column("stl_decomposition", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("drift_thresholds", "stl_decomposition")
