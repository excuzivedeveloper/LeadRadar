from __future__ import annotations

import re
import unicodedata


MATCHING_CONCEPTS_VERSION = "matching-concepts.v1"

_TOKEN_PATTERN = re.compile(r"[^\W_]+(?:[+#]+)?", re.UNICODE)
_PHRASE_CONCEPTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "web_development",
        (
            "web development",
            "website development",
            "веб разработка",
            "веб-разработка",
        ),
    ),
    (
        "fullstack",
        (
            "full stack",
            "full-stack",
            "fullstack developer",
            "full-stack developer",
            "full-stack разработчик",
            "fullstack разработчик",
        ),
    ),
    ("frontend", ("front end", "front-end")),
    ("backend", ("back end", "back-end")),
    ("nextjs", ("next js", "next.js")),
    ("javascript", ("java script",)),
    ("typescript", ("type script",)),
    ("openai_api", ("openai api", "chatgpt api", "gpt api", "llm api")),
)
_TOKEN_CONCEPTS: dict[str, str] = {
    "web": "web",
    "веб": "web",
    "website": "web",
    "frontend": "frontend",
    "фронтенд": "frontend",
    "фронтэнд": "frontend",
    "backend": "backend",
    "бекенд": "backend",
    "бэкенд": "backend",
    "fullstack": "fullstack",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "react": "react",
    "reactjs": "react",
    "nextjs": "nextjs",
}


def canonical_matching_concepts(text: str) -> frozenset[str]:
    normalized = _normalize(text)
    concepts: set[str] = set()
    for concept, patterns in _PHRASE_CONCEPTS:
        if any(_phrase_matches(normalized, pattern) for pattern in patterns):
            concepts.add(concept)
    for token in _TOKEN_PATTERN.findall(normalized):
        if concept := _TOKEN_CONCEPTS.get(token):
            concepts.add(concept)
    if "web_development" in concepts:
        concepts.add("web")
    return frozenset(concepts)


def canonical_matching_token_sequence(text: str) -> tuple[str, ...]:
    normalized = _normalize(text)
    concepts: list[str] = []
    for concept, patterns in _PHRASE_CONCEPTS:
        if any(_phrase_matches(normalized, pattern) for pattern in patterns):
            concepts.append(concept)
    for token in _TOKEN_PATTERN.findall(normalized):
        if concept := _TOKEN_CONCEPTS.get(token):
            concepts.append(concept)
    if "web_development" in concepts:
        concepts.append("web")
    return tuple(dict.fromkeys(concepts))


def _phrase_matches(text: str, pattern: str) -> bool:
    normalized = _normalize(pattern)
    return re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", text) is not None


def _normalize(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("matching concept input must be a string")
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[\u2010-\u2015]+", "-", normalized)
    return re.sub(r"\s+", " ", normalized).strip()
