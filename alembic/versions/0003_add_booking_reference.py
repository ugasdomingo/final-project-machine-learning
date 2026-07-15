"""Añade booking_reference a predictions.

Número/localizador de reserva que introduce el hotel (opcional), para que el
historial muestre algo reconocible en lugar del id interno.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-14

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("predictions", sa.Column("booking_reference", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("predictions", "booking_reference")
