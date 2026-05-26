"""Initial schema — all Sentinel tables.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-05-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── model_registry ────────────────────────────────────────
    op.create_table(
        "model_registry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("task_type", sa.String(64)),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("config_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id", name="pk_model_registry"),
    )

    # ── predictions ───────────────────────────────────────────
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("prediction", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("actual", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["model_id"], ["model_registry.id"],
                                name="fk_predictions_model_id_model_registry",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_predictions"),
    )
    op.create_index("ix_predictions_model_id_created_at", "predictions",
                    ["model_id", "created_at"])

    # ── reference_baselines ───────────────────────────────────
    op.create_table(
        "reference_baselines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("feature_stats", sa.JSON(), nullable=False),
        sa.Column("n_samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["model_id"], ["model_registry.id"],
                                name="fk_reference_baselines_model_id_model_registry",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_reference_baselines"),
    )
    op.create_index("ix_reference_baselines_model_id", "reference_baselines", ["model_id"])

    # ── drift_events ──────────────────────────────────────────
    op.create_table(
        "drift_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("detector", sa.String(64), nullable=False),
        sa.Column("metric_name", sa.String(255)),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("drift_type", sa.String(64)),
        sa.Column("severity", sa.String(32), nullable=False, server_default="warn"),
        sa.Column("shap_attribution", sa.JSON()),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["model_id"], ["model_registry.id"],
                                name="fk_drift_events_model_id_model_registry",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_drift_events"),
    )
    op.create_index("ix_drift_events_model_id_detected_at", "drift_events",
                    ["model_id", "detected_at"])

    # ── drift_thresholds ──────────────────────────────────────
    op.create_table(
        "drift_thresholds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("detector", sa.String(64), nullable=False),
        sa.Column("metric_name", sa.String(255)),
        sa.Column("ewma_threshold", sa.Float(), nullable=False),
        sa.Column("ewma_mean", sa.Float()),
        sa.Column("ewma_std", sa.Float()),
        sa.Column("history", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["model_id"], ["model_registry.id"],
                                name="fk_drift_thresholds_model_id_model_registry",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_drift_thresholds"),
    )
    op.create_index("ix_drift_thresholds_model_detector", "drift_thresholds",
                    ["model_id", "detector", "metric_name"])

    # ── alerts ────────────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("drift_event_id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("suppressed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["drift_event_id"], ["drift_events.id"],
                                name="fk_alerts_drift_event_id_drift_events",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_alerts"),
    )
    op.create_index("ix_alerts_model_id_status", "alerts", ["model_id", "status"])

    # ── audit_log ─────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("performed_by", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"],
                                name="fk_audit_log_alert_id_alerts",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )

    # ── calibration_curves ────────────────────────────────────
    op.create_table(
        "calibration_curves",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("detector", sa.String(64)),
        sa.Column("curve_data", sa.JSON()),
        sa.Column("threshold_recommendations", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["model_id"], ["model_registry.id"],
                                name="fk_calibration_curves_model_id_model_registry",
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_calibration_curves"),
    )


def downgrade() -> None:
    op.drop_table("calibration_curves")
    op.drop_table("audit_log")
    op.drop_table("alerts")
    op.drop_table("drift_thresholds")
    op.drop_table("drift_events")
    op.drop_table("reference_baselines")
    op.drop_table("predictions")
    op.drop_table("model_registry")
    op.drop_table("users")