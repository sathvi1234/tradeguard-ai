"""Falsification research reports.

Revision ID: 003_falsification_reports
Revises: 002_backtest_runs
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003_falsification_reports"
down_revision: Union[str, None] = "002_backtest_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "falsification_reports",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.String(length=32), nullable=False),
        sa.Column("end_date", sa.String(length=32), nullable=False),
        sa.Column("overall_state", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("result_kind", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("falsification_reports")
