"""add_markets_table

Revision ID: f38b6c9a7c27
Revises: efe2d5f421a5
Create Date: 2026-02-16 06:12:11.714168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f38b6c9a7c27'
down_revision: Union[str, Sequence[str], None] = 'efe2d5f421a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add markets table for multi-modal data markets."""
    op.create_table('markets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('source_type', sa.Enum('GITHUB', 'NEWS', 'WEATHER', name='marketsourcetype', create_constraint=True), nullable=False),
        sa.Column('resolution_criteria', sa.JSON(), nullable=False),
        sa.Column('status', sa.Enum('OPEN', 'LOCKED', 'RESOLVED', name='marketstatus', create_constraint=True), nullable=False),
        sa.Column('outcome', sa.String(length=500), nullable=True),
        sa.Column('bounty', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Remove markets table."""
    op.drop_table('markets')
    op.execute("DROP TYPE IF EXISTS marketsourcetype")
    op.execute("DROP TYPE IF EXISTS marketstatus")
