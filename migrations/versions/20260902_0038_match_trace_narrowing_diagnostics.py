"""Add match trace narrowing diagnostics.

Revision ID: 20260902_0038
Revises: 20260825_0037
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260902_0038"
down_revision: str | None = "20260825_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "match_traces",
        sa.Column(
            "narrowing_diagnostics",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_check_constraint(
        op.f("ck_match_traces_narrowing_diagnostics_array"),
        "match_traces",
        "jsonb_typeof(narrowing_diagnostics) = 'array'",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_match_traces_narrowing_diagnostics_array"),
        "match_traces",
        type_="check",
    )
    op.drop_column("match_traces", "narrowing_diagnostics")
