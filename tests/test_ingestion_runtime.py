from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from freelancer_bot.config import RuntimeConfig
from freelancer_bot.filters import FilterConfig, FilterConfigSnapshot
from freelancer_bot.ingestion_runtime import _build_worker
from freelancer_bot.persistence.entitlements import OwnerEntitlementChecker


class IngestionRuntimeWorkerTest(unittest.TestCase):
    def test_prefilter_shadow_filter_is_loaded_from_runtime_config(self):
        with tempfile.TemporaryDirectory() as tempdir:
            filters_path = Path(tempdir) / "filters.json"
            config = RuntimeConfig(filters_path=filters_path, _env_file=None)
            snapshot = FilterConfigSnapshot(
                config=FilterConfig(
                    min_score=7,
                    keywords={"runtime-shadow-keyword": 7},
                    stop_words=("runtime-shadow-stop",),
                ),
                sha256="a" * 64,
            )

            with patch(
                "freelancer_bot.ingestion_runtime.load_filter_snapshot",
                return_value=snapshot,
            ) as load_snapshot, patch(
                "freelancer_bot.ingestion_runtime.RawMessagePrefilterProcessor"
            ) as processor:
                _build_worker(
                    object(),
                    config,
                    logger=Mock(),
                    worker_id="runtime-shadow-test",
                    analyzer=None,
                    delivery_sender=None,
                )

        load_snapshot.assert_called_once_with(filters_path)
        _, kwargs = processor.call_args
        self.assertEqual(kwargs["shadow_filter_config"].min_score, 7)
        self.assertEqual(
            kwargs["shadow_filter_config"].keywords,
            {"runtime-shadow-keyword": 7},
        )
        self.assertEqual(
            kwargs["shadow_filter_config_sha256"],
            "a" * 64,
        )

    def test_delivery_worker_receives_telegram_allowlist(self):
        snapshot = FilterConfigSnapshot(
            config=FilterConfig(
                min_score=1,
                keywords={"python": 1},
                stop_words=(),
            ),
            sha256="b" * 64,
        )
        config = RuntimeConfig(
            telegram_allowed_user_ids=(7000001, 7000002),
            _env_file=None,
        )

        with patch(
            "freelancer_bot.ingestion_runtime.load_filter_snapshot",
            return_value=snapshot,
        ), patch(
            "freelancer_bot.ingestion_runtime.RawMessagePrefilterProcessor"
        ), patch(
            "freelancer_bot.ingestion_runtime.PersonalizedDeliveryJobProcessor"
        ) as delivery_processor:
            _build_worker(
                object(),
                config,
                logger=Mock(),
                worker_id="delivery-allowlist-test",
                analyzer=None,
                delivery_sender=object(),
            )

        _, kwargs = delivery_processor.call_args
        self.assertEqual(
            kwargs["telegram_allowed_user_ids"],
            (7000001, 7000002),
        )

    def test_delivery_worker_uses_owner_entitlement_policy_consistently(self):
        snapshot = FilterConfigSnapshot(
            config=FilterConfig(
                min_score=1,
                keywords={"python": 1},
                stop_words=(),
            ),
            sha256="c" * 64,
        )
        config = RuntimeConfig(
            owner_telegram_user_id=7000001,
            _env_file=None,
        )

        with patch(
            "freelancer_bot.ingestion_runtime.load_filter_snapshot",
            return_value=snapshot,
        ), patch(
            "freelancer_bot.ingestion_runtime.RawMessagePrefilterProcessor"
        ), patch(
            "freelancer_bot.ingestion_runtime.PersonalizedDeliveryService"
        ) as delivery_service, patch(
            "freelancer_bot.ingestion_runtime.PersonalizedDeliveryJobProcessor"
        ) as delivery_processor, patch(
            "freelancer_bot.ingestion_runtime.MatchingDeliveryJobProcessor"
        ) as matching_processor, patch(
            "freelancer_bot.ingestion_runtime.ProfileRematchJobProcessor"
        ) as rematch_processor:
            _build_worker(
                object(),
                config,
                logger=Mock(),
                worker_id="owner-entitlement-runtime-test",
                analyzer=None,
                delivery_sender=object(),
            )

        _, service_kwargs = delivery_service.call_args
        _, send_kwargs = delivery_processor.call_args
        _, matching_kwargs = matching_processor.call_args
        _, rematch_kwargs = rematch_processor.call_args
        self.assertIsInstance(
            service_kwargs["entitlement_checker"],
            OwnerEntitlementChecker,
        )
        self.assertIs(
            send_kwargs["entitlement_checker"],
            service_kwargs["entitlement_checker"],
        )
        self.assertIs(matching_kwargs["deliveries"], delivery_service.return_value)
        self.assertIs(rematch_kwargs["deliveries"], delivery_service.return_value)


if __name__ == "__main__":
    unittest.main()
