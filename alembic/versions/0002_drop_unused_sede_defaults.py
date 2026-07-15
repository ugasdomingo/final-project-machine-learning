"""Elimina default_deposit_type y default_room_type de sedes.

El modelo v2 ya no usa reserved_room_type (letras anonimizadas del dataset,
imposibles de informar por un hotel real) ni deposit_type (artefacto del
dataset: 'Non Refund' implicaba ~99% de cancelación).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-14

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sedes") as batch_op:
        batch_op.drop_column("default_deposit_type")
        batch_op.drop_column("default_room_type")


def downgrade() -> None:
    with op.batch_alter_table("sedes") as batch_op:
        batch_op.add_column(
            sa.Column("default_deposit_type", sa.String(), nullable=False, server_default="No Deposit")
        )
        batch_op.add_column(
            sa.Column("default_room_type", sa.String(), nullable=False, server_default="A")
        )
