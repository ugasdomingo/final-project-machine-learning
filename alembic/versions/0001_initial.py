"""Esquema inicial: cuentas multi-sede, predicciones y overbooking.

Revision ID: 0001
Revises:
Create Date: 2026-07-13

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("api_key_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_accounts_api_key_hash", "accounts", ["api_key_hash"], unique=True)

    op.create_table(
        "sedes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("hotel_type", sa.String(), nullable=False),
        sa.Column("total_rooms", sa.Integer(), nullable=False),
        sa.Column("default_country", sa.String(), nullable=False),
        sa.Column("default_meal", sa.String(), nullable=False),
        sa.Column("default_deposit_type", sa.String(), nullable=False),
        sa.Column("default_room_type", sa.String(), nullable=False),
        sa.Column("default_adr", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_sedes_account_id", "sedes", ["account_id"])

    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sede_id", sa.Integer(), sa.ForeignKey("sedes.id"), nullable=False),
        sa.Column("arrival_date", sa.Date(), nullable=True),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("probability", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_predictions_sede_id", "predictions", ["sede_id"])
    op.create_index("ix_predictions_arrival_date", "predictions", ["arrival_date"])

    op.create_table(
        "overbooking_calcs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sede_id", sa.Integer(), sa.ForeignKey("sedes.id"), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("n_bookings", sa.Integer(), nullable=False),
        sa.Column("risk_alpha", sa.Float(), nullable=False),
        sa.Column("expected_cancellations", sa.Float(), nullable=False),
        sa.Column("recommended_extra", sa.Integer(), nullable=False),
        sa.Column("recommended_pct", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_overbooking_calcs_sede_id", "overbooking_calcs", ["sede_id"])


def downgrade() -> None:
    op.drop_table("overbooking_calcs")
    op.drop_table("predictions")
    op.drop_table("sedes")
    op.drop_table("accounts")
