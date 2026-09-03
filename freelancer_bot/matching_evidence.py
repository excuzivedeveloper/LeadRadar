from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import unicodedata

from .lexical_matching import lexical_concepts
from .opportunity_analysis import OpportunityAnalysis
from .persistence.search_profiles import SearchProfileRecord


MATCHING_EVIDENCE_SCHEMA_VERSION = "matching-evidence.v1"
MATCHING_EVIDENCE_ONTOLOGY_VERSION = "matching-evidence-ontology.v1"


class EvidenceMatch(str, Enum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EvidenceDimensionMatch:
    value: EvidenceMatch
    opportunity_values: tuple[str, ...]
    profile_values: tuple[str, ...]
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class MatchingEvidence:
    schema_version: str
    ontology_version: str
    capability: EvidenceDimensionMatch
    action_or_problem: EvidenceDimensionMatch
    platform: EvidenceDimensionMatch
    technology: EvidenceDimensionMatch
    constraint: EvidenceDimensionMatch


_PATTERNS: dict[str, tuple[str, ...]] = {
    "telegram": ("telegram", "телеграм", "тг", "бот telegram", "telegram bot"),
    "whatsapp": ("whatsapp", "ватсап", "wa bot"),
    "web": (
        "website",
        "web site",
        "webapp",
        "web app",
        "сайт",
        "лендинг",
        "landing",
        "frontend",
        "фронтенд",
        "dashboard",
    ),
    "browser": ("browser", "браузер", "chrome", "playwright", "selenium"),
    "android": ("android", "kotlin", "mobile app", "мобильное приложение"),
    "google_sheets": ("google sheets", "spreadsheet", "таблица", "таблицы"),
    "discord": ("discord",),
    "slack": ("slack",),
    "python": ("python", "питон"),
    "fastapi": ("fastapi", "fast api"),
    "aiogram": ("aiogram",),
    "telethon": ("telethon",),
    "playwright": ("playwright",),
    "selenium": ("selenium",),
    "react": ("react", "reactjs"),
    "nextjs": ("nextjs", "next.js", "next js"),
    "javascript": ("javascript", "js"),
    "typescript": ("typescript", "ts"),
    "postgresql": ("postgresql", "postgres"),
    "redis": ("redis",),
    "docker": ("docker",),
    "kotlin": ("kotlin",),
    "openai_api": ("openai api", "chatgpt api", "llm api", "gpt api"),
}

_CAPABILITY_RULES: dict[str, tuple[str, ...]] = {
    "telegram_automation": (
        "telegram",
        "телеграм",
        "bot",
        "бот",
        "aiogram",
        "telethon",
        "webhook",
    ),
    "python_backend_api": (
        "python",
        "backend",
        "бекенд",
        "api",
        "fastapi",
        "webhook",
    ),
    "api_webhook_integrations": (
        "api",
        "webhook",
        "integration",
        "интеграция",
        "crm",
        "rest",
        "callback",
    ),
    "business_automation": (
        "automation",
        "автоматизация",
        "workflow",
        "процесс",
        "оператор",
        "routine",
    ),
    "google_sheets_automation": (
        "google sheets",
        "spreadsheet",
        "таблица",
        "таблицы",
        "apps script",
    ),
    "web_scraping": (
        "scraping",
        "parser",
        "парсер",
        "crawl",
        "crawler",
        "data extraction",
    ),
    "monitoring_alerting": (
        "monitoring",
        "мониторинг",
        "alert",
        "уведомления",
        "watcher",
    ),
    "browser_automation": (
        "browser automation",
        "браузерная автоматизация",
        "playwright",
        "selenium",
        "forms",
    ),
    "chrome_extension": ("chrome extension", "расширение chrome", "manifest"),
    "react_next_web": ("react", "nextjs", "next.js", "frontend", "dashboard"),
    "responsive_frontend": ("responsive", "адаптив", "css", "html", "layout"),
    "llm_ai_integration": ("llm", "openai", "gpt", "ai api", "rag", "нейросеть"),
    "docker_vps_deployment": ("docker", "vps", "deploy", "systemd", "nginx"),
    "android_kotlin_utility": ("android", "kotlin", "mobile utility"),
    "fullstack_product_integration": (
        "fullstack",
        "full stack",
        "frontend",
        "backend",
        "mvp",
        "crm",
    ),
}

_ACTION_RULES: dict[str, tuple[str, ...]] = {
    "build": ("build", "develop", "create", "сделать", "разработать", "написать"),
    "integrate": ("integrate", "integration", "подключить", "интеграция"),
    "automate": ("automate", "automation", "автоматизировать", "автоматизация"),
    "moderate": ("moderate", "moderation", "модерация", "модерировать"),
    "write_content": ("copywriting", "prompt writing", "texts", "контент", "тексты"),
    "teach": ("tutor", "teacher", "обучить", "наставник", "репетитор"),
    "scrape": ("scrape", "scraping", "parser", "парсер", "crawl"),
    "deploy": ("deploy", "deployment", "развернуть", "деплой"),
    "monitor": ("monitoring", "alert", "уведомления", "watcher"),
    "test": ("qa", "test", "тестирование", "manual testing"),
}

_PLATFORMS = frozenset(
    {
        "telegram",
        "whatsapp",
        "web",
        "browser",
        "android",
        "google_sheets",
        "discord",
        "slack",
    }
)
_TECHNOLOGIES = frozenset(
    {
        "python",
        "fastapi",
        "aiogram",
        "telethon",
        "playwright",
        "selenium",
        "react",
        "nextjs",
        "javascript",
        "typescript",
        "postgresql",
        "redis",
        "docker",
        "kotlin",
        "openai_api",
    }
)


def derive_matching_evidence(
    analysis: OpportunityAnalysis,
    profile: SearchProfileRecord,
) -> MatchingEvidence:
    opportunity_text = _opportunity_text(analysis)
    profile_text = _profile_text(profile)
    opportunity_capabilities = _capabilities(opportunity_text)
    profile_capabilities = _capabilities(profile_text)
    opportunity_actions = _concepts_for_rules(opportunity_text, _ACTION_RULES)
    profile_actions = _concepts_for_rules(profile_text, _ACTION_RULES)
    opportunity_platforms = _concepts_for_rules(opportunity_text, _PATTERNS) & _PLATFORMS
    profile_platforms = _concepts_for_rules(profile_text, _PATTERNS) & _PLATFORMS
    opportunity_technologies = (
        _concepts_for_rules(opportunity_text, _PATTERNS) & _TECHNOLOGIES
    )
    profile_technologies = _concepts_for_rules(profile_text, _PATTERNS) & _TECHNOLOGIES

    return MatchingEvidence(
        schema_version=MATCHING_EVIDENCE_SCHEMA_VERSION,
        ontology_version=MATCHING_EVIDENCE_ONTOLOGY_VERSION,
        capability=_dimension_match(opportunity_capabilities, profile_capabilities),
        action_or_problem=_action_dimension_match(
            opportunity_actions,
            profile_actions,
        ),
        platform=_dimension_match(opportunity_platforms, profile_platforms),
        technology=_dimension_match(
            opportunity_technologies,
            profile_technologies,
            technology=True,
        ),
        constraint=EvidenceDimensionMatch(
            value=EvidenceMatch.UNKNOWN,
            opportunity_values=(),
            profile_values=(),
            evidence=(),
        ),
    )


def _dimension_match(
    opportunity_values: frozenset[str],
    profile_values: frozenset[str],
    *,
    technology: bool = False,
) -> EvidenceDimensionMatch:
    intersection = tuple(sorted(opportunity_values & profile_values))
    if intersection:
        value = EvidenceMatch.YES
    elif not opportunity_values or not profile_values:
        value = EvidenceMatch.UNKNOWN
    elif technology and _technology_family_compatible(opportunity_values, profile_values):
        value = EvidenceMatch.UNKNOWN
    else:
        value = EvidenceMatch.NO
    return EvidenceDimensionMatch(
        value=value,
        opportunity_values=tuple(sorted(opportunity_values)),
        profile_values=tuple(sorted(profile_values)),
        evidence=intersection,
    )


def _action_dimension_match(
    opportunity_values: frozenset[str],
    profile_values: frozenset[str],
) -> EvidenceDimensionMatch:
    intersection = tuple(sorted(opportunity_values & profile_values))
    if intersection:
        value = EvidenceMatch.YES
        evidence = intersection
    elif not opportunity_values or not profile_values:
        value = EvidenceMatch.UNKNOWN
        evidence = ()
    elif _action_family_compatible(opportunity_values, profile_values):
        value = EvidenceMatch.YES
        evidence = ("execution_family",)
    else:
        value = EvidenceMatch.NO
        evidence = ()
    return EvidenceDimensionMatch(
        value=value,
        opportunity_values=tuple(sorted(opportunity_values)),
        profile_values=tuple(sorted(profile_values)),
        evidence=evidence,
    )


def _action_family_compatible(
    opportunity_values: frozenset[str],
    profile_values: frozenset[str],
) -> bool:
    execution = frozenset(
        {"build", "integrate", "automate", "scrape", "deploy", "monitor", "test"}
    )
    return bool(opportunity_values & execution and profile_values & execution)


def _technology_family_compatible(
    opportunity_values: frozenset[str],
    profile_values: frozenset[str],
) -> bool:
    web_stack = frozenset({"react", "nextjs", "javascript", "typescript"})
    python_stack = frozenset({"python", "fastapi", "aiogram", "telethon"})
    browser_stack = frozenset({"playwright", "selenium"})
    for family in (web_stack, python_stack, browser_stack):
        if opportunity_values & family and profile_values & family:
            return True
    return False


def _capabilities(text: str) -> frozenset[str]:
    capabilities = set(_concepts_for_rules(text, _CAPABILITY_RULES))
    detected = _concepts_for_rules(text, _PATTERNS)
    words = lexical_concepts(text)
    if {"telegram", "python"} <= detected:
        capabilities.add("telegram_automation")
    if {"fastapi", "python"} & detected and (
        "api" in words or "backend" in words or "бекенд" in words
    ):
        capabilities.add("python_backend_api")
    if detected & {"playwright", "selenium"}:
        capabilities.add("browser_automation")
    if detected & {"react", "nextjs"}:
        capabilities.add("react_next_web")
    if "webhook" in words or "api" in words:
        capabilities.add("api_webhook_integrations")
    return frozenset(capabilities)


def _concepts_for_rules(
    text: str,
    rules: dict[str, tuple[str, ...]],
) -> frozenset[str]:
    normalized = _normalize(text)
    words = lexical_concepts(normalized)
    found: set[str] = set()
    for concept, patterns in rules.items():
        if any(_pattern_matches(normalized, words, pattern) for pattern in patterns):
            found.add(concept)
    return frozenset(found)


def _pattern_matches(text: str, words: frozenset[str], pattern: str) -> bool:
    normalized = _normalize(pattern)
    if " " in normalized:
        return normalized in text
    return normalized in words or re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", text) is not None


def _opportunity_text(analysis: OpportunityAnalysis) -> str:
    values = (
        analysis.category,
        analysis.role_title,
        *analysis.skills,
        analysis.task_summary,
        analysis.language,
        analysis.work.location,
        analysis.opportunity_type.value,
    )
    return " | ".join(value for value in values if value)


def _profile_text(profile: SearchProfileRecord) -> str:
    values = [
        profile.semantic_text_original,
        profile.semantic_text_normalized,
        *(term.value for terms in (profile.roles, profile.skills, profile.categories) for term in terms),
    ]
    return " | ".join(value for value in values if value)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip().casefold()
