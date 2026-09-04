from __future__ import annotations

import unittest

from freelancer_bot.lexical_matching import label_similarity, lexical_concepts
from freelancer_bot.matching_concepts import (
    canonical_matching_concepts,
    canonical_matching_token_sequence,
)


class MatchingConceptTest(unittest.TestCase):
    def test_web_development_canonicalizes_across_ru_and_en(self):
        self.assertIn("web", canonical_matching_concepts("веб"))
        self.assertIn("web", canonical_matching_concepts("web"))
        self.assertIn(
            "web_development",
            canonical_matching_concepts("веб-разработка"),
        )
        self.assertIn(
            "web_development",
            canonical_matching_concepts("web development"),
        )
        self.assertGreater(label_similarity("веб-разработка", "web development"), 0)

    def test_role_family_canonicalizes_without_broad_profession_graph(self):
        self.assertIn(
            "fullstack",
            canonical_matching_concepts("Full-stack разработчик"),
        )
        self.assertIn("fullstack", canonical_matching_concepts("full stack developer"))
        self.assertIn("frontend", canonical_matching_concepts("фронтенд"))
        self.assertIn("frontend", canonical_matching_concepts("frontend"))
        self.assertIn("backend", canonical_matching_concepts("бекенд"))
        self.assertIn("backend", canonical_matching_concepts("бэкенд"))
        self.assertIn("backend", canonical_matching_concepts("backend"))

    def test_specific_technologies_are_preserved_as_specific_concepts(self):
        concepts = canonical_matching_concepts("React Next.js JavaScript TypeScript")

        self.assertGreaterEqual(
            concepts,
            {"react", "nextjs", "javascript", "typescript"},
        )
        self.assertIn("react", lexical_concepts("React"))
        self.assertIn("nextjs", lexical_concepts("Next.js"))
        self.assertNotIn("react", canonical_matching_concepts("OpenCart SEO website"))
        self.assertNotIn("nextjs", canonical_matching_concepts("OpenCart SEO website"))

    def test_negative_boundaries_stay_non_equivalent(self):
        self.assertNotIn("web", canonical_matching_concepts("browser automation"))
        self.assertNotIn(
            "web_development",
            canonical_matching_concepts("web scraping parser"),
        )
        self.assertNotIn("fullstack", canonical_matching_concepts("parser"))
        self.assertNotIn("react", canonical_matching_concepts("SEO"))
        self.assertNotIn("nextjs", canonical_matching_concepts("OpenCart"))

    def test_token_sequence_exposes_shared_hash_features(self):
        ru = canonical_matching_token_sequence(
            "веб-разработка | Full-stack разработчик | React | Next.js"
        )
        en = canonical_matching_token_sequence(
            "web development | full stack developer | React | Next.js"
        )

        self.assertGreaterEqual(
            set(ru) & set(en),
            {"web", "web_development", "fullstack", "react", "nextjs"},
        )


if __name__ == "__main__":
    unittest.main()
