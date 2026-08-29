from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

from freelancer_bot.config import RuntimeConfig, RuntimeMode
from freelancer_bot.message_prefilter import AnalyzerMessage, MinimalAnalyzerInput
from freelancer_bot.opportunity_analysis import (
    OPENROUTER_CHAT_COMPLETIONS_URL,
    OpenAICompatibleOpportunityAnalyzer,
    opportunity_analysis_provider_available,
    resolve_opportunity_analysis_provider,
)


CANDIDATE = MinimalAnalyzerInput(
    current=AnalyzerMessage(
        raw_message_id=UUID("00000000-0000-0000-0000-000000000001"),
        source_id=1,
        external_source_id="openrouter-test-source",
        external_message_id=1,
        message_date=datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
        message_url="https://t.me/example/1",
        content="Нужен разработчик Telegram-бота",
    ),
    parent=None,
)


def _config(environment: dict[str, str]) -> RuntimeConfig:
    with patch.dict("os.environ", environment, clear=True):
        return RuntimeConfig.from_env(
            mode=RuntimeMode.CHECK_CONFIG,
            env_file=None,
        )


def test_openrouter_resolves_its_own_key_and_default_endpoint():
    config = _config(
        {
            "OPENROUTER_API_KEY": "openrouter-test-secret",
            "OPPORTUNITY_ANALYSIS_PROVIDER": "openrouter",
            "OPPORTUNITY_ANALYSIS_MODEL": "minimax/minimax-m3:free",
        }
    )

    settings = resolve_opportunity_analysis_provider(config)

    assert settings.name == "openrouter"
    assert settings.api_key == "openrouter-test-secret"
    assert settings.api_key_name == "OPENROUTER_API_KEY"
    assert settings.base_url == OPENROUTER_CHAT_COMPLETIONS_URL
    assert opportunity_analysis_provider_available(config) is True


def test_openrouter_normalizes_custom_base_url_without_provider_aliasing():
    for base_url in (
        "https://openrouter.example/api/v1",
        "https://openrouter.example/api/v1/chat/completions",
    ):
        config = _config(
            {
                "OPENROUTER_API_KEY": "openrouter-test-secret",
                "OPENROUTER_BASE_URL": base_url,
                "TOKENROUTER_API_KEY": "tokenrouter-test-secret",
                "OPPORTUNITY_ANALYSIS_PROVIDER": "openrouter",
                "OPPORTUNITY_ANALYSIS_MODEL": "minimax/minimax-m3:free",
            }
        )

        settings = resolve_opportunity_analysis_provider(config)

        assert settings.name == "openrouter"
        assert settings.api_key_name == "OPENROUTER_API_KEY"
        assert settings.api_key == "openrouter-test-secret"
        assert settings.base_url == "https://openrouter.example/api/v1/chat/completions"


def test_openrouter_does_not_borrow_other_provider_credentials():
    config = _config(
        {
            "TOKENROUTER_API_KEY": "tokenrouter-test-secret",
            "OPENAI_API_KEY": "openai-test-secret",
            "OPPORTUNITY_ANALYSIS_PROVIDER": "openrouter",
            "OPPORTUNITY_ANALYSIS_MODEL": "minimax/minimax-m3:free",
        }
    )

    assert opportunity_analysis_provider_available(config) is False


def test_openrouter_uses_json_object_contract_with_strict_local_schema_prompt():
    analyzer = OpenAICompatibleOpportunityAnalyzer(
        api_key="openrouter-test-secret",
        model="minimax/minimax-m3:free",
        provider="openrouter",
        base_url=OPENROUTER_CHAT_COMPLETIONS_URL,
        max_output_attempts=1,
    )

    payload = analyzer._payload(CANDIDATE)

    assert analyzer.provider == "openrouter"
    assert analyzer.model == "minimax/minimax-m3:free"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["model"] == "minimax/minimax-m3:free"
    assert '"schema_version"' in payload["messages"][0]["content"]
    assert '"additionalProperties": false' in payload["messages"][0]["content"]


def test_openrouter_key_is_classified_secret_and_base_url_public():
    assert RuntimeConfig.model_fields["openrouter_api_key"].json_schema_extra == {
        "sensitivity": "secret"
    }
    assert RuntimeConfig.model_fields["openrouter_base_url"].json_schema_extra == {
        "sensitivity": "public"
    }
