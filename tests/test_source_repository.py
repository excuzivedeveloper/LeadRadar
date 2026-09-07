import asyncio
import unittest

import sqlalchemy as sa
from alembic import command
from sqlalchemy.exc import IntegrityError

from freelancer_bot.persistence.collector_accounts import CollectorAccountRepository
from freelancer_bot.persistence.database import Database
from freelancer_bot.persistence.schema import (
    source_discovery_lineage,
    source_lifecycle_events,
    source_taxonomy_assignments,
    source_taxonomy_terms,
    sources,
)
from freelancer_bot.persistence.source_repository import (
    InvalidSourceTransition,
    PostgresSourceCatalog,
    SourceLanguageColumnsUnavailable,
    SourceLanguageOrigin,
    SourceIdentityConflict,
    SourceRepository,
    SourceStatus,
)
from postgres_support import (
    TEST_DATABASE_URL,
    alembic_config,
    migrate_to_head,
    temporary_database,
)


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not configured")
class SourceRepositoryTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.database_context = temporary_database()
        self.database_url = self.database_context.__enter__()
        migrate_to_head(self.database_url)
        self.database = Database(self.database_url, pool_size=4, max_overflow=8)
        self.repository = SourceRepository()
        self.collector_accounts = CollectorAccountRepository()

    async def asyncTearDown(self):
        await self.database.close()
        self.database_context.__exit__(None, None, None)

    async def test_valid_lifecycle_and_collector_catalog_expose_only_approved(self):
        approved = await self._create_candidate("approved", "@approved_source")
        candidate = await self._create_candidate("candidate", "@candidate_source")
        rejected = await self._create_candidate("rejected", "@rejected_source")

        async with self.database.transaction() as connection:
            approved = await self.repository.transition(
                connection,
                approved.id,
                SourceStatus.APPROVED,
                reason="operator review passed",
            )
            approved = await self.repository.transition(
                connection,
                approved.id,
                SourceStatus.PAUSED,
                reason="temporary collector pause",
            )
            approved = await self.repository.transition(
                connection,
                approved.id,
                SourceStatus.APPROVED,
                reason="collector access restored",
            )
            approved = await self.repository.update_metadata(
                connection,
                approved.id,
                display_name="Approved source updated",
                access_type="PUBLIC",
                handle="@APPROVED_SOURCE",
                canonical_url="https://t.me/approved_source",
            )
            rejected = await self.repository.transition(
                connection,
                rejected.id,
                SourceStatus.REJECTED,
                reason="not relevant",
            )

        async with self.database.transaction() as connection:
            with self.assertRaisesRegex(
                InvalidSourceTransition,
                "candidate -> paused",
            ):
                await self.repository.transition(
                    connection,
                    candidate.id,
                    SourceStatus.PAUSED,
                    reason="invalid normal transition",
                )

        async with self.database.transaction() as connection:
            collector_account = await self.collector_accounts.ensure(
                connection,
                platform="telegram",
                external_account_id="repository-test-account",
                display_name="Repository test account",
            )

        catalog = PostgresSourceCatalog(self.database, self.repository)
        collector_sources = await catalog.list_approved(
            collector_account_id=collector_account.id,
            platform="telegram",
        )

        self.assertEqual([source.id for source in collector_sources], [approved.id])
        self.assertEqual(collector_sources[0].lifecycle_status, SourceStatus.APPROVED)
        self.assertEqual(collector_sources[0].display_name, "Approved source updated")
        self.assertEqual(collector_sources[0].handle, "@approved_source")
        async with self.database.connect() as connection:
            events = await self.repository.list_lifecycle_events(connection, approved.id)
        self.assertEqual(
            [(event.from_status, event.to_status) for event in events],
            [
                (None, SourceStatus.CANDIDATE),
                (SourceStatus.CANDIDATE, SourceStatus.APPROVED),
                (SourceStatus.APPROVED, SourceStatus.PAUSED),
                (SourceStatus.PAUSED, SourceStatus.APPROVED),
            ],
        )

    async def test_manual_overrides_preserve_source_lineage_taxonomy_and_history(self):
        source = await self._create_candidate("manual", "@manual_source")
        async with self.database.transaction() as connection:
            term_id = await connection.scalar(
                sa.insert(source_taxonomy_terms)
                .values(
                    dimension="category",
                    key="telegram_development",
                    display_name="Telegram development",
                )
                .returning(source_taxonomy_terms.c.id)
            )
            await connection.execute(
                sa.insert(source_taxonomy_assignments).values(
                    source_id=source.id,
                    term_id=term_id,
                )
            )
            source = await self.repository.override(
                connection,
                source.id,
                SourceStatus.PAUSED,
                operator_id="operator-7",
                reason="manual pause",
            )
            source = await self.repository.override(
                connection,
                source.id,
                SourceStatus.REJECTED,
                operator_id="operator-7",
                reason="manual rejection",
            )
            source = await self.repository.override(
                connection,
                source.id,
                SourceStatus.APPROVED,
                operator_id="operator-8",
                reason="manual approval after review",
            )

        async with self.database.connect() as connection:
            events = await self.repository.list_lifecycle_events(connection, source.id)
            lineage = await self.repository.list_lineage(connection, source.id)
            assignments = await connection.scalar(
                sa.select(sa.func.count())
                .select_from(source_taxonomy_assignments)
                .where(source_taxonomy_assignments.c.source_id == source.id)
            )

        self.assertEqual(source.lifecycle_status, SourceStatus.APPROVED)
        self.assertEqual(assignments, 1)
        self.assertEqual(len(lineage), 1)
        self.assertEqual(lineage[0].provider, "repository_seed")
        self.assertEqual(
            [event.to_status for event in events],
            [
                SourceStatus.CANDIDATE,
                SourceStatus.PAUSED,
                SourceStatus.REJECTED,
                SourceStatus.APPROVED,
            ],
        )
        self.assertEqual([event.is_override for event in events], [False, True, True, True])
        self.assertEqual(
            [event.actor_id for event in events[1:]],
            ["operator-7", "operator-7", "operator-8"],
        )

    async def test_platform_external_identity_and_lineage_are_idempotent(self):
        source = await self._create_candidate("identity", "@identity_source")
        with self.assertRaises(SourceIdentityConflict):
            async with self.database.transaction() as connection:
                await self.repository.create_candidate(
                    connection,
                    platform="TELEGRAM",
                    external_id="identity",
                    access_type="public",
                    display_name="Duplicate identity",
                    handle="@identity_duplicate",
                    provider="web_search",
                    lineage_key="result-duplicate",
                )

        async with self.database.transaction() as connection:
            duplicate_created = await self.repository.record_lineage(
                connection,
                source_id=source.id,
                provider="repository_seed",
                lineage_key="fixture:identity",
            )
            second_created = await self.repository.record_lineage(
                connection,
                source_id=source.id,
                provider="telegram_graph",
                lineage_key="graph:identity:2",
                provider_run_id="discovery-run-2",
                seed_reference="@parent_source",
                context={"distance": 1},
            )

        self.assertFalse(duplicate_created)
        self.assertTrue(second_created)
        async with self.database.connect() as connection:
            lineage = await self.repository.list_lineage(connection, source.id)
        self.assertEqual(len(lineage), 2)
        self.assertEqual(lineage[1].provider, "telegram_graph")
        self.assertEqual(lineage[1].provider_run_id, "discovery-run-2")
        self.assertEqual(lineage[1].context, {"distance": 1})

    async def test_source_with_history_cannot_be_deleted(self):
        source = await self._create_candidate("protected", "@protected_source")

        with self.assertRaises(IntegrityError):
            async with self.database.transaction() as connection:
                await connection.execute(sa.delete(sources).where(sources.c.id == source.id))

        async with self.database.connect() as connection:
            self.assertEqual(
                await connection.scalar(
                    sa.select(sa.func.count())
                    .select_from(source_lifecycle_events)
                    .where(source_lifecycle_events.c.source_id == source.id)
                ),
                1,
            )
            self.assertEqual(
                await connection.scalar(
                    sa.select(sa.func.count())
                    .select_from(source_discovery_lineage)
                    .where(source_discovery_lineage.c.source_id == source.id)
                ),
                1,
            )

    async def test_source_language_evidence_preserves_origin_precedence(self):
        source = await self._create_candidate("language", "@language_source")
        async with self.database.transaction() as connection:
            source = await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="en",
                language_origin=SourceLanguageOrigin.DISCOVERY_QUERY,
            )
            self.assertEqual(source.language, "en")
            self.assertEqual(
                source.language_origin,
                SourceLanguageOrigin.DISCOVERY_QUERY,
            )

            source = await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="ru",
                language_origin=SourceLanguageOrigin.DISCOVERY_QUERY,
            )
            self.assertIsNone(source.language)
            self.assertIsNone(source.language_origin)
            self.assertTrue(source.language_conflict)

            source = await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="ru",
                language_origin=SourceLanguageOrigin.AUDIT,
            )
            self.assertEqual(source.language, "ru")
            self.assertEqual(source.language_origin, SourceLanguageOrigin.AUDIT)
            self.assertFalse(source.language_conflict)

            source = await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="en",
                language_origin=SourceLanguageOrigin.DISCOVERY_QUERY,
            )
            self.assertEqual(source.language, "ru")
            self.assertEqual(source.language_origin, SourceLanguageOrigin.AUDIT)

    async def test_same_language_stronger_evidence_promotes_provenance(self):
        promotions = (
            (SourceLanguageOrigin.DISCOVERY_QUERY, SourceLanguageOrigin.AUDIT),
            (SourceLanguageOrigin.DISCOVERY_QUERY, SourceLanguageOrigin.SEED),
            (SourceLanguageOrigin.SEED, SourceLanguageOrigin.AUDIT),
            (SourceLanguageOrigin.SEED, SourceLanguageOrigin.OPERATOR),
            (SourceLanguageOrigin.AUDIT, SourceLanguageOrigin.OPERATOR),
        )
        for initial, stronger in promotions:
            with self.subTest(initial=initial, stronger=stronger):
                source = await self._create_candidate(
                    f"promote-{initial.value}-{stronger.value}",
                    f"@promote_{initial.value}_{stronger.value}",
                )
                async with self.database.transaction() as connection:
                    source = await self.repository.apply_language_evidence(
                        connection,
                        source.id,
                        language="ru",
                        language_origin=initial,
                    )
                    self.assertEqual(source.language, "ru")
                    self.assertEqual(source.language_origin, initial)

                    source = await self.repository.apply_language_evidence(
                        connection,
                        source.id,
                        language="ru",
                        language_origin=stronger,
                    )
                self.assertEqual(source.language, "ru")
                self.assertEqual(source.language_origin, stronger)

    async def test_weaker_same_language_evidence_never_downgrades_origin(self):
        demotions = (
            (SourceLanguageOrigin.AUDIT, SourceLanguageOrigin.DISCOVERY_QUERY),
            (SourceLanguageOrigin.OPERATOR, SourceLanguageOrigin.AUDIT),
            (SourceLanguageOrigin.OPERATOR, SourceLanguageOrigin.SEED),
            (SourceLanguageOrigin.AUDIT, SourceLanguageOrigin.SEED),
        )
        for initial, weaker in demotions:
            with self.subTest(initial=initial, weaker=weaker):
                source = await self._create_candidate(
                    f"keep-{initial.value}-{weaker.value}",
                    f"@keep_{initial.value}_{weaker.value}",
                )
                async with self.database.transaction() as connection:
                    source = await self.repository.apply_language_evidence(
                        connection,
                        source.id,
                        language="ru",
                        language_origin=initial,
                    )
                    source = await self.repository.apply_language_evidence(
                        connection,
                        source.id,
                        language="ru",
                        language_origin=weaker,
                    )
                self.assertEqual(source.language, "ru")
                self.assertEqual(source.language_origin, initial)

    async def test_stronger_contradictory_evidence_wins_deterministically(self):
        cases = (
            ("ru", SourceLanguageOrigin.DISCOVERY_QUERY, "en", SourceLanguageOrigin.AUDIT),
            ("ru", SourceLanguageOrigin.SEED, "en", SourceLanguageOrigin.OPERATOR),
        )
        for language, origin, new_language, new_origin in cases:
            with self.subTest(
                language=language,
                origin=origin,
                new_language=new_language,
                new_origin=new_origin,
            ):
                source = await self._create_candidate(
                    f"strong-{origin.value}-{new_origin.value}",
                    f"@strong_{origin.value}_{new_origin.value}",
                )
                async with self.database.transaction() as connection:
                    source = await self.repository.apply_language_evidence(
                        connection,
                        source.id,
                        language=language,
                        language_origin=origin,
                    )
                    source = await self.repository.apply_language_evidence(
                        connection,
                        source.id,
                        language=new_language,
                        language_origin=new_origin,
                    )
                self.assertEqual(source.language, new_language)
                self.assertEqual(source.language_origin, new_origin)

    async def test_weaker_contradictory_evidence_never_overwrites_stronger_state(self):
        cases = (
            ("ru", SourceLanguageOrigin.AUDIT, "en", SourceLanguageOrigin.DISCOVERY_QUERY),
            ("ru", SourceLanguageOrigin.OPERATOR, "en", SourceLanguageOrigin.SEED),
        )
        for language, origin, new_language, new_origin in cases:
            with self.subTest(
                language=language,
                origin=origin,
                new_language=new_language,
                new_origin=new_origin,
            ):
                source = await self._create_candidate(
                    f"shield-{origin.value}-{new_origin.value}",
                    f"@shield_{origin.value}_{new_origin.value}",
                )
                async with self.database.transaction() as connection:
                    source = await self.repository.apply_language_evidence(
                        connection,
                        source.id,
                        language=language,
                        language_origin=origin,
                    )
                    source = await self.repository.apply_language_evidence(
                        connection,
                        source.id,
                        language=new_language,
                        language_origin=new_origin,
                    )
                self.assertEqual(source.language, language)
                self.assertEqual(source.language_origin, origin)

    async def test_conflicting_discovery_evidence_stays_unresolved(self):
        source = await self._create_candidate("conflict", "@conflict_source")
        async with self.database.transaction() as connection:
            source = await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="ru",
                language_origin=SourceLanguageOrigin.DISCOVERY_QUERY,
            )
            source = await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="en",
                language_origin=SourceLanguageOrigin.DISCOVERY_QUERY,
            )
            self.assertIsNone(source.language)
            self.assertIsNone(source.language_origin)
            self.assertTrue(source.language_conflict)

            source = await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="ru",
                language_origin=SourceLanguageOrigin.DISCOVERY_QUERY,
            )
            self.assertIsNone(source.language)
            self.assertIsNone(source.language_origin)
            self.assertTrue(source.language_conflict)

        async with self.database.connect() as connection:
            durable = await self.repository.get(connection, source.id)
        self.assertIsNone(durable.language)
        self.assertIsNone(durable.language_origin)
        self.assertTrue(durable.language_conflict)

    async def test_audit_resolves_discovery_conflict_and_blocks_later_discovery(self):
        source = await self._create_candidate("resolve", "@resolve_source")
        async with self.database.transaction() as connection:
            await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="ru",
                language_origin=SourceLanguageOrigin.DISCOVERY_QUERY,
            )
            await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="en",
                language_origin=SourceLanguageOrigin.DISCOVERY_QUERY,
            )
            resolved = await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="ru",
                language_origin=SourceLanguageOrigin.AUDIT,
            )
            self.assertEqual(resolved.language, "ru")
            self.assertEqual(
                resolved.language_origin,
                SourceLanguageOrigin.AUDIT,
            )
            self.assertFalse(resolved.language_conflict)

            after = await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="en",
                language_origin=SourceLanguageOrigin.DISCOVERY_QUERY,
            )
        self.assertEqual(after.language, "ru")
        self.assertEqual(after.language_origin, SourceLanguageOrigin.AUDIT)
        self.assertFalse(after.language_conflict)

    async def test_seed_evidence_resolves_discovery_conflict(self):
        source = await self._create_candidate("seed-resolve", "@seed_resolve")
        async with self.database.transaction() as connection:
            await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="ru",
                language_origin=SourceLanguageOrigin.DISCOVERY_QUERY,
            )
            await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="en",
                language_origin=SourceLanguageOrigin.DISCOVERY_QUERY,
            )
            resolved = await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="ru",
                language_origin=SourceLanguageOrigin.SEED,
            )
        self.assertEqual(resolved.language, "ru")
        self.assertEqual(resolved.language_origin, SourceLanguageOrigin.SEED)
        self.assertFalse(resolved.language_conflict)

    async def test_concurrent_evidence_writers_keep_strongest_origin(self):
        source = await self._create_candidate("atomic", "@atomic_source")
        results = await asyncio.gather(
            *(
                self._apply_evidence_in_own_transaction(
                    source.id,
                    language="ru",
                    language_origin=origin,
                )
                for origin in (
                    SourceLanguageOrigin.AUDIT,
                    SourceLanguageOrigin.OPERATOR,
                    SourceLanguageOrigin.SEED,
                    SourceLanguageOrigin.DISCOVERY_QUERY,
                )
            )
        )
        async with self.database.connect() as connection:
            final = await self.repository.get(connection, source.id)
        self.assertTrue(
            all(
                result.language in {None, "ru"}
                for result in results
            )
        )
        self.assertEqual(final.language, "ru")
        self.assertEqual(final.language_origin, SourceLanguageOrigin.OPERATOR)

    async def _apply_evidence_in_own_transaction(
        self,
        source_id: int,
        *,
        language: str,
        language_origin: SourceLanguageOrigin,
    ):
        async with self.database.transaction() as connection:
            return await self.repository.apply_language_evidence(
                connection,
                source_id,
                language=language,
                language_origin=language_origin,
            )

    async def test_metadata_updates_do_not_clear_source_language(self):
        source = await self._create_candidate("metadata-language", "@metadata_lang")
        async with self.database.transaction() as connection:
            source = await self.repository.update_language(
                connection,
                source.id,
                language="ru",
                language_origin=SourceLanguageOrigin.SEED,
            )
            source = await self.repository.update_metadata(
                connection,
                source.id,
                display_name="Metadata Language",
                access_type="public",
                handle="@metadata_lang",
                canonical_url="https://t.me/metadata_lang",
            )
            self.assertEqual(source.language, "ru")
            self.assertEqual(source.language_origin, SourceLanguageOrigin.SEED)

    async def test_metadata_updates_do_not_clear_language_conflict(self):
        source = await self._create_candidate("metadata-conflict", "@metadata_conflict")
        async with self.database.transaction() as connection:
            await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="ru",
                language_origin=SourceLanguageOrigin.DISCOVERY_QUERY,
            )
            conflicted = await self.repository.apply_language_evidence(
                connection,
                source.id,
                language="en",
                language_origin=SourceLanguageOrigin.DISCOVERY_QUERY,
            )
            self.assertTrue(conflicted.language_conflict)

            conflicted = await self.repository.update_metadata(
                connection,
                source.id,
                display_name="Metadata Conflict",
                access_type="public",
                handle="@metadata_conflict",
                canonical_url="https://t.me/metadata_conflict",
            )
            self.assertIsNone(conflicted.language)
            self.assertIsNone(conflicted.language_origin)
            self.assertTrue(conflicted.language_conflict)

            resolved = await self.repository.update_language(
                connection,
                source.id,
                language="ru",
                language_origin=SourceLanguageOrigin.OPERATOR,
            )
            self.assertEqual(resolved.language, "ru")
            self.assertEqual(resolved.language_origin, SourceLanguageOrigin.OPERATOR)
            self.assertFalse(resolved.language_conflict)

    async def test_language_conflict_db_constraint_accepts_only_unresolved_conflicts(self):
        valid_states = (
            ("valid-null-clear", None, None, False),
            ("valid-null-conflict", None, None, True),
            ("valid-ru-audit", "ru", "audit", False),
            ("valid-en-operator", "en", "operator", False),
        )
        for external_id, language, origin, conflict in valid_states:
            with self.subTest(external_id=external_id):
                async with self.database.transaction() as connection:
                    await _insert_source_language_state(
                        connection,
                        external_id=external_id,
                        language=language,
                        language_origin=origin,
                        language_conflict=conflict,
                    )

        invalid_states = (
            ("invalid-ru-audit-conflict", "ru", "audit", True),
            ("invalid-en-operator-conflict", "en", "operator", True),
        )
        for external_id, language, origin, conflict in invalid_states:
            with self.subTest(external_id=external_id):
                with self.assertRaises(IntegrityError):
                    async with self.database.transaction() as connection:
                        await _insert_source_language_state(
                            connection,
                            external_id=external_id,
                            language=language,
                            language_origin=origin,
                            language_conflict=conflict,
                        )

    async def _create_candidate(self, external_id: str, handle: str):
        async with self.database.transaction() as connection:
            return await self.repository.create_candidate(
                connection,
                platform="telegram",
                external_id=external_id,
                access_type="public",
                display_name=f"Source {external_id}",
                handle=handle,
                canonical_url=f"https://t.me/{handle.removeprefix('@')}",
                provider="repository_seed",
                lineage_key=f"fixture:{external_id}",
                provider_run_id="fixture-run-1",
                seed_reference=handle,
                context={"fixture": True},
            )


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not configured")
class SourceLanguageColumnMigrationCompatTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.database_context = temporary_database()
        self.database_url = self.database_context.__enter__()
        self.config = alembic_config(self.database_url)
        command.upgrade(self.config, "20260905_0040")
        self.database = Database(self.database_url, pool_size=1, max_overflow=0)
        self.repository = SourceRepository()

    async def asyncTearDown(self):
        await self.database.close()
        self.database_context.__exit__(None, None, None)

    async def test_pre0041_reads_work_and_language_mutations_fail_closed(self):
        async with self.database.transaction() as connection:
            source = await self.repository.create_candidate(
                connection,
                platform="telegram",
                external_id="pre0041",
                access_type="public",
                display_name="Pre 0041 source",
                handle="@pre0041_source",
                provider="repository_seed",
                lineage_key="fixture:pre0041",
            )
        self.assertEqual(source.language, None)
        self.assertEqual(source.language_origin, None)

        async with self.database.transaction() as connection:
            with self.assertRaises(SourceLanguageColumnsUnavailable):
                await self.repository.update_language(
                    connection,
                    source.id,
                    language="ru",
                    language_origin=SourceLanguageOrigin.OPERATOR,
                )
        async with self.database.transaction() as connection:
            with self.assertRaises(SourceLanguageColumnsUnavailable):
                await self.repository.apply_language_evidence(
                    connection,
                    source.id,
                    language="ru",
                    language_origin=SourceLanguageOrigin.OPERATOR,
                )

        async with self.database.connect() as connection:
            listed = await self.repository.list_sources(connection)
            self.assertEqual(
                [record.language for record in listed],
                [None],
            )
            self.assertEqual(
                [record.language_conflict for record in listed],
                [False],
            )

    async def test_negative_schema_detection_is_not_cached_stale(self):
        from freelancer_bot.persistence.source_repository import (
            _SOURCE_LANGUAGE_COLUMNS_CACHE_KEY,
        )

        engine = self.database.engine
        async with engine.connect() as connection:
            detected_before = await _detect_columns(connection)
            self.assertFalse(detected_before)
            cached = await connection.run_sync(
                lambda sync_connection: sync_connection.info.get(
                    _SOURCE_LANGUAGE_COLUMNS_CACHE_KEY
                )
            )
            # A pre-migration False must not be cached permanently: only
            # positive detection is cached.
            self.assertNotEqual(cached, False)
            # Release the transaction snapshot so catalog inspection after
            # the migration can observe the new columns.
            await connection.commit()

            command.upgrade(self.config, "head")

            # Same physical connection: after 0041 is applied, detection must
            # re-inspect the schema and observe the new columns.
            detected_after = await _detect_columns(connection)
        self.assertTrue(detected_after)

    async def test_pre0041_negative_detection_reinspects_after_migration(self):
        engine = self.database.engine
        async with engine.connect() as connection:
            detected_before = await _detect_columns(connection)
            self.assertFalse(detected_before)

        command.upgrade(self.config, "head")

        async with engine.connect() as connection:
            detected_after = await _detect_columns(connection)
            self.assertTrue(detected_after)


async def _detect_columns(connection):
    from freelancer_bot.persistence import source_repository

    return await source_repository._sources_have_language_columns(connection)


async def _insert_source_language_state(
    connection,
    *,
    external_id: str,
    language: str | None,
    language_origin: str | None,
    language_conflict: bool,
) -> None:
    await connection.execute(
        sources.insert().values(
            platform="telegram",
            external_id=external_id,
            access_type="public",
            lifecycle_status="candidate",
            display_name=f"Source {external_id}",
            handle=f"@{external_id.replace('-', '_')}",
            language=language,
            language_origin=language_origin,
            language_conflict=language_conflict,
        )
    )


if __name__ == "__main__":
    unittest.main()
