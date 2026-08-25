from __future__ import annotations

import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import Mock, patch

from freelancer_bot.config import RuntimeConfig
from freelancer_bot.ingestion_runtime import _build_worker


class IngestionRuntimeWorkerTest(unittest.TestCase):
    def test_prefilter_shadow_filter_is_loaded_from_runtime_config(self):
        with tempfile.TemporaryDirectory() as tempdir:
            filters_path = Path(tempdir) / "filters.json"
            filter_bytes = json.dumps(
                {
                    "min_score": 7,
                    "keywords": {"runtime-shadow-keyword": 7},
                    "stop_words": ["runtime-shadow-stop"],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            filters_path.write_bytes(filter_bytes)
            config = RuntimeConfig(filters_path=filters_path, _env_file=None)

            with patch(
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

        _, kwargs = processor.call_args
        self.assertEqual(kwargs["shadow_filter_config"].min_score, 7)
        self.assertEqual(
            kwargs["shadow_filter_config"].keywords,
            {"runtime-shadow-keyword": 7},
        )
        self.assertEqual(
            kwargs["shadow_filter_config_sha256"],
            sha256(filter_bytes).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
