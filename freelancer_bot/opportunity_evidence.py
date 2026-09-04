from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .opportunity_analysis import OpportunityAnalysis
from .persistence.search_profiles import SearchProfileRecord


OPPORTUNITY_ANALYSIS_V2_SCHEMA_VERSION = "opportunity_analysis.v2"
OPPORTUNITY_EVIDENCE_ONTOLOGY_VERSION = "opportunity-evidence-ontology.v1"
OPPORTUNITY_EVIDENCE_SHADOW_VERSION = "opportunity-evidence-shadow.v1"


class EvidenceDimension(str, Enum):
    CAPABILITY = "capability"
    PLATFORM = "platform"
    SOLUTION_TYPE = "solution_type"
    TECHNOLOGY = "technology"
    ACTION_OR_PROBLEM = "action_or_problem"


class EvidenceOrigin(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    DERIVED = "derived"


class EvidenceSource(str, Enum):
    OPPORTUNITY = "opportunity"
    PROFILE = "profile"


class _StrictContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )


class EvidenceItem(_StrictContract):
    dimension: EvidenceDimension
    concept_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    origin: EvidenceOrigin
    source: EvidenceSource
    raw_span: str = Field(min_length=1, max_length=500)
    field_path: str = Field(min_length=1, max_length=120)
    verified: bool
    verifier_version: str = Field(min_length=1, max_length=80)

    @field_validator("concept_id")
    @classmethod
    def validate_concept_id(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", value):
            raise ValueError("concept_id must be a safe lowercase identifier")
        return value

    @field_validator("field_path", "verifier_version")
    @classmethod
    def validate_safe_label(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,119}", value):
            raise ValueError("field path/version must be a safe identifier")
        return value

    @model_validator(mode="after")
    def validate_verified_explicit_span(self) -> EvidenceItem:
        if self.origin is EvidenceOrigin.EXPLICIT and not self.verified:
            raise ValueError("explicit evidence must be verified against a raw span")
        if self.origin is not EvidenceOrigin.EXPLICIT and self.verified:
            raise ValueError("only explicit evidence is raw-span verified")
        return self


class EvidenceAwareMatchItem(_StrictContract):
    dimension: EvidenceDimension
    concept_id: str
    opportunity_origin: EvidenceOrigin
    profile_origin: EvidenceOrigin
    opportunity_span: str
    profile_span: str


class OpportunityAnalysisV2(_StrictContract):
    schema_version: str
    base_schema_version: str
    ontology_version: str
    analysis: OpportunityAnalysis
    evidence: tuple[EvidenceItem, ...]

    @model_validator(mode="after")
    def validate_versions_and_evidence(self) -> OpportunityAnalysisV2:
        if self.schema_version != OPPORTUNITY_ANALYSIS_V2_SCHEMA_VERSION:
            raise ValueError("unsupported opportunity analysis V2 schema version")
        if self.base_schema_version != self.analysis.schema_version:
            raise ValueError("base schema version must match embedded analysis")
        if self.ontology_version != OPPORTUNITY_EVIDENCE_ONTOLOGY_VERSION:
            raise ValueError("unsupported opportunity evidence ontology version")
        identities = [
            (
                item.source,
                item.dimension,
                item.concept_id,
                item.origin,
                _normalize(item.raw_span),
            )
            for item in self.evidence
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate evidence items are not allowed")
        if any(item.source is not EvidenceSource.OPPORTUNITY for item in self.evidence):
            raise ValueError("OpportunityAnalysisV2 may only contain opportunity evidence")
        return self


@dataclass(frozen=True)
class ProfileEvidence:
    schema_version: str
    ontology_version: str
    evidence: tuple[EvidenceItem, ...]


class EvidenceShadowDecision(str, Enum):
    STRONG_ELIGIBLE = "strong_eligible"
    WEAK_OR_GENERIC = "weak_or_generic"
    NO_EVIDENCE_MATCH = "no_evidence_match"


@dataclass(frozen=True)
class EvidenceAwareShadowTrace:
    shadow_version: str
    current_policy_changed: bool
    matches: tuple[EvidenceAwareMatchItem, ...]
    score: Decimal
    decision: EvidenceShadowDecision
    generic_signal_blocked: bool
    deduped_match_count: int
    independent_dimensions: tuple[str, ...]


@dataclass(frozen=True)
class _ConceptRule:
    dimension: EvidenceDimension
    concept_id: str
    label: str
    patterns: tuple[str, ...]
    source_origins: Mapping[EvidenceSource, EvidenceOrigin]
    generic: bool = False


_RULES: tuple[_ConceptRule, ...] = (
    _ConceptRule(
        EvidenceDimension.PLATFORM,
        "vk",
        "VK",
        ("вк", "вконтакте", "в контакте", "vk"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.EXPLICIT,
            EvidenceSource.PROFILE: EvidenceOrigin.EXPLICIT,
        },
    ),
    _ConceptRule(
        EvidenceDimension.PLATFORM,
        "telegram",
        "Telegram",
        ("telegram", "телеграм", "тг"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.EXPLICIT,
            EvidenceSource.PROFILE: EvidenceOrigin.EXPLICIT,
        },
    ),
    _ConceptRule(
        EvidenceDimension.PLATFORM,
        "web",
        "Web",
        ("web", "веб", "сайт", "website", "frontend", "лендинг"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.EXPLICIT,
            EvidenceSource.PROFILE: EvidenceOrigin.EXPLICIT,
        },
        generic=True,
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "react",
        "React",
        ("react", "reactjs"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.EXPLICIT,
            EvidenceSource.PROFILE: EvidenceOrigin.EXPLICIT,
        },
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "nextjs",
        "Next.js",
        ("next.js", "next js", "nextjs"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.EXPLICIT,
            EvidenceSource.PROFILE: EvidenceOrigin.EXPLICIT,
        },
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "fastapi",
        "FastAPI",
        ("fastapi", "fast api"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.EXPLICIT,
            EvidenceSource.PROFILE: EvidenceOrigin.EXPLICIT,
        },
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "python",
        "Python",
        ("python", "питон"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.EXPLICIT,
            EvidenceSource.PROFILE: EvidenceOrigin.EXPLICIT,
        },
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "openai_api",
        "OpenAI-compatible API",
        ("openai api", "openai-compatible api", "chatgpt api", "gpt api", "llm api"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.EXPLICIT,
            EvidenceSource.PROFILE: EvidenceOrigin.EXPLICIT,
        },
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "playwright",
        "Playwright",
        ("playwright",),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.EXPLICIT,
            EvidenceSource.PROFILE: EvidenceOrigin.EXPLICIT,
        },
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "aiogram",
        "aiogram",
        ("aiogram",),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.EXPLICIT,
            EvidenceSource.PROFILE: EvidenceOrigin.EXPLICIT,
        },
    ),
    _ConceptRule(
        EvidenceDimension.SOLUTION_TYPE,
        "ai_assistant",
        "AI assistant",
        ("ии-менеджер", "ии менеджер", "ai assistant", "ai manager", "нейро-менеджер"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.EXPLICIT,
            EvidenceSource.PROFILE: EvidenceOrigin.DERIVED,
        },
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "chat_automation",
        "Chat automation",
        ("чат", "chat", "бот", "bot", "менеджер"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.INFERRED,
            EvidenceSource.PROFILE: EvidenceOrigin.DERIVED,
        },
        generic=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "lead_handling",
        "Lead handling",
        ("лид", "лиды", "заявка", "заявки", "заявок", "lead", "leads"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.INFERRED,
            EvidenceSource.PROFILE: EvidenceOrigin.DERIVED,
        },
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "platform_integration",
        "Platform integration",
        ("интеграция", "подключить", "platform integration", "api", "webhook"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.INFERRED,
            EvidenceSource.PROFILE: EvidenceOrigin.DERIVED,
        },
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "react_next_web",
        "React/Next.js web",
        ("react", "next.js", "next js", "nextjs"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.INFERRED,
            EvidenceSource.PROFILE: EvidenceOrigin.DERIVED,
        },
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "llm_ai_integration",
        "LLM/AI integration",
        ("openai api", "chatgpt api", "gpt api", "llm api", "openai-compatible api"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.INFERRED,
            EvidenceSource.PROFILE: EvidenceOrigin.DERIVED,
        },
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "backend_api",
        "Backend API",
        ("fastapi", "backend api", "бекенд api"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.INFERRED,
            EvidenceSource.PROFILE: EvidenceOrigin.DERIVED,
        },
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "api_webhook_integration",
        "API/webhook integration",
        ("api", "webhook", "вебхук", "вебхуки"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.INFERRED,
            EvidenceSource.PROFILE: EvidenceOrigin.DERIVED,
        },
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "browser_automation",
        "Browser automation",
        ("playwright", "selenium", "browser automation", "браузерная автоматизация"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.INFERRED,
            EvidenceSource.PROFILE: EvidenceOrigin.DERIVED,
        },
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "telegram_automation",
        "Telegram automation",
        ("telegram", "телеграм", "тг", "aiogram"),
        {
            EvidenceSource.OPPORTUNITY: EvidenceOrigin.INFERRED,
            EvidenceSource.PROFILE: EvidenceOrigin.DERIVED,
        },
    ),
)

_GENERIC_CONCEPT_IDS = frozenset(
    rule.concept_id for rule in _RULES if rule.generic
) | frozenset({"automation", "bot", "backend"})


def build_opportunity_analysis_v2(analysis: OpportunityAnalysis) -> OpportunityAnalysisV2:
    evidence = tuple(
        _dedupe_evidence(
            _derive_evidence(_opportunity_fields(analysis), EvidenceSource.OPPORTUNITY)
        )
    )
    return OpportunityAnalysisV2(
        schema_version=OPPORTUNITY_ANALYSIS_V2_SCHEMA_VERSION,
        base_schema_version=analysis.schema_version,
        ontology_version=OPPORTUNITY_EVIDENCE_ONTOLOGY_VERSION,
        analysis=analysis,
        evidence=evidence,
    )


def derive_profile_evidence(profile: SearchProfileRecord) -> ProfileEvidence:
    evidence = tuple(
        _dedupe_evidence(
            _derive_evidence(_profile_fields(profile), EvidenceSource.PROFILE)
        )
    )
    return ProfileEvidence(
        schema_version="search_profile_evidence.v1",
        ontology_version=OPPORTUNITY_EVIDENCE_ONTOLOGY_VERSION,
        evidence=evidence,
    )


def evidence_aware_shadow_trace(
    analysis: OpportunityAnalysis | OpportunityAnalysisV2,
    profile: SearchProfileRecord,
) -> EvidenceAwareShadowTrace:
    opportunity_v2 = (
        analysis
        if isinstance(analysis, OpportunityAnalysisV2)
        else build_opportunity_analysis_v2(analysis)
    )
    profile_evidence = derive_profile_evidence(profile)
    matches = _dedupe_matches(
        _match_evidence(opportunity_v2.evidence, profile_evidence.evidence)
    )
    independent_dimensions = tuple(
        sorted({match.dimension.value for match in matches})
    )
    has_specific_verified = any(
        match.opportunity_origin is EvidenceOrigin.EXPLICIT
        and match.concept_id not in _GENERIC_CONCEPT_IDS
        for match in matches
    )
    generic_signal_blocked = bool(matches) and not (
        has_specific_verified or len(independent_dimensions) >= 2
    )
    if not matches:
        decision = EvidenceShadowDecision.NO_EVIDENCE_MATCH
    elif generic_signal_blocked:
        decision = EvidenceShadowDecision.WEAK_OR_GENERIC
    else:
        decision = EvidenceShadowDecision.STRONG_ELIGIBLE
    score = _score(matches, generic_signal_blocked=generic_signal_blocked)
    return EvidenceAwareShadowTrace(
        shadow_version=OPPORTUNITY_EVIDENCE_SHADOW_VERSION,
        current_policy_changed=False,
        matches=matches,
        score=score,
        decision=decision,
        generic_signal_blocked=generic_signal_blocked,
        deduped_match_count=len(matches),
        independent_dimensions=independent_dimensions,
    )


def explicit_evidence_is_grounded(item: EvidenceItem, fields: Mapping[str, str]) -> bool:
    if item.origin is not EvidenceOrigin.EXPLICIT:
        return False
    value = fields.get(item.field_path)
    return value is not None and _span_in_text(item.raw_span, value)


def _derive_evidence(
    fields: Mapping[str, str],
    source: EvidenceSource,
) -> Iterable[EvidenceItem]:
    for field_path, value in fields.items():
        if not value:
            continue
        normalized = _normalize(value)
        for rule in _RULES:
            origin = rule.source_origins.get(source)
            if origin is None:
                continue
            span = _first_matching_span(normalized, rule.patterns)
            if span is None:
                continue
            verified = origin is EvidenceOrigin.EXPLICIT and _span_in_text(span, value)
            yield EvidenceItem(
                dimension=rule.dimension,
                concept_id=rule.concept_id,
                label=rule.label,
                origin=origin,
                source=source,
                raw_span=span,
                field_path=field_path,
                verified=verified,
                verifier_version="explicit-evidence-verifier.v1",
            )


def _match_evidence(
    opportunity: Iterable[EvidenceItem],
    profile: Iterable[EvidenceItem],
) -> Iterable[EvidenceAwareMatchItem]:
    profile_by_identity = {
        (item.dimension, item.concept_id): item
        for item in profile
    }
    for item in opportunity:
        profile_item = profile_by_identity.get((item.dimension, item.concept_id))
        if profile_item is None:
            continue
        yield EvidenceAwareMatchItem(
            dimension=item.dimension,
            concept_id=item.concept_id,
            opportunity_origin=item.origin,
            profile_origin=profile_item.origin,
            opportunity_span=item.raw_span,
            profile_span=profile_item.raw_span,
        )


def _dedupe_evidence(items: Iterable[EvidenceItem]) -> Iterable[EvidenceItem]:
    seen: set[tuple[EvidenceSource, EvidenceDimension, str]] = set()
    for item in items:
        identity = (item.source, item.dimension, item.concept_id)
        if identity in seen:
            continue
        seen.add(identity)
        yield item


def _dedupe_matches(
    items: Iterable[EvidenceAwareMatchItem],
) -> tuple[EvidenceAwareMatchItem, ...]:
    selected: dict[tuple[EvidenceDimension, str], EvidenceAwareMatchItem] = {}
    for item in items:
        selected.setdefault((item.dimension, item.concept_id), item)
    return tuple(
        selected[key]
        for key in sorted(selected, key=lambda value: (value[0].value, value[1]))
    )


def _score(
    matches: tuple[EvidenceAwareMatchItem, ...],
    *,
    generic_signal_blocked: bool,
) -> Decimal:
    if not matches:
        return Decimal("0.0000")
    weights = {
        EvidenceDimension.PLATFORM: Decimal("0.24"),
        EvidenceDimension.SOLUTION_TYPE: Decimal("0.24"),
        EvidenceDimension.CAPABILITY: Decimal("0.22"),
        EvidenceDimension.TECHNOLOGY: Decimal("0.20"),
        EvidenceDimension.ACTION_OR_PROBLEM: Decimal("0.10"),
    }
    raw = sum((weights[item.dimension] for item in matches), Decimal("0"))
    score = min(Decimal("1"), raw)
    if generic_signal_blocked:
        score = min(score, Decimal("0.3900"))
    return score.quantize(Decimal("0.0001"))


def _opportunity_fields(analysis: OpportunityAnalysis) -> dict[str, str]:
    values: dict[str, str] = {}
    if analysis.category:
        values["analysis.category"] = analysis.category
    if analysis.role_title:
        values["analysis.role_title"] = analysis.role_title
    for index, skill in enumerate(analysis.skills):
        values[f"analysis.skills:{index}"] = skill
    if analysis.task_summary:
        values["analysis.task_summary"] = analysis.task_summary
    return values


def _profile_fields(profile: SearchProfileRecord) -> dict[str, str]:
    values = {
        "profile.semantic_text_original": profile.semantic_text_original,
        "profile.semantic_text_normalized": profile.semantic_text_normalized,
    }
    for field_name, terms in (
        ("roles", profile.roles),
        ("skills", profile.skills),
        ("categories", profile.categories),
    ):
        for index, term in enumerate(terms):
            values[f"profile.{field_name}:{index}"] = term.value
    return values


def _first_matching_span(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        normalized = _normalize(pattern)
        if " " in normalized:
            if re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", text):
                return normalized
            continue
        if re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", text):
            return normalized
    return None


def _span_in_text(span: str, text: str) -> bool:
    normalized_span = _normalize(span)
    normalized_text = _normalize(text)
    return (
        re.search(rf"(?<!\w){re.escape(normalized_span)}(?!\w)", normalized_text)
        is not None
    )


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[\u2010-\u2015]+", "-", normalized)
    return re.sub(r"\s+", " ", normalized).strip()
