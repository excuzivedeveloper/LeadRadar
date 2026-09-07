from __future__ import annotations

import re
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock
from uuid import UUID

from freelancer_bot.app import LeadBot
from freelancer_bot.delivery_actions import encode_delivery_action_callback
from freelancer_bot.persistence.database import Database
from freelancer_bot.persistence.delivery_actions import DeliveryActionType
from freelancer_bot.profile_confirmation import ProfileConfirmationService
from freelancer_bot.profile_onboarding import OnboardingProfileError
from freelancer_bot.persistence.search_profiles import SearchProfileEditConflict
from freelancer_bot.telegram_navigation import TelegramNavigationService
from freelancer_bot.telegram_onboarding import TelegramProfileOnboarding
from postgres_support import TEST_DATABASE_URL, migrate_to_head, temporary_database


class _HandlerClient:
    def __init__(self):
        self.handlers = []

    def on(self, event_builder):
        def register(handler):
            self.handlers.append((event_builder, handler))
            return handler

        return register


class _RecordingProfileOnboarding:
    def __init__(self, response):
        self.response = response
        self.begin_calls = []
        self.create_manual = AsyncMock()
        self.set_source_languages = AsyncMock(return_value=response)

    async def begin(self, *, external_user_id: str, description: str):
        self.begin_calls.append((external_user_id, description))
        return self.response


class _TelegramEvent(SimpleNamespace):
    def __init__(
        self,
        *,
        text: str | None = None,
        sender_id: int | None = 4242,
        chat_id: int | None = None,
        is_private: bool | None = True,
    ):
        super().__init__(
            sender_id=sender_id,
            chat_id=sender_id if chat_id is None else chat_id,
            is_private=is_private,
            raw_text=text,
            answer=AsyncMock(),
            respond=AsyncMock(),
        )


class _UnavailableAI:
    async def create_from_description(self, **kwargs):
        raise OnboardingProfileError("provider unavailable")


class TelegramNavigationHandlerTest(unittest.IsolatedAsyncioTestCase):
    async def test_authorized_start_can_subscribe_legacy_chat(self):
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot.config = SimpleNamespace(
            telegram_allowed_user_ids=(4242,),
            legacy_delivery_enabled=True,
        )
        bot._background_enabled = True
        bot.storage = SimpleNamespace(add_subscriber=Mock())
        bot.navigation = SimpleNamespace(home=Mock())
        bot._register_bot_commands()

        start = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "start"
        )
        event = _TelegramEvent(sender_id=4242)

        await start(event)

        bot.storage.add_subscriber.assert_called_once_with(4242)
        event.respond.assert_awaited_once()
        bot.navigation.home.assert_not_called()

    async def test_unauthorized_start_has_no_user_or_subscriber_side_effects(self):
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot.config = SimpleNamespace(
            telegram_allowed_user_ids=(4242,),
            legacy_delivery_enabled=True,
        )
        bot._background_enabled = True
        bot.storage = SimpleNamespace(add_subscriber=Mock())
        bot.navigation = SimpleNamespace(home=Mock())
        bot._register_bot_commands()

        start = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "start"
        )
        event = _TelegramEvent(sender_id=4343)

        await start(event)

        bot.storage.add_subscriber.assert_not_called()
        bot.navigation.home.assert_not_called()
        event.respond.assert_not_awaited()

    async def test_allowlisted_owner_group_keywords_are_blocked(self):
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot.config = SimpleNamespace(telegram_allowed_user_ids=(4242,))
        bot.filter_config = SimpleNamespace(
            keywords={"python": 5},
            stop_words=(),
            min_score=5,
        )
        bot._register_bot_commands()

        keywords = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "keywords"
        )
        event = _TelegramEvent(sender_id=4242, chat_id=-1001234567890, is_private=False)

        await keywords(event)

        event.respond.assert_not_awaited()

    async def test_empty_allowlist_preserves_public_group_keywords_behavior(self):
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot.config = SimpleNamespace(telegram_allowed_user_ids=())
        bot.filter_config = SimpleNamespace(
            keywords={"python": 5},
            stop_words=(),
            min_score=5,
        )
        bot._register_bot_commands()

        keywords = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "keywords"
        )
        event = _TelegramEvent(sender_id=4343, chat_id=-1001234567890, is_private=False)

        await keywords(event)

        event.respond.assert_awaited_once()

    async def test_allowlisted_owner_group_navigation_text_is_blocked_before_ai(self):
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot.config = SimpleNamespace(telegram_allowed_user_ids=(4242,))
        bot._pending_navigation_inputs = {
            "4242": SimpleNamespace(kind="profile_ai"),
        }
        bot.profile_onboarding = SimpleNamespace(begin=AsyncMock())
        bot._register_bot_commands()

        text_input = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "navigation_text_input"
        )
        event = _TelegramEvent(
            text="Python Telegram automation",
            sender_id=4242,
            chat_id=-1001234567890,
            is_private=False,
        )

        await text_input(event)

        bot.profile_onboarding.begin.assert_not_awaited()
        event.respond.assert_not_awaited()

    async def test_authorized_delivery_action_callback_records_action(self):
        delivery_id = UUID("11111111-1111-1111-1111-111111111111")
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot.config = SimpleNamespace(telegram_allowed_user_ids=(4242,))
        bot.delivery_actions = SimpleNamespace(
            record=AsyncMock(
                return_value=SimpleNamespace(
                    event=SimpleNamespace(source_url="https://t.me/source/42")
                )
            )
        )
        bot._register_callback_handlers()
        record_delivery_action = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "record_delivery_action"
        )
        event = _TelegramEvent(sender_id=4242)
        event.data = encode_delivery_action_callback(
            delivery_id,
            DeliveryActionType.NOT_SUITABLE,
        )

        await record_delivery_action(event)

        bot.delivery_actions.record.assert_awaited_once()
        event.answer.assert_awaited_once_with("Понял, учту")

    async def test_unauthorized_delivery_action_callback_has_no_mutation(self):
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot.config = SimpleNamespace(telegram_allowed_user_ids=(4242,))
        bot.delivery_actions = SimpleNamespace(record=AsyncMock())
        bot._register_callback_handlers()
        record_delivery_action = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "record_delivery_action"
        )
        event = _TelegramEvent(sender_id=4343)
        event.data = encode_delivery_action_callback(
            UUID("11111111-1111-1111-1111-111111111111"),
            DeliveryActionType.NOT_SUITABLE,
        )

        await record_delivery_action(event)

        bot.delivery_actions.record.assert_not_awaited()
        event.answer.assert_not_awaited()

    async def test_allowlisted_owner_group_delivery_action_callback_is_blocked(self):
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot.config = SimpleNamespace(telegram_allowed_user_ids=(4242,))
        bot.delivery_actions = SimpleNamespace(record=AsyncMock())
        bot._register_callback_handlers()
        record_delivery_action = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "record_delivery_action"
        )
        event = _TelegramEvent(sender_id=4242, chat_id=-1001234567890, is_private=False)
        event.data = encode_delivery_action_callback(
            UUID("11111111-1111-1111-1111-111111111111"),
            DeliveryActionType.NOT_SUITABLE,
        )

        await record_delivery_action(event)

        bot.delivery_actions.record.assert_not_awaited()
        event.answer.assert_not_awaited()

    async def test_missing_sender_id_does_not_fall_back_to_allowed_chat_id(self):
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot.config = SimpleNamespace(
            telegram_allowed_user_ids=(4242,),
            legacy_delivery_enabled=True,
        )
        bot._background_enabled = True
        bot.storage = SimpleNamespace(add_subscriber=Mock())
        bot.navigation = SimpleNamespace(home=Mock())
        bot._register_bot_commands()

        start = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "start"
        )
        event = _TelegramEvent(sender_id=None, chat_id=4242, is_private=True)

        await start(event)

        bot.storage.add_subscriber.assert_not_called()
        bot.navigation.home.assert_not_called()
        event.respond.assert_not_awaited()

    async def test_unauthorized_free_text_does_not_invoke_onboarding(self):
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot.config = SimpleNamespace(telegram_allowed_user_ids=(4242,))
        bot._pending_navigation_inputs = {
            "4343": SimpleNamespace(kind="profile_ai"),
        }
        bot.profile_onboarding = SimpleNamespace(begin=AsyncMock())
        bot._register_bot_commands()

        text_input = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "navigation_text_input"
        )
        event = _TelegramEvent(text="Python Telegram automation", sender_id=4343)

        await text_input(event)

        bot.profile_onboarding.begin.assert_not_awaited()
        event.respond.assert_not_awaited()

    async def test_new_search_routes_natural_text_to_ai_onboarding_handler(self):
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot._pending_navigation_inputs = {}
        bot.profile_onboarding = _RecordingProfileOnboarding(
            SimpleNamespace(text="Профиль поиска", buttons=(), retryable=False)
        )
        bot._register_bot_commands()
        bot._register_callback_handlers()

        new_search = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "navigation_new_profile"
        )
        text_input = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "navigation_text_input"
        )

        await new_search(_TelegramEvent())
        event = _TelegramEvent(
            text=(
                "Я Python-разработчик и специалист по автоматизации. "
                "Делаю Telegram-ботов, Mini Apps и API-интеграции."
            )
        )
        await text_input(event)

        self.assertEqual(
            bot.profile_onboarding.begin_calls,
            [
                (
                    "4242",
                    "Я Python-разработчик и специалист по автоматизации. "
                    "Делаю Telegram-ботов, Mini Apps и API-интеграции.",
                )
            ],
        )
        bot.profile_onboarding.create_manual.assert_not_awaited()
        self.assertEqual(event.respond.await_args.args[0], "Профиль поиска")
        self.assertNotIn("4242", bot._pending_navigation_inputs)

    async def test_ai_unavailable_is_retryable_and_never_invokes_manual_parser(self):
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot._pending_navigation_inputs = {}
        bot.profile_onboarding = _RecordingProfileOnboarding(
            SimpleNamespace(
                text="Не удалось обработать описание через AI. Попробуйте ещё раз.",
                buttons=(),
                retryable=True,
            )
        )
        bot._register_bot_commands()
        bot._register_callback_handlers()

        new_search = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "navigation_new_profile"
        )
        text_input = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "navigation_text_input"
        )

        await new_search(_TelegramEvent())
        event = _TelegramEvent(text="Нужен Python backend")
        await text_input(event)

        bot.profile_onboarding.create_manual.assert_not_awaited()
        self.assertIn("4242", bot._pending_navigation_inputs)
        self.assertIn("Попробуйте", event.respond.await_args.args[0])

    async def test_source_language_save_callback_persists_once_with_revision(self):
        profile_id = UUID("11111111-2222-3333-4444-555555555555")
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot.config = SimpleNamespace(telegram_allowed_user_ids=(4242,))
        bot._pending_navigation_inputs = {"4242": SimpleNamespace(kind="setting")}
        bot.profile_onboarding = _RecordingProfileOnboarding(
            SimpleNamespace(text="saved", buttons=(), retryable=False)
        )
        bot.navigation = SimpleNamespace(
            settings_for_profile=AsyncMock(
                return_value=SimpleNamespace(text="settings", buttons=())
            )
        )
        bot._register_callback_handlers()
        save = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "navigation_save_source_languages"
        )
        data = f"nav:sls:{profile_id}:7:re".encode("ascii")
        event = _TelegramEvent(sender_id=4242)
        event.data = data
        event.pattern_match = re.match(
            rb"^nav:sls:([0-9a-f-]{36}):(\d+):(re|r|e)$",
            data,
        )

        await save(event)

        bot.profile_onboarding.set_source_languages.assert_awaited_once_with(
            external_user_id="4242",
            profile_id=profile_id,
            source_languages=("ru", "en"),
            expected_revision=7,
        )
        event.answer.assert_awaited_once_with("Настройка сохранена")
        self.assertNotIn("4242", bot._pending_navigation_inputs)

    async def test_stale_source_language_open_callback_discards_mask(self):
        profile_id = UUID("11111111-2222-3333-4444-555555555555")
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot.config = SimpleNamespace(telegram_allowed_user_ids=(4242,))
        bot._pending_navigation_inputs = {}
        bot.navigation = SimpleNamespace(
            source_language_settings=AsyncMock(
                side_effect=SearchProfileEditConflict("stale revision")
            )
        )
        bot._register_callback_handlers()
        open_settings = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "navigation_source_languages"
        )
        data = f"nav:sl:{profile_id}:5:r".encode("ascii")
        event = _TelegramEvent(sender_id=4242)
        event.data = data
        event.pattern_match = re.match(
            rb"^nav:sl:([0-9a-f-]{36}):(\d+):(re|r|e)$",
            data,
        )

        await open_settings(event)

        first_call = bot.navigation.source_language_settings.await_args_list[0]
        self.assertEqual(first_call.kwargs.get("selected"), ("ru",))
        self.assertEqual(first_call.kwargs.get("expected_revision"), 5)
        refresh_call = bot.navigation.source_language_settings.await_args_list[1]
        self.assertNotIn("selected", refresh_call.kwargs)
        self.assertNotIn("expected_revision", refresh_call.kwargs)
        self.assertTrue(event.answer.await_count >= 1)

    async def test_stale_source_language_toggle_callback_discards_mask(self):
        profile_id = UUID("11111111-2222-3333-4444-555555555555")
        bot = LeadBot.__new__(LeadBot)
        bot.bot_client = _HandlerClient()
        bot.config = SimpleNamespace(telegram_allowed_user_ids=(4242,))
        bot._pending_navigation_inputs = {}
        bot.navigation = SimpleNamespace(
            source_language_settings=AsyncMock(
                side_effect=SearchProfileEditConflict("stale revision")
            )
        )
        bot._register_callback_handlers()
        toggle = next(
            handler
            for _, handler in bot.bot_client.handlers
            if handler.__name__ == "navigation_toggle_source_language"
        )
        data = f"nav:slt:{profile_id}:5:r:e".encode("ascii")
        event = _TelegramEvent(sender_id=4242)
        event.data = data
        event.pattern_match = re.match(
            rb"^nav:slt:([0-9a-f-]{36}):(\d+):(re|r|e):([re])$",
            data,
        )

        await toggle(event)

        first_call = bot.navigation.source_language_settings.await_args_list[0]
        self.assertEqual(first_call.kwargs.get("selected"), ("ru", "en"))
        self.assertEqual(first_call.kwargs.get("expected_revision"), 5)
        refresh_call = bot.navigation.source_language_settings.await_args_list[1]
        self.assertNotIn("selected", refresh_call.kwargs)
        self.assertNotIn("expected_revision", refresh_call.kwargs)
        self.assertTrue(event.answer.await_count >= 1)

    async def test_real_onboarding_adapter_marks_provider_error_retryable(self):
        confirmation = SimpleNamespace(show=AsyncMock())
        onboarding = TelegramProfileOnboarding(confirmation, _UnavailableAI())

        response = await onboarding.begin(
            external_user_id="4242",
            description="Нужен Python backend",
        )

        self.assertTrue(response.retryable)
        self.assertIn("Попробуйте отправить описание ещё раз", response.text)
        confirmation.show.assert_not_awaited()


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not configured")
class TelegramNavigationIntegrationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.database_context = temporary_database()
        self.database_url = self.database_context.__enter__()
        migrate_to_head(self.database_url)
        self.database = Database(self.database_url, pool_size=4, max_overflow=8)
        self.confirmation = ProfileConfirmationService(self.database)
        self.onboarding = TelegramProfileOnboarding(self.confirmation, None)
        self.navigation = TelegramNavigationService(self.confirmation)

    async def asyncTearDown(self):
        await self.database.close()
        self.database_context.__exit__(None, None, None)

    async def test_navigation_keeps_profiles_isolated_and_exposes_controls(self):
        first = await self._draft("navigation-owner", "first")
        second = await self._draft("navigation-owner", "second")

        search = await self.navigation.my_search(
            external_user_id="navigation-owner",
        )
        self.assertIn("Мой поиск", search.text)
        profile_callbacks = [
            button.data
            for row in search.buttons
            for button in row
            if button.data.startswith(b"nav:profile:")
            and button.data != b"nav:profile:new"
        ]
        self.assertEqual(len(profile_callbacks), 2)
        self.assertTrue(any(str(first.profile.id).encode() in data for data in profile_callbacks))
        self.assertTrue(any(str(second.profile.id).encode() in data for data in profile_callbacks))

        first_settings = await self.navigation.settings_for_profile(
            external_user_id="navigation-owner",
            profile_id=first.profile.id,
        )
        second_settings = await self.navigation.settings_for_profile(
            external_user_id="navigation-owner",
            profile_id=second.profile.id,
        )
        first_id = str(first.profile.id).encode("ascii")
        second_id = str(second.profile.id).encode("ascii")
        first_controls = [
            button.data
            for row in first_settings.buttons
            for button in row
            if button.data.startswith(b"nav:")
        ]
        second_controls = [
            button.data
            for row in second_settings.buttons
            for button in row
            if button.data.startswith(b"nav:")
        ]
        self.assertTrue(any(first_id in data for data in first_controls))
        self.assertFalse(any(second_id in data for data in first_controls))
        self.assertTrue(any(second_id in data for data in second_controls))
        self.assertTrue(all(len(data) <= 64 for data in first_controls + second_controls))

        source_languages = await self.navigation.source_language_settings(
            external_user_id="navigation-owner",
            profile_id=first.profile.id,
        )
        self.assertIn("Языки источников", source_languages.text)
        self.assertIn("Языки заявок", source_languages.text)
        self.assertTrue(
            all(
                len(button.data) <= 64
                for row in source_languages.buttons
                for button in row
            )
        )
        self.assertIn(
            "[x] Русский",
            [button.label for row in source_languages.buttons for button in row],
        )
        self.assertIn(
            "[x] English",
            [button.label for row in source_languages.buttons for button in row],
        )

        subscription = await self.navigation.subscription(
            external_user_id="navigation-owner",
        )
        self.assertIn("Пробный период ещё не начался", subscription.text)
        self.assertIn("Тариф: 990 RUB/month", subscription.text)

    async def test_owner_subscription_view_shows_unlimited_access_without_trial_authority(self):
        owner_navigation = TelegramNavigationService(
            self.confirmation,
            owner_telegram_user_id=7000201,
        )

        owner_subscription = await owner_navigation.subscription(
            external_user_id="7000201",
        )
        non_owner_subscription = await owner_navigation.subscription(
            external_user_id="7000202",
        )

        self.assertIn("Доступ владельца активен", owner_subscription.text)
        self.assertIn("Срок действия: без ограничений", owner_subscription.text)
        self.assertIn("Подписка для аккаунта владельца не требуется", owner_subscription.text)
        self.assertNotIn("Пробный период", owner_subscription.text)
        self.assertIn("Пробный период ещё не начался", non_owner_subscription.text)
        self.assertIn("Тариф: 990 RUB/month", non_owner_subscription.text)

    async def test_confirmed_profile_settings_can_be_changed_from_navigation_state(self):
        draft = await self._draft("settings-owner", "settings")
        confirmed = await self.confirmation.confirm(
            platform="telegram",
            external_user_id="settings-owner",
            profile_id=draft.profile.id,
            expected_revision=draft.profile.revision,
        )
        activated = await self.confirmation.activate(
            platform="telegram",
            external_user_id="settings-owner",
            profile_id=confirmed.profile.id,
            expected_revision=confirmed.profile.revision,
        )

        profile = await self.navigation.profile(
            external_user_id="settings-owner",
            profile_id=draft.profile.id,
        )
        self.assertIn("Остановить поиск", " ".join(
            button.label for row in profile.buttons for button in row
        ))
        settings = await self.navigation.settings_for_profile(
            external_user_id="settings-owner",
            profile_id=draft.profile.id,
        )
        self.assertIn("Бюджет", " ".join(
            button.label for row in settings.buttons for button in row
        ))
        self.assertFalse(any(
            button.data.endswith(b":roles")
            for row in settings.buttons
            for button in row
        ))

        updated = await self.onboarding.edit_setting(
            external_user_id="settings-owner",
            profile_id=draft.profile.id,
            field="budget",
            value="80000,RUB,allow_unknown",
            expected_revision=activated.profile.profile.revision,
        )
        self.assertIn("от 80000 RUB", updated.text)
        subscription = await self.navigation.subscription(
            external_user_id="settings-owner",
        )
        self.assertIn("Пробный период активирован", subscription.text)
        self.assertIn("действует до", subscription.text)

    async def test_stale_open_toggle_and_save_callbacks_cannot_rebase_mask(self):
        draft = await self._draft("stale-owner", "stale")
        confirmed = await self.confirmation.confirm(
            platform="telegram",
            external_user_id="stale-owner",
            profile_id=draft.profile.id,
            expected_revision=draft.profile.revision,
        )
        await self.confirmation.activate(
            platform="telegram",
            external_user_id="stale-owner",
            profile_id=confirmed.profile.id,
            expected_revision=confirmed.profile.revision,
        )
        view = await self.confirmation.show(
            platform="telegram",
            external_user_id="stale-owner",
            profile_id=draft.profile.id,
        )
        revision_five = view.profile.revision
        saved = await self.confirmation.set_source_languages(
            platform="telegram",
            external_user_id="stale-owner",
            profile_id=draft.profile.id,
            source_languages=("ru",),
            expected_revision=revision_five,
        )
        self.assertEqual(saved.profile.revision, revision_five + 1)

        # Simulate the old rev-5 UI: callback encodes the stale revision and
        # the stale mask "r" (ru only) while the persisted rev-6 state is [en].
        rebased = await self.confirmation.set_source_languages(
            platform="telegram",
            external_user_id="stale-owner",
            profile_id=draft.profile.id,
            source_languages=("en",),
            expected_revision=saved.profile.revision,
        )
        current = await self.confirmation.show(
            platform="telegram",
            external_user_id="stale-owner",
            profile_id=draft.profile.id,
        )
        self.assertEqual(current.profile.preferences.source_languages, ("en",))

        stale_revision = revision_five
        with self.assertRaises(SearchProfileEditConflict):
            await self.navigation.source_language_settings(
                external_user_id="stale-owner",
                profile_id=draft.profile.id,
                selected=("ru",),
                expected_revision=stale_revision,
            )

        refreshed = await self.navigation.source_language_settings(
            external_user_id="stale-owner",
            profile_id=draft.profile.id,
        )
        labels = [
            button.label
            for row in refreshed.buttons
            for button in row
        ]
        self.assertIn("[x] English", labels)
        self.assertNotIn("[x] Русский", labels)
        save_buttons = [
            button.data
            for row in refreshed.buttons
            for button in row
            if button.data.startswith(b"nav:sls:")
        ]
        self.assertEqual(len(save_buttons), 1)
        self.assertIn(f":{current.profile.revision}:".encode("ascii"), save_buttons[0])
        self.assertNotIn(f":{stale_revision}:".encode("ascii"), save_buttons[0])

        with self.assertRaises(SearchProfileEditConflict):
            await self.onboarding.set_source_languages(
                external_user_id="stale-owner",
                profile_id=draft.profile.id,
                source_languages=("ru",),
                expected_revision=stale_revision,
            )
        after = await self.confirmation.show(
            platform="telegram",
            external_user_id="stale-owner",
            profile_id=draft.profile.id,
        )
        self.assertEqual(
            after.profile.preferences.source_languages,
            ("en",),
        )

    async def test_stale_toggle_callback_raises_conflict_for_old_revision(self):
        draft = await self._draft("stale-toggle-owner", "stale-toggle")
        confirmed = await self.confirmation.confirm(
            platform="telegram",
            external_user_id="stale-toggle-owner",
            profile_id=draft.profile.id,
            expected_revision=draft.profile.revision,
        )
        activated = await self.confirmation.activate(
            platform="telegram",
            external_user_id="stale-toggle-owner",
            profile_id=confirmed.profile.id,
            expected_revision=confirmed.profile.revision,
        )
        revision = activated.profile.profile.revision
        saved = await self.confirmation.set_source_languages(
            platform="telegram",
            external_user_id="stale-toggle-owner",
            profile_id=draft.profile.id,
            source_languages=("en",),
            expected_revision=revision,
        )

        with self.assertRaises(SearchProfileEditConflict):
            await self.navigation.source_language_settings(
                external_user_id="stale-toggle-owner",
                profile_id=draft.profile.id,
                selected=("ru",),
                expected_revision=revision,
            )
        current = await self.confirmation.show(
            platform="telegram",
            external_user_id="stale-toggle-owner",
            profile_id=draft.profile.id,
        )
        self.assertEqual(
            current.profile.preferences.source_languages,
            ("en",),
        )
        self.assertEqual(current.profile.revision, saved.profile.revision)

    async def test_current_revision_source_language_callback_still_works(self):
        draft = await self._draft("fresh-owner", "fresh")
        confirmed = await self.confirmation.confirm(
            platform="telegram",
            external_user_id="fresh-owner",
            profile_id=draft.profile.id,
            expected_revision=draft.profile.revision,
        )
        activated = await self.confirmation.activate(
            platform="telegram",
            external_user_id="fresh-owner",
            profile_id=confirmed.profile.id,
            expected_revision=confirmed.profile.revision,
        )
        revision = activated.profile.profile.revision

        response = await self.navigation.source_language_settings(
            external_user_id="fresh-owner",
            profile_id=draft.profile.id,
            selected=("ru", "en"),
            expected_revision=revision,
        )
        labels = [
            button.label
            for row in response.buttons
            for button in row
        ]
        self.assertIn("[x] Русский", labels)
        self.assertIn("[x] English", labels)

    async def _draft(self, external_user_id: str, suffix: str):
        return await self.confirmation.create_manual_draft(
            platform="telegram",
            external_user_id=external_user_id,
            semantic_text=f"Разработчик {suffix} | Python | Telegram",
            roles=(f"Разработчик {suffix}",),
            skills=("Python",),
            categories=("Telegram",),
        )


if __name__ == "__main__":
    unittest.main()
