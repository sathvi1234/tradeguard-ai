"""Initial demo ledger tables (account, positions, trades).

Revision ID: 001_demo_ledger
Revises:
Create Date: 2026-09-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_demo_ledger"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("starting_cash", sa.Float(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_demo_account_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "positions",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("avg_entry", sa.Float(), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("symbol"),
    )
    op.create_table(
        "trades",
        sa.Column("trade_id", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("trade_id"),
    )
    op.execute(
        "INSERT INTO account (id, cash, realized_pnl, starting_cash) VALUES (1, 100000.0, 0, 100000.0)"
    )


def downgrade() -> None:
    op.drop_table("trades")
    op.drop_table("positions")
    op.drop_table("account")
