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
OPPORTUNITY_EVIDENCE_ONTOLOGY_VERSION = "opportunity-evidence-ontology.v2"
OPPORTUNITY_EVIDENCE_SHADOW_VERSION = "opportunity-evidence-shadow.v2"
PROFILE_EVIDENCE_SCHEMA_VERSION = "search_profile_evidence.v2"


class EvidenceDimension(str, Enum):
    BUSINESS_PROBLEM = "business_problem"
    DESIRED_OUTCOME = "desired_outcome"
    CAPABILITY = "capability"
    PLATFORM = "platform"
    SOLUTION_TYPE = "solution_type"
    TECHNOLOGY = "technology"
    ACTION_OR_PROBLEM = "action_or_problem"
    UNCERTAINTY = "uncertainty"


class EvidenceOrigin(str, Enum):
    RAW_EXPLICIT = "raw_explicit"
    ANALYSIS_INFERRED = "analysis_inferred"
    DERIVED_RULE = "derived_rule"
    SEMANTIC_TEXT_HINT = "semantic_text_hint"


class EvidenceVerification(str, Enum):
    RAW_SPAN_VERIFIED = "raw_span_verified"
    RULE_VERIFIED = "rule_verified"
    MODEL_ONLY = "model_only"


class EvidenceConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidencePolarity(str, Enum):
    POSITIVE = "positive"
    NEGATED = "negated"
    CONTRADICTED = "contradicted"
    UNKNOWN = "unknown"


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
    verification: EvidenceVerification
    confidence: EvidenceConfidence
    polarity: EvidencePolarity
    authoritative: bool
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
    def validate_axes(self) -> EvidenceItem:
        if (
            self.origin is EvidenceOrigin.RAW_EXPLICIT
            and self.verification is not EvidenceVerification.RAW_SPAN_VERIFIED
        ):
            raise ValueError("RAW_EXPLICIT evidence requires RAW_SPAN_VERIFIED")
        if (
            self.verification is EvidenceVerification.MODEL_ONLY
            and self.origin is EvidenceOrigin.RAW_EXPLICIT
        ):
            raise ValueError("MODEL_ONLY cannot claim RAW_EXPLICIT")
        if self.confidence is EvidenceConfidence.LOW and self.authoritative:
            raise ValueError("low-confidence evidence cannot be authoritative")
        if self.polarity is not EvidencePolarity.POSITIVE and self.authoritative:
            raise ValueError("non-positive evidence cannot be authoritative")
        return self

    @property
    def counts_as_positive(self) -> bool:
        return (
            self.authoritative
            and self.polarity is EvidencePolarity.POSITIVE
            and self.confidence is not EvidenceConfidence.LOW
        )


class EvidenceAwareMatchItem(_StrictContract):
    dimension: EvidenceDimension
    concept_id: str
    opportunity_origin: EvidenceOrigin
    profile_origin: EvidenceOrigin
    opportunity_verification: EvidenceVerification
    profile_verification: EvidenceVerification
    opportunity_confidence: EvidenceConfidence
    profile_confidence: EvidenceConfidence
    opportunity_polarity: EvidencePolarity
    profile_polarity: EvidencePolarity
    opportunity_span: str
    profile_span: str
    counts_as_positive: bool


class OpportunityAnalysisV2(_StrictContract):
    schema_version: str
    base_schema_version: str
    ontology_version: str
    analysis: OpportunityAnalysis
    evidence: tuple[EvidenceItem, ...]
    business_problems: tuple[EvidenceItem, ...]
    desired_outcomes: tuple[EvidenceItem, ...]
    solution_types: tuple[EvidenceItem, ...]
    required_capabilities: tuple[EvidenceItem, ...]
    uncertainties: tuple[EvidenceItem, ...]

    @model_validator(mode="after")
    def validate_versions_and_evidence(self) -> OpportunityAnalysisV2:
        if self.schema_version != OPPORTUNITY_ANALYSIS_V2_SCHEMA_VERSION:
            raise ValueError("unsupported opportunity analysis V2 schema version")
        if self.base_schema_version != self.analysis.schema_version:
            raise ValueError("base schema version must match embedded analysis")
        if self.ontology_version != OPPORTUNITY_EVIDENCE_ONTOLOGY_VERSION:
            raise ValueError("unsupported opportunity evidence ontology version")
        if any(item.source is not EvidenceSource.OPPORTUNITY for item in self.evidence):
            raise ValueError("OpportunityAnalysisV2 may only contain opportunity evidence")
        identities = [_evidence_identity(item) for item in self.evidence]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate evidence items are not allowed")
        subsets = {
            EvidenceDimension.BUSINESS_PROBLEM: self.business_problems,
            EvidenceDimension.DESIRED_OUTCOME: self.desired_outcomes,
            EvidenceDimension.SOLUTION_TYPE: self.solution_types,
            EvidenceDimension.CAPABILITY: self.required_capabilities,
            EvidenceDimension.UNCERTAINTY: self.uncertainties,
        }
        for dimension, items in subsets.items():
            if any(item.dimension is not dimension for item in items):
                raise ValueError(f"{dimension.value} subset contains another dimension")
            if not set(items).issubset(set(self.evidence)):
                raise ValueError(f"{dimension.value} subset must come from evidence")
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
    shadow_weights_experimental: bool = True
    shadow_score_not_production_policy: bool = True


@dataclass(frozen=True)
class _ConceptRule:
    dimension: EvidenceDimension
    concept_id: str
    label: str
    patterns: tuple[str, ...]
    raw_explicit: bool = False
    profile_structured: bool = False
    profile_semantic_hint: bool = False
    analysis_inferred: bool = False
    generic: bool = False


_RULES: tuple[_ConceptRule, ...] = (
    _ConceptRule(
        EvidenceDimension.PLATFORM,
        "vk",
        "VK",
        ("вк", "вконтакте", "в контакте", "vk"),
        raw_explicit=True,
        profile_structured=True,
    ),
    _ConceptRule(
        EvidenceDimension.PLATFORM,
        "telegram",
        "Telegram",
        ("telegram", "телеграм", "тг"),
        raw_explicit=True,
        profile_structured=True,
    ),
    _ConceptRule(
        EvidenceDimension.PLATFORM,
        "web",
        "Web",
        ("web", "веб", "сайт", "сайта", "website", "frontend", "лендинг", "portal"),
        raw_explicit=True,
        profile_structured=True,
        generic=True,
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "react",
        "React",
        ("react", "reactjs"),
        raw_explicit=True,
        profile_structured=True,
        profile_semantic_hint=True,
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "nextjs",
        "Next.js",
        ("next.js", "next js", "nextjs"),
        raw_explicit=True,
        profile_structured=True,
        profile_semantic_hint=True,
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "fastapi",
        "FastAPI",
        ("fastapi", "fast api"),
        raw_explicit=True,
        profile_structured=True,
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "python",
        "Python",
        ("python", "питон"),
        raw_explicit=True,
        profile_structured=True,
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "openai_api",
        "OpenAI-compatible API",
        ("openai api", "openai-compatible api", "chatgpt api", "gpt api"),
        raw_explicit=True,
        profile_structured=True,
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "playwright",
        "Playwright",
        ("playwright",),
        raw_explicit=True,
        profile_structured=True,
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "aiogram",
        "aiogram",
        ("aiogram",),
        raw_explicit=True,
        profile_structured=True,
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "postgresql",
        "PostgreSQL",
        ("postgresql", "postgres"),
        raw_explicit=True,
        profile_structured=True,
    ),
    _ConceptRule(
        EvidenceDimension.TECHNOLOGY,
        "redis",
        "Redis",
        ("redis",),
        raw_explicit=True,
        profile_structured=True,
    ),
    _ConceptRule(
        EvidenceDimension.SOLUTION_TYPE,
        "ai_assistant",
        "AI assistant",
        ("ии-менеджер", "ии менеджер", "ai assistant", "ai manager", "нейро-менеджер"),
        raw_explicit=True,
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.SOLUTION_TYPE,
        "booking_bot",
        "Booking bot",
        ("booking bot", "бот бронирования", "запись клиентов"),
        raw_explicit=True,
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.BUSINESS_PROBLEM,
        "lost_requests",
        "Lost requests",
        ("заявки не терялись", "не терялись заявки", "lost requests", "lost leads"),
        raw_explicit=True,
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.DESIRED_OUTCOME,
        "auto_customer_replies",
        "Automatic customer replies",
        ("отвечал клиентам", "отвечает клиентам", "answer customers", "customer replies"),
        raw_explicit=True,
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.DESIRED_OUTCOME,
        "data_to_sheets",
        "Data sent to sheets",
        ("летели в таблицу", "данные в таблицу", "data to spreadsheet", "google sheets"),
        raw_explicit=True,
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.UNCERTAINTY,
        "feasibility_unknown",
        "Feasibility unknown",
        ("можно ли", "не уверен", "feasibility", "is it possible"),
        raw_explicit=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "chat_automation",
        "Chat automation",
        ("чат", "chat", "бот", "bot", "менеджер", "отвечал клиентам"),
        profile_structured=True,
        analysis_inferred=True,
        generic=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "lead_handling",
        "Lead handling",
        ("лид", "лиды", "заявка", "заявки", "заявок", "номер", "номера", "lead", "leads"),
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "routine_automation",
        "Routine automation",
        ("автоматизировать рутину", "рутина", "routine automation", "automation"),
        profile_structured=True,
        analysis_inferred=True,
        generic=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "sheets_automation",
        "Sheets automation",
        ("таблица", "таблицу", "google sheets", "spreadsheet"),
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "classifieds_monitoring",
        "Classifieds monitoring",
        ("объявления", "присылать новые", "classifieds", "new listings"),
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "price_monitoring",
        "Price monitoring",
        ("мониторить цены", "цены", "price monitoring", "monitor prices"),
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "platform_integration",
        "Platform integration",
        ("интеграция", "подключить", "crm integration", "platform integration"),
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "react_next_web",
        "React/Next.js web",
        ("react", "next.js", "next js", "nextjs"),
        profile_structured=True,
        profile_semantic_hint=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "llm_ai_integration",
        "LLM/AI integration",
        ("ai", "llm api", "internal llm api", "openai api", "chatgpt api", "gpt api", "ai integration"),
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "backend_api",
        "Backend API",
        ("fastapi", "backend", "backend api", "бекенд", "бэкенд", "бекенд api", "postgresql", "redis"),
        profile_structured=True,
        analysis_inferred=True,
        generic=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "api_webhook_integration",
        "API/webhook integration",
        ("api", "webhook", "вебхук", "вебхуки"),
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "browser_automation",
        "Browser automation",
        ("playwright", "selenium", "browser automation", "браузерная автоматизация"),
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.CAPABILITY,
        "telegram_automation",
        "Telegram automation",
        ("telegram", "телеграм", "тг", "aiogram"),
        profile_structured=True,
        analysis_inferred=True,
    ),
    _ConceptRule(
        EvidenceDimension.ACTION_OR_PROBLEM,
        "scrape",
        "Scrape",
        ("scraping", "scrape", "парсинг", "парсер", "собирать объявления"),
        profile_structured=True,
        analysis_inferred=True,
    ),
)

_GENERIC_CONCEPT_IDS = frozenset(rule.concept_id for rule in _RULES if rule.generic)


def build_opportunity_analysis_v2(
    analysis: OpportunityAnalysis,
    *,
    raw_message_text: str,
) -> OpportunityAnalysisV2:
    raw_text = _required_text(raw_message_text, "raw_message_text")
    explicit = _derive_raw_explicit_evidence(raw_text, EvidenceSource.OPPORTUNITY)
    inferred = _without_raw_negated_concepts(
        _derive_analysis_inferred_evidence(_opportunity_fields(analysis)),
        explicit,
    )
    evidence = tuple(_dedupe_evidence((*explicit, *inferred)))
    return OpportunityAnalysisV2(
        schema_version=OPPORTUNITY_ANALYSIS_V2_SCHEMA_VERSION,
        base_schema_version=analysis.schema_version,
        ontology_version=OPPORTUNITY_EVIDENCE_ONTOLOGY_VERSION,
        analysis=analysis,
        evidence=evidence,
        business_problems=_filter_dimension(evidence, EvidenceDimension.BUSINESS_PROBLEM),
        desired_outcomes=_filter_dimension(evidence, EvidenceDimension.DESIRED_OUTCOME),
        solution_types=_filter_dimension(evidence, EvidenceDimension.SOLUTION_TYPE),
        required_capabilities=_filter_dimension(evidence, EvidenceDimension.CAPABILITY),
        uncertainties=_filter_dimension(evidence, EvidenceDimension.UNCERTAINTY),
    )


def derive_profile_evidence(profile: SearchProfileRecord) -> ProfileEvidence:
    structured = _derive_profile_structured_evidence(_profile_structured_fields(profile))
    hints = _derive_profile_semantic_hints(_profile_semantic_fields(profile))
    return ProfileEvidence(
        schema_version=PROFILE_EVIDENCE_SCHEMA_VERSION,
        ontology_version=OPPORTUNITY_EVIDENCE_ONTOLOGY_VERSION,
        evidence=tuple(_dedupe_evidence((*structured, *hints))),
    )


def evidence_aware_shadow_trace(
    analysis: OpportunityAnalysisV2,
    profile: SearchProfileRecord,
) -> EvidenceAwareShadowTrace:
    profile_evidence = derive_profile_evidence(profile)
    matches = _dedupe_matches(
        _match_evidence(analysis.evidence, profile_evidence.evidence)
    )
    positive_matches = tuple(match for match in matches if match.counts_as_positive)
    independent_dimensions = tuple(
        sorted({match.dimension.value for match in positive_matches})
    )
    has_specific_supported = any(
        match.concept_id not in _GENERIC_CONCEPT_IDS for match in positive_matches
    )
    non_generic_dimensions = {
        match.dimension.value
        for match in positive_matches
        if match.concept_id not in _GENERIC_CONCEPT_IDS
    }
    generic_signal_blocked = bool(matches) and not (
        has_specific_supported or len(non_generic_dimensions) >= 2
    )
    if not positive_matches:
        decision = EvidenceShadowDecision.NO_EVIDENCE_MATCH
    elif generic_signal_blocked:
        decision = EvidenceShadowDecision.WEAK_OR_GENERIC
    else:
        decision = EvidenceShadowDecision.STRONG_ELIGIBLE
    score = _score(positive_matches, generic_signal_blocked=generic_signal_blocked)
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


def explicit_evidence_is_grounded(item: EvidenceItem, raw_message_text: str) -> bool:
    if item.origin is not EvidenceOrigin.RAW_EXPLICIT:
        return False
    return _span_in_text(item.raw_span, raw_message_text)


def _derive_raw_explicit_evidence(
    raw_message_text: str,
    source: EvidenceSource,
) -> tuple[EvidenceItem, ...]:
    items: list[EvidenceItem] = []
    normalized = _normalize(raw_message_text)
    for rule in _RULES:
        if not rule.raw_explicit:
            continue
        span = _first_matching_span(normalized, rule.patterns)
        if span is None:
            continue
        polarity = _polarity_for_span(span, normalized)
        items.append(
            EvidenceItem(
                dimension=rule.dimension,
                concept_id=rule.concept_id,
                label=rule.label,
                origin=EvidenceOrigin.RAW_EXPLICIT,
                source=source,
                raw_span=span,
                field_path="raw_message_text",
                verification=EvidenceVerification.RAW_SPAN_VERIFIED,
                confidence=EvidenceConfidence.HIGH,
                polarity=polarity,
                authoritative=polarity is EvidencePolarity.POSITIVE,
                verifier_version="explicit-evidence-verifier.v2",
            )
        )
    return tuple(items)


def _without_raw_negated_concepts(
    inferred: tuple[EvidenceItem, ...],
    explicit: tuple[EvidenceItem, ...],
) -> tuple[EvidenceItem, ...]:
    blocked = {
        item.concept_id
        for item in explicit
        if item.polarity is not EvidencePolarity.POSITIVE
    }
    if "react" in blocked or "nextjs" in blocked:
        blocked.add("react_next_web")
    if "telegram" in blocked:
        blocked.add("telegram_automation")
    return tuple(item for item in inferred if item.concept_id not in blocked)


def _derive_analysis_inferred_evidence(
    fields: Mapping[str, str],
) -> tuple[EvidenceItem, ...]:
    items: list[EvidenceItem] = []
    for field_path, value in fields.items():
        normalized = _normalize(value)
        for rule in _RULES:
            if not rule.analysis_inferred:
                continue
            span = _first_matching_span(normalized, rule.patterns)
            if span is None:
                continue
            polarity = _polarity_for_span(span, normalized)
            items.append(
                EvidenceItem(
                    dimension=rule.dimension,
                    concept_id=rule.concept_id,
                    label=rule.label,
                    origin=EvidenceOrigin.ANALYSIS_INFERRED,
                    source=EvidenceSource.OPPORTUNITY,
                    raw_span=span,
                    field_path=field_path,
                    verification=EvidenceVerification.MODEL_ONLY,
                    confidence=EvidenceConfidence.MEDIUM,
                    polarity=polarity,
                    authoritative=polarity is EvidencePolarity.POSITIVE,
                    verifier_version="analysis-inference-verifier.v2",
                )
            )
    return tuple(items)


def _derive_profile_structured_evidence(
    fields: Mapping[str, str],
) -> tuple[EvidenceItem, ...]:
    items: list[EvidenceItem] = []
    for field_path, value in fields.items():
        normalized = _normalize(value)
        for rule in _RULES:
            if not rule.profile_structured:
                continue
            span = _first_matching_span(normalized, rule.patterns)
            if span is None:
                continue
            polarity = _polarity_for_span(span, normalized)
            items.append(
                EvidenceItem(
                    dimension=rule.dimension,
                    concept_id=rule.concept_id,
                    label=rule.label,
                    origin=EvidenceOrigin.DERIVED_RULE,
                    source=EvidenceSource.PROFILE,
                    raw_span=span,
                    field_path=field_path,
                    verification=EvidenceVerification.RULE_VERIFIED,
                    confidence=EvidenceConfidence.HIGH,
                    polarity=polarity,
                    authoritative=polarity is EvidencePolarity.POSITIVE,
                    verifier_version="profile-structured-verifier.v2",
                )
            )
    return tuple(items)


def _derive_profile_semantic_hints(
    fields: Mapping[str, str],
) -> tuple[EvidenceItem, ...]:
    items: list[EvidenceItem] = []
    for field_path, value in fields.items():
        normalized = _normalize(value)
        for rule in _RULES:
            if not rule.profile_semantic_hint:
                continue
            span = _first_matching_span(normalized, rule.patterns)
            if span is None:
                continue
            items.append(
                EvidenceItem(
                    dimension=rule.dimension,
                    concept_id=rule.concept_id,
                    label=rule.label,
                    origin=EvidenceOrigin.SEMANTIC_TEXT_HINT,
                    source=EvidenceSource.PROFILE,
                    raw_span=span,
                    field_path=field_path,
                    verification=EvidenceVerification.MODEL_ONLY,
                    confidence=EvidenceConfidence.LOW,
                    polarity=EvidencePolarity.POSITIVE,
                    authoritative=False,
                    verifier_version="profile-semantic-hint-verifier.v2",
                )
            )
    return tuple(items)


def _match_evidence(
    opportunity: Iterable[EvidenceItem],
    profile: Iterable[EvidenceItem],
) -> Iterable[EvidenceAwareMatchItem]:
    profile_by_identity = {(item.dimension, item.concept_id): item for item in profile}
    for item in opportunity:
        profile_item = profile_by_identity.get((item.dimension, item.concept_id))
        if profile_item is None:
            continue
        counts = item.counts_as_positive and profile_item.counts_as_positive
        yield EvidenceAwareMatchItem(
            dimension=item.dimension,
            concept_id=item.concept_id,
            opportunity_origin=item.origin,
            profile_origin=profile_item.origin,
            opportunity_verification=item.verification,
            profile_verification=profile_item.verification,
            opportunity_confidence=item.confidence,
            profile_confidence=profile_item.confidence,
            opportunity_polarity=item.polarity,
            profile_polarity=profile_item.polarity,
            opportunity_span=item.raw_span,
            profile_span=profile_item.raw_span,
            counts_as_positive=counts,
        )


def _dedupe_evidence(items: Iterable[EvidenceItem]) -> Iterable[EvidenceItem]:
    selected: dict[tuple[EvidenceSource, EvidenceDimension, str], EvidenceItem] = {}
    for item in items:
        identity = (item.source, item.dimension, item.concept_id)
        current = selected.get(identity)
        if current is None or _evidence_rank(item) > _evidence_rank(current):
            selected[identity] = item
    return tuple(
        selected[key]
        for key in sorted(selected, key=lambda value: (value[1].value, value[2]))
    )


def _dedupe_matches(
    items: Iterable[EvidenceAwareMatchItem],
) -> tuple[EvidenceAwareMatchItem, ...]:
    selected: dict[tuple[EvidenceDimension, str], EvidenceAwareMatchItem] = {}
    for item in items:
        identity = (item.dimension, item.concept_id)
        current = selected.get(identity)
        if current is None or _match_rank(item) > _match_rank(current):
            selected[identity] = item
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
        EvidenceDimension.BUSINESS_PROBLEM: Decimal("0.14"),
        EvidenceDimension.DESIRED_OUTCOME: Decimal("0.14"),
        EvidenceDimension.PLATFORM: Decimal("0.18"),
        EvidenceDimension.SOLUTION_TYPE: Decimal("0.18"),
        EvidenceDimension.CAPABILITY: Decimal("0.18"),
        EvidenceDimension.TECHNOLOGY: Decimal("0.14"),
        EvidenceDimension.ACTION_OR_PROBLEM: Decimal("0.04"),
        EvidenceDimension.UNCERTAINTY: Decimal("0.00"),
    }
    raw = sum((weights[item.dimension] for item in matches), Decimal("0"))
    score = min(Decimal("1"), raw)
    if generic_signal_blocked:
        score = min(score, Decimal("0.3900"))
    return score.quantize(Decimal("0.0001"))


def _filter_dimension(
    evidence: tuple[EvidenceItem, ...],
    dimension: EvidenceDimension,
) -> tuple[EvidenceItem, ...]:
    return tuple(item for item in evidence if item.dimension is dimension)


def _evidence_identity(item: EvidenceItem) -> tuple[EvidenceSource, EvidenceDimension, str]:
    return (item.source, item.dimension, item.concept_id)


def _evidence_rank(item: EvidenceItem) -> tuple[int, int, int]:
    verification_rank = {
        EvidenceVerification.RAW_SPAN_VERIFIED: 3,
        EvidenceVerification.RULE_VERIFIED: 2,
        EvidenceVerification.MODEL_ONLY: 1,
    }[item.verification]
    confidence_rank = {
        EvidenceConfidence.HIGH: 3,
        EvidenceConfidence.MEDIUM: 2,
        EvidenceConfidence.LOW: 1,
    }[item.confidence]
    polarity_rank = 0 if item.polarity is EvidencePolarity.POSITIVE else 1
    return (verification_rank, confidence_rank, polarity_rank)


def _match_rank(item: EvidenceAwareMatchItem) -> tuple[int, int]:
    return (
        int(item.counts_as_positive),
        int(item.opportunity_polarity is EvidencePolarity.POSITIVE),
    )


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


def _profile_structured_fields(profile: SearchProfileRecord) -> dict[str, str]:
    values: dict[str, str] = {}
    for field_name, terms in (
        ("roles", profile.roles),
        ("skills", profile.skills),
        ("categories", profile.categories),
    ):
        for index, term in enumerate(terms):
            values[f"profile.{field_name}:{index}"] = term.value
    return values


def _profile_semantic_fields(profile: SearchProfileRecord) -> dict[str, str]:
    return {
        "profile.semantic_text_original": profile.semantic_text_original,
        "profile.semantic_text_normalized": profile.semantic_text_normalized,
    }


def _first_matching_span(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        normalized = _normalize(pattern)
        boundary = rf"(?<!\w){re.escape(normalized)}(?!\w)"
        if re.search(boundary, text):
            return normalized
    return None


def _polarity_for_span(span: str, normalized_text: str) -> EvidencePolarity:
    escaped = re.escape(span)
    negated_patterns = (
        rf"(?<!\w)без\s+{escaped}(?!\w)",
        rf"(?<!\w)without\s+{escaped}(?!\w)",
        rf"(?<!\w)no\s+{escaped}(?!\w)",
        rf"(?<!\w)not\s+{escaped}(?!\w)",
        rf"(?<!\w)не\s+{escaped}(?!\w)",
        rf"(?<!\w){escaped}\s+не\s+(?:нужен|нужна|нужно|нужны)(?!\w)",
        rf"(?<!\w){escaped}\s+not\s+(?:needed|required)(?!\w)",
    )
    if any(re.search(pattern, normalized_text) for pattern in negated_patterns):
        return EvidencePolarity.NEGATED
    return EvidencePolarity.POSITIVE


def _span_in_text(span: str, text: str) -> bool:
    normalized_span = _normalize(span)
    normalized_text = _normalize(text)
    return (
        re.search(rf"(?<!\w){re.escape(normalized_span)}(?!\w)", normalized_text)
        is not None
    )


def _required_text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be blank")
    return normalized


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[\u2010-\u2015]+", "-", normalized)
    return re.sub(r"\s+", " ", normalized).strip()
