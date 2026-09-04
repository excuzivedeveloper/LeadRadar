"""Add Opportunity evidence shadow traces.

Revision ID: 20260904_0039
Revises: 20260902_0038
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260904_0039"
down_revision: str | None = "20260902_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_evidence_shadow_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("shadow_version", sa.String(64), nullable=False),
        sa.Column("ontology_version", sa.String(64), nullable=False),
        sa.Column("match_trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("search_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_revision", sa.Integer(), nullable=False),
        sa.Column("raw_message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raw_source_policy_version", sa.String(64), nullable=False),
        sa.Column("raw_content_sha256", sa.String(64), nullable=False),
        sa.Column("current_decision_code", sa.String(40), nullable=False),
        sa.Column("current_eligible", sa.Boolean(), nullable=False),
        sa.Column("current_combined_relevance_score", sa.Numeric(6, 5)),
        sa.Column("current_final_rank_score", sa.Numeric(6, 5)),
        sa.Column("shadow_decision", sa.String(40), nullable=False),
        sa.Column("shadow_score", sa.Numeric(6, 5), nullable=False),
        sa.Column("generic_signal_blocked", sa.Boolean(), nullable=False),
        sa.Column("shadow_payload", postgresql.JSONB(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["match_trace_id"],
            ["match_traces.id"],
            name=op.f(
                "fk_opportunity_evidence_shadow_traces_match_trace_id_match_traces"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["match_run_id"],
            ["match_evaluation_runs.id"],
            name=op.f(
                "fk_opportunity_evidence_shadow_traces_match_run_id_match_evaluation_runs"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["opportunities.id"],
            name=op.f(
                "fk_opportunity_evidence_shadow_traces_opportunity_id_opportunities"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["search_profile_id"],
            ["search_profiles.id"],
            name=op.f(
                "fk_opportunity_evidence_shadow_traces_search_profile_id_search_profiles"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["raw_message_id"],
            ["raw_messages.id"],
            name=op.f(
                "fk_opportunity_evidence_shadow_traces_raw_message_id_raw_messages"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_opportunity_evidence_shadow_traces"),
        ),
        sa.UniqueConstraint(
            "match_trace_id",
            "shadow_version",
            name=op.f(
                "uq_opportunity_evidence_shadow_traces_trace_version"
            ),
        ),
        sa.CheckConstraint(
            "schema_version ~ '^[a-z0-9][a-z0-9._-]{0,63}$' "
            "AND shadow_version ~ '^[a-z0-9][a-z0-9._-]{0,63}$' "
            "AND ontology_version ~ '^[a-z0-9][a-z0-9._-]{0,63}$' "
            "AND raw_source_policy_version ~ '^[a-z0-9][a-z0-9._-]{0,63}$'",
            name=op.f(
                "ck_opportunity_evidence_shadow_traces_evidence_shadow_versions_valid"
            ),
        ),
        sa.CheckConstraint(
            "profile_revision >= 1",
            name=op.f(
                "ck_opportunity_evidence_shadow_traces_evidence_shadow_revision_valid"
            ),
        ),
        sa.CheckConstraint(
            "raw_content_sha256 ~ '^[0-9a-f]{64}$' "
            "AND payload_sha256 ~ '^[0-9a-f]{64}$'",
            name=op.f(
                "ck_opportunity_evidence_shadow_traces_evidence_shadow_hashes_valid"
            ),
        ),
        sa.CheckConstraint(
            "current_decision_code IN ('eligible', 'hard_rejected', "
            "'freshness_expired', 'below_relevance_threshold', "
            "'below_rank_score_threshold')",
            name=op.f(
                "ck_opportunity_evidence_shadow_traces_evidence_shadow_current_decision_valid"
            ),
        ),
        sa.CheckConstraint(
            "shadow_decision IN ('strong_eligible', 'weak_or_generic', "
            "'no_evidence_match')",
            name=op.f(
                "ck_opportunity_evidence_shadow_traces_evidence_shadow_decision_valid"
            ),
        ),
        sa.CheckConstraint(
            "shadow_score BETWEEN 0 AND 1",
            name=op.f(
                "ck_opportunity_evidence_shadow_traces_evidence_shadow_score_valid"
            ),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(shadow_payload) = 'object'",
            name=op.f(
                "ck_opportunity_evidence_shadow_traces_evidence_shadow_payload_object"
            ),
        ),
    )
    op.create_index(
        "ix_opportunity_evidence_shadow_traces_match_run",
        "opportunity_evidence_shadow_traces",
        ["match_run_id", "created_at", "id"],
    )
    op.create_index(
        "ix_opportunity_evidence_shadow_traces_opportunity",
        "opportunity_evidence_shadow_traces",
        ["opportunity_id", "search_profile_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_opportunity_evidence_shadow_traces_opportunity",
        table_name="opportunity_evidence_shadow_traces",
    )
    op.drop_index(
        "ix_opportunity_evidence_shadow_traces_match_run",
        table_name="opportunity_evidence_shadow_traces",
    )
    op.drop_table("opportunity_evidence_shadow_traces")
