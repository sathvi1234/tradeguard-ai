"""Store historical backtest simulation results.

Revision ID: 002_backtest_runs
Revises: 001_demo_ledger
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_backtest_runs"
down_revision: Union[str, None] = "001_demo_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.String(length=32), nullable=False),
        sa.Column("end_date", sa.String(length=32), nullable=False),
        sa.Column("initial_capital", sa.Float(), nullable=False),
        sa.Column("position_size", sa.Float(), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("result_kind", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("backtest_runs")
