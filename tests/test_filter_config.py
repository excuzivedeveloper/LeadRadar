import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from freelancer_bot.filters import load_filter_config, load_filter_snapshot, match_text


class FilterConfigTest(unittest.TestCase):
    def test_loads_custom_rules_from_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "filters.json"
            path.write_text(
                json.dumps(
                    {
                        "min_score": 5,
                        "keywords": {"custom order": 5, "python": 1},
                        "stop_words": ["casino"],
                    }
                ),
                encoding="utf-8",
            )

            config = load_filter_config(path)
            result = match_text("Новый custom order на Python", config)

            self.assertEqual(config.min_score, 5)
            self.assertTrue(result.accepted)
            self.assertEqual(result.matched_keywords, ("custom order", "python"))

    def test_rejects_invalid_min_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "filters.json"
            path.write_text(
                json.dumps({"min_score": 0, "keywords": {"order": 1}, "stop_words": []}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "min_score"):
                load_filter_config(path)

    def test_snapshot_hash_matches_the_parsed_bytes(self):
        first = json.dumps(
            {
                "min_score": 5,
                "keywords": {"first snapshot": 5},
                "stop_words": [],
            },
            separators=(",", ":"),
        ).encode("utf-8")
        second = json.dumps(
            {
                "min_score": 9,
                "keywords": {"second snapshot": 9},
                "stop_words": [],
            },
            separators=(",", ":"),
        ).encode("utf-8")
        path = _ChangingBytesPath(first, second)

        snapshot = load_filter_snapshot(path)

        self.assertEqual(path.calls, 1)
        self.assertEqual(snapshot.config.min_score, 5)
        self.assertEqual(snapshot.config.keywords, {"first snapshot": 5})
        self.assertEqual(snapshot.sha256, sha256(first).hexdigest())
        self.assertNotEqual(snapshot.sha256, sha256(second).hexdigest())


class _ChangingBytesPath:
    def __init__(self, first: bytes, second: bytes) -> None:
        self.calls = 0
        self._first = first
        self._second = second

    def read_bytes(self) -> bytes:
        self.calls += 1
        return self._first if self.calls == 1 else self._second

    def __str__(self) -> str:
        return "changing-filters.json"


if __name__ == "__main__":
    unittest.main()
