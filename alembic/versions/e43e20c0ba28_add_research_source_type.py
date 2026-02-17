"""add_research_source_type

Revision ID: e43e20c0ba28
Revises: f38b6c9a7c27
Create Date: 2026-02-16 19:18:02.538234

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e43e20c0ba28'
down_revision: Union[str, Sequence[str], None] = 'f38b6c9a7c27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add RESEARCH value to marketsourcetype enum.

    ALTER TYPE cannot run in a transaction on older PG versions,
    so we COMMIT first. IF NOT EXISTS makes this idempotent.
    """
    op.execute("COMMIT")
    op.execute("ALTER TYPE marketsourcetype ADD VALUE IF NOT EXISTS 'RESEARCH'")


def downgrade() -> None:
    """Postgres does not support removing enum values."""
    pass
