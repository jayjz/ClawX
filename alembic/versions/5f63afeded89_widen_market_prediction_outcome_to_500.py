"""widen_market_prediction_outcome_to_500

Revision ID: 5f63afeded89
Revises: e43e20c0ba28
Create Date: 2026-02-17 03:39:17.526122

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f63afeded89'
down_revision: Union[str, Sequence[str], None] = 'e43e20c0ba28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Widen market_predictions.outcome from VARCHAR(50) to VARCHAR(500)."""
    op.alter_column(
        "market_predictions",
        "outcome",
        type_=sa.String(500),
        existing_type=sa.String(50),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Revert to VARCHAR(50) — may truncate existing data."""
    op.alter_column(
        "market_predictions",
        "outcome",
        type_=sa.String(50),
        existing_type=sa.String(500),
        existing_nullable=False,
    )
