"""booking_reference pasa a ser obligatorio y único por sede.

Cada reserva es única y su número permite al hotel ubicar los datos del
huésped. Las predicciones antiguas sin número reciben '#<id>' como respaldo.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-14

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill: las filas históricas sin número reciben uno derivado del id,
    # que es único por construcción.
    op.execute(
        "UPDATE predictions SET booking_reference = '#' || id WHERE booking_reference IS NULL"
    )
    with op.batch_alter_table("predictions") as batch_op:
        batch_op.alter_column("booking_reference", existing_type=sa.String(), nullable=False)
        batch_op.create_unique_constraint(
            "uq_predictions_sede_reference", ["sede_id", "booking_reference"]
        )


def downgrade() -> None:
    with op.batch_alter_table("predictions") as batch_op:
        batch_op.drop_constraint("uq_predictions_sede_reference", type_="unique")
        batch_op.alter_column("booking_reference", existing_type=sa.String(), nullable=True)
