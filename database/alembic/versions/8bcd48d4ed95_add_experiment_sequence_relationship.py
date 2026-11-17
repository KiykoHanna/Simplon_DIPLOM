"""add experiment sequence relationship

Revision ID: 8bcd48d4ed95
Revises: 
Create Date: 2026-11-16 18:02:47.670689

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8bcd48d4ed95'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.add_column("experiments", sa.Column("sequence_id", sa.Integer(), nullable=True))
    op.add_column("experiments", sa.Column("source", sa.String(30), nullable=True))
    op.add_column("experiments", sa.Column("source_document_id", sa.String(50), nullable=True))
    op.add_column("experiments", sa.Column("source_experiment_id", sa.String(100), nullable=True))
    op.alter_column("experiments", "source", existing_type=sa.String(30), nullable=False)
    op.create_index("ix_experiments_sequence_id", "experiments", ["sequence_id"])
    op.create_index("ix_experiments_source", "experiments", ["source"])
    op.create_unique_constraint("uq_experiment_source_document", "experiments", ["source", "source_document_id"])
    op.create_unique_constraint("uq_experiment_source_experiment", "experiments", ["source", "source_experiment_id"])
    op.create_foreign_key("fk_experiments_sequence_id_sequences", "experiments", "sequences", ["sequence_id"], ["id"], ondelete="RESTRICT")


def downgrade() -> None:
    op.drop_constraint("fk_experiments_sequence_id_sequences", "experiments", type_="foreignkey")
    op.drop_constraint("uq_experiment_source_experiment", "experiments", type_="unique")
    op.drop_constraint("uq_experiment_source_document", "experiments", type_="unique")
    op.drop_index("ix_experiments_source", table_name="experiments")
    op.drop_index("ix_experiments_sequence_id", table_name="experiments")
    op.drop_column("experiments", "source_experiment_id")
    op.drop_column("experiments", "source_document_id")
    op.drop_column("experiments", "source")
    op.drop_column("experiments", "sequence_id")

