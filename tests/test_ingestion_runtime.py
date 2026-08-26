from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from freelancer_bot.config import RuntimeConfig
from freelancer_bot.filters import FilterConfig, FilterConfigSnapshot
from freelancer_bot.ingestion_runtime import _build_worker


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


if __name__ == "__main__":
    unittest.main()
