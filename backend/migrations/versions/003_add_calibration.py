"""Add calibration optimal_threshold and auc, and indexes.

Revision ID: 003_add_calibration
Revises: 002_add_stl
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003_add_calibration"
down_revision = "002_add_stl"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calibration_curves",
        sa.Column("optimal_threshold", sa.Float(), nullable=True),
    )
    op.add_column(
        "calibration_curves",
        sa.Column("auc", sa.Float(), nullable=True),
    )
    op.create_index(
        "ix_calibration_curves_model_id",
        "calibration_curves",
        ["model_id"],
    )
    op.create_index(
        "ix_alerts_model_id",
        "alerts",
        ["model_id"],
    )
    op.create_index(
        "ix_predictions_created_at",
        "predictions",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_predictions_created_at", table_name="predictions")
    op.drop_index("ix_alerts_model_id", table_name="alerts")
    op.drop_index("ix_calibration_curves_model_id", table_name="calibration_curves")
    op.drop_column("calibration_curves", "auc")
    op.drop_column("calibration_curves", "optimal_threshold")
