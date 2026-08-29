from __future__ import annotations

import json
import unittest
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


class OpenRouterOpportunityAnalysisTest(unittest.IsolatedAsyncioTestCase):
    def test_resolves_own_key_and_default_endpoint(self):
        config = _config(
            {
                "OPENROUTER_API_KEY": "openrouter-test-secret",
                "OPPORTUNITY_ANALYSIS_PROVIDER": "openrouter",
                "OPPORTUNITY_ANALYSIS_MODEL": "minimax/minimax-m3:free",
            }
        )

        settings = resolve_opportunity_analysis_provider(config)

        self.assertEqual(settings.name, "openrouter")
        self.assertEqual(settings.api_key, "openrouter-test-secret")
        self.assertEqual(settings.api_key_name, "OPENROUTER_API_KEY")
        self.assertEqual(settings.base_url, OPENROUTER_CHAT_COMPLETIONS_URL)
        self.assertTrue(opportunity_analysis_provider_available(config))

    def test_normalizes_custom_base_url_without_provider_aliasing(self):
        for base_url in (
            "https://openrouter.example/api/v1",
            "https://openrouter.example/api/v1/chat/completions",
        ):
            with self.subTest(base_url=base_url):
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

                self.assertEqual(settings.name, "openrouter")
                self.assertEqual(settings.api_key_name, "OPENROUTER_API_KEY")
                self.assertEqual(settings.api_key, "openrouter-test-secret")
                self.assertEqual(
                    settings.base_url,
                    "https://openrouter.example/api/v1/chat/completions",
                )

    def test_does_not_borrow_other_provider_credentials(self):
        config = _config(
            {
                "TOKENROUTER_API_KEY": "tokenrouter-test-secret",
                "OPENAI_API_KEY": "openai-test-secret",
                "OPPORTUNITY_ANALYSIS_PROVIDER": "openrouter",
                "OPPORTUNITY_ANALYSIS_MODEL": "minimax/minimax-m3:free",
            }
        )

        self.assertFalse(opportunity_analysis_provider_available(config))

    def test_uses_json_object_contract_with_strict_local_schema_prompt(self):
        analyzer = OpenAICompatibleOpportunityAnalyzer(
            api_key="openrouter-test-secret",
            model="minimax/minimax-m3:free",
            provider="openrouter",
            base_url=OPENROUTER_CHAT_COMPLETIONS_URL,
            max_output_attempts=1,
        )

        payload = analyzer._payload(CANDIDATE)

        self.assertEqual(analyzer.provider, "openrouter")
        self.assertEqual(analyzer.model, "minimax/minimax-m3:free")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["model"], "minimax/minimax-m3:free")
        self.assertIn('"schema_version"', payload["messages"][0]["content"])
        self.assertIn(
            '"additionalProperties": false',
            payload["messages"][0]["content"],
        )

    async def test_transport_uses_openrouter_endpoint_and_preserves_identity(self):
        captured = []
        analyzer = OpenAICompatibleOpportunityAnalyzer(
            api_key="openrouter-test-secret",
            model="minimax/minimax-m3:free",
            provider="openrouter",
            base_url=OPENROUTER_CHAT_COMPLETIONS_URL,
            max_output_attempts=1,
        )

        def fake_urlopen(request, timeout):
            captured.append((request, json.loads(request.data), timeout))
            return _Response(_provider_response())

        with patch(
            "freelancer_bot.opportunity_analysis.urllib.request.urlopen",
            fake_urlopen,
        ):
            call = await analyzer.analyze(CANDIDATE)

        self.assertEqual(call.provider, "openrouter")
        self.assertEqual(call.requested_model, "minimax/minimax-m3:free")
        request, payload, timeout = captured[0]
        self.assertEqual(request.full_url, OPENROUTER_CHAT_COMPLETIONS_URL)
        self.assertEqual(
            request.headers["Authorization"],
            "Bearer openrouter-test-secret",
        )
        self.assertEqual(timeout, 45)
        self.assertEqual(payload["response_format"], {"type": "json_object"})

    def test_key_is_secret_and_base_url_is_public(self):
        self.assertEqual(
            RuntimeConfig.model_fields["openrouter_api_key"].json_schema_extra,
            {"sensitivity": "secret"},
        )
        self.assertEqual(
            RuntimeConfig.model_fields["openrouter_base_url"].json_schema_extra,
            {"sensitivity": "public"},
        )


class _Response:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return self.payload.encode("utf-8")


def _config(environment: dict[str, str]) -> RuntimeConfig:
    with patch.dict("os.environ", environment, clear=True):
        return RuntimeConfig.from_env(
            mode=RuntimeMode.CHECK_CONFIG,
            env_file=None,
        )


def _provider_response() -> str:
    analysis = {
        "schema_version": "opportunity_analysis.v1",
        "is_opportunity": True,
        "confidence": 0.94,
        "market_direction": "buyer_to_specialist",
        "intent_stage": "active",
        "opportunity_type": "project",
        "category": "telegram_development",
        "role_title": "Telegram bot developer",
        "skills": ["Python", "Telegram Bot API"],
        "task_summary": "Build a Telegram bot",
        "budget": {
            "known": False,
            "min": None,
            "max": None,
            "currency": None,
            "period": None,
            "explicit": False,
        },
        "work": {
            "remote": True,
            "location": None,
            "full_time": None,
            "part_time": None,
        },
        "language": "ru",
        "contact": {"telegram": None, "email": None, "url": None},
        "quality": {
            "actionability": 0.9,
            "commercial_plausibility": 0.8,
            "specificity": 0.7,
            "credibility": 0.8,
        },
        "red_flags": [],
    }
    return json.dumps(
        {
            "model": "minimax/minimax-m3:free",
            "usage": {
                "prompt_tokens": 17,
                "completion_tokens": 31,
                "total_tokens": 48,
            },
            "choices": [
                {
                    "message": {
                        "content": json.dumps(analysis, ensure_ascii=False),
                    }
                }
            ],
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    unittest.main()
