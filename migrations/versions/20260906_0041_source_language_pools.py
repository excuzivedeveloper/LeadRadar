"""Add source language pools to sources and profile preferences.

Revision ID: 20260906_0041
Revises: 20260905_0040
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260906_0041"
down_revision: str | None = "20260905_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_V1_DEFAULT = (
    "jsonb_build_object("
    "'schema_version', 'search_profile_preferences.v1', "
    "'work_types', NULL, 'minimum_budget', NULL, 'currency', NULL, "
    "'budget_policy', NULL, 'languages', NULL, 'geographies', NULL, "
    "'work_modes', NULL, 'excluded_categories', NULL)"
)
_V2_DEFAULT = (
    "jsonb_build_object("
    "'schema_version', 'search_profile_preferences.v2', "
    "'work_types', NULL, 'minimum_budget', NULL, 'currency', NULL, "
    "'budget_policy', NULL, 'languages', NULL, 'geographies', NULL, "
    "'work_modes', NULL, 'excluded_categories', NULL, "
    "'source_languages', jsonb_build_array('ru', 'en'))"
)


def upgrade() -> None:
    op.add_column("sources", sa.Column("language", sa.String(2), nullable=True))
    op.add_column("sources", sa.Column("language_origin", sa.String(20), nullable=True))
    op.create_check_constraint(
        op.f("ck_sources_language_supported"),
        "sources",
        "language IS NULL OR language IN ('ru', 'en')",
    )
    op.create_check_constraint(
        op.f("ck_sources_language_origin_supported"),
        "sources",
        "language_origin IS NULL OR language_origin IN "
        "('seed', 'discovery_query', 'audit', 'operator')",
    )
    op.create_check_constraint(
        op.f("ck_sources_language_origin_consistent"),
        "sources",
        "(language IS NULL AND language_origin IS NULL) OR "
        "(language IS NOT NULL AND language_origin IS NOT NULL)",
    )
    op.create_index("ix_sources_language", "sources", ["language"])

    op.drop_constraint(
        op.f("ck_search_profiles_preferences_contract_valid"),
        "search_profiles",
        type_="check",
    )
    op.execute(
        """
        UPDATE search_profiles
        SET preferences =
            jsonb_set(
                preferences || jsonb_build_object('source_languages', NULL),
                '{schema_version}',
                to_jsonb('search_profile_preferences.v2'::text)
            )
        WHERE preferences ->> 'schema_version' = 'search_profile_preferences.v1'
        """
    )
    op.alter_column(
        "search_profiles",
        "preferences",
        server_default=sa.text(_V2_DEFAULT),
    )
    op.create_check_constraint(
        op.f("ck_search_profiles_preferences_contract_valid"),
        "search_profiles",
        "jsonb_typeof(preferences) = 'object' "
        "AND preferences ->> 'schema_version' = 'search_profile_preferences.v2' "
        "AND preferences ?& ARRAY['work_types', 'minimum_budget', 'currency', "
        "'budget_policy', 'languages', 'geographies', 'work_modes', "
        "'excluded_categories', 'source_languages'] "
        "AND (preferences -> 'work_types' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'work_types') = 'array') "
        "AND (preferences -> 'minimum_budget' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'minimum_budget') = 'string') "
        "AND (preferences -> 'currency' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'currency') = 'string') "
        "AND (preferences -> 'budget_policy' = 'null'::jsonb OR "
        "preferences ->> 'budget_policy' IN "
        "('allow_unknown', 'require_explicit')) "
        "AND (preferences -> 'languages' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'languages') = 'array') "
        "AND (preferences -> 'geographies' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'geographies') = 'array') "
        "AND (preferences -> 'work_modes' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'work_modes') = 'array') "
        "AND (preferences -> 'excluded_categories' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'excluded_categories') = 'array') "
        "AND (preferences -> 'source_languages' = 'null'::jsonb OR "
        "preferences -> 'source_languages' IN "
        "('[\"ru\"]'::jsonb, '[\"en\"]'::jsonb, '[\"ru\", \"en\"]'::jsonb))",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_search_profiles_preferences_contract_valid"),
        "search_profiles",
        type_="check",
    )
    op.execute(
        """
        UPDATE search_profiles
        SET preferences =
            preferences - 'source_languages'
            || jsonb_build_object('schema_version', 'search_profile_preferences.v1')
        WHERE preferences ->> 'schema_version' = 'search_profile_preferences.v2'
        """
    )
    op.alter_column(
        "search_profiles",
        "preferences",
        server_default=sa.text(_V1_DEFAULT),
    )
    op.create_check_constraint(
        op.f("ck_search_profiles_preferences_contract_valid"),
        "search_profiles",
        "jsonb_typeof(preferences) = 'object' "
        "AND preferences ->> 'schema_version' = 'search_profile_preferences.v1' "
        "AND preferences ?& ARRAY['work_types', 'minimum_budget', 'currency', "
        "'budget_policy', 'languages', 'geographies', 'work_modes', "
        "'excluded_categories'] "
        "AND (preferences -> 'work_types' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'work_types') = 'array') "
        "AND (preferences -> 'minimum_budget' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'minimum_budget') = 'string') "
        "AND (preferences -> 'currency' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'currency') = 'string') "
        "AND (preferences -> 'budget_policy' = 'null'::jsonb OR "
        "preferences ->> 'budget_policy' IN "
        "('allow_unknown', 'require_explicit')) "
        "AND (preferences -> 'languages' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'languages') = 'array') "
        "AND (preferences -> 'geographies' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'geographies') = 'array') "
        "AND (preferences -> 'work_modes' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'work_modes') = 'array') "
        "AND (preferences -> 'excluded_categories' = 'null'::jsonb OR "
        "jsonb_typeof(preferences -> 'excluded_categories') = 'array')",
    )
    op.drop_index("ix_sources_language", table_name="sources")
    op.drop_constraint(op.f("ck_sources_language_origin_consistent"), "sources", type_="check")
    op.drop_constraint(op.f("ck_sources_language_origin_supported"), "sources", type_="check")
    op.drop_constraint(op.f("ck_sources_language_supported"), "sources", type_="check")
    op.drop_column("sources", "language_origin")
    op.drop_column("sources", "language")
