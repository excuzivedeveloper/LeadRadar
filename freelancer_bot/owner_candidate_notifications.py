from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import html
import re
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from telethon import Button

from .config import RuntimeConfig
from .profile_discovery import build_profile_discovery_intent
from .persistence.database import Database
from .persistence.owner_candidate_notifications import (
    OwnerSourceCandidateNotificationRepository,
    OwnerSourceCandidateReservationStatus,
)
from .persistence.source_repository import SourceRecord, SourceStatus
from .persistence.search_profiles import (
    SearchProfileConfirmationStatus,
    SearchProfileRepository,
    UserNotFound,
    UserRepository,
)
from .telegram_request_governor import TelegramRequestCategory, TelegramRequestGovernor


MAX_OWNER_CANDIDATE_NOTIFICATIONS_PER_PASS = 10
FRESH_ACTIVITY_WINDOW = timedelta(days=10)
OWNER_CANDIDATE_RELEVANCE_GATE = "strong"
_TELEGRAM_HANDLE_RE = re.compile(r"^@?[a-zA-Z][a-zA-Z0-9_]{4,31}$")


@dataclass(frozen=True)
class TelegramCandidateAddress:
    lookup: str
    url: str
    expected_handle: str | None
    expected_canonical_url: str | None


@dataclass
class OwnerCandidateNotificationSummary:
    profile_gate_ready: bool = False
    profile_id: UUID | None = None
    profile_revision: int | None = None
    discovery_intent_id: UUID | None = None
    relevance_gate: str = OWNER_CANDIDATE_RELEVANCE_GATE
    candidates_considered: int = 0
    activity_probes: int = 0
    fresh_within_10_days: int = 0
    stale_or_empty: int = 0
    unresolvable: int = 0
    already_notified: int = 0
    reserved: int = 0
    sent: int = 0
    failed: int = 0
    no_longer_candidate: int = 0
    identity_changed: int = 0
    source_not_found: int = 0

    def as_lines(self) -> tuple[str, ...]:
        return (
            f"PROFILE_GATE_READY={'YES' if self.profile_gate_ready else 'NO'}",
            f"PROFILE_ID={self.profile_id or 'NONE'}",
            f"PROFILE_REVISION={self.profile_revision or 'NONE'}",
            f"DISCOVERY_INTENT_ID={self.discovery_intent_id or 'NONE'}",
            f"RELEVANCE_GATE={self.relevance_gate}",
            f"CANDIDATES_CONSIDERED={self.candidates_considered}",
            f"ACTIVITY_PROBES={self.activity_probes}",
            f"FRESH_WITHIN_10_DAYS={self.fresh_within_10_days}",
            f"STALE_OR_EMPTY={self.stale_or_empty}",
            f"UNRESOLVABLE={self.unresolvable}",
            f"ALREADY_NOTIFIED={self.already_notified}",
            f"RESERVED={self.reserved}",
            f"SENT={self.sent}",
            f"FAILED={self.failed}",
            f"NO_LONGER_CANDIDATE={self.no_longer_candidate}",
            f"IDENTITY_CHANGED={self.identity_changed}",
            f"SOURCE_NOT_FOUND={self.source_not_found}",
        )


@dataclass(frozen=True)
class _ActivityProbe:
    latest_message_at: datetime | None
    unresolvable: bool = False


class OwnerCandidateNotificationService:
    def __init__(
        self,
        database: Database,
        *,
        repository: OwnerSourceCandidateNotificationRepository | None = None,
        user_repository: UserRepository | None = None,
        search_profile_repository: SearchProfileRepository | None = None,
        clock: Callable[[], datetime] | None = None,
        button_factory: Callable[[str, str], Any] | None = None,
    ) -> None:
        self._database = database
        self._repository = repository or OwnerSourceCandidateNotificationRepository()
        self._user_repository = user_repository or UserRepository()
        self._search_profile_repository = (
            search_profile_repository or SearchProfileRepository()
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._button_factory = button_factory or Button.url

    @classmethod
    def from_config(
        cls,
        config: RuntimeConfig,
        database: Database,
    ) -> "OwnerCandidateNotificationService":
        del config
        return cls(database)

    async def run_once(
        self,
        *,
        config: RuntimeConfig,
        collector_account_id: int,
        user_client: Any,
        bot_client: Any,
        governor: TelegramRequestGovernor,
        limit: int = MAX_OWNER_CANDIDATE_NOTIFICATIONS_PER_PASS,
    ) -> OwnerCandidateNotificationSummary:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if collector_account_id <= 0:
            raise ValueError("collector_account_id must be positive")
        del collector_account_id
        owner_chat_id = config.owner_telegram_user_id
        summary = OwnerCandidateNotificationSummary()
        if owner_chat_id is None:
            return summary

        async with self._database.transaction() as connection:
            try:
                owner = await self._user_repository.get_by_identity(
                    connection,
                    platform="telegram",
                    external_user_id=str(owner_chat_id),
                )
            except UserNotFound:
                return summary
            profiles = await self._search_profile_repository.list_for_user(
                connection,
                user_id=owner.id,
            )
            eligible_profiles = tuple(
                profile
                for profile in profiles
                if profile.is_active
                and profile.is_primary
                and profile.confirmation_status
                == SearchProfileConfirmationStatus.CONFIRMED
            )
            if len(eligible_profiles) != 1:
                return summary
            profile = eligible_profiles[0]
            intent = build_profile_discovery_intent(profile)
            summary.profile_gate_ready = True
            summary.profile_id = profile.id
            summary.profile_revision = profile.revision
            summary.discovery_intent_id = intent.id
            candidates = await self._repository.list_unnotified_candidates(
                connection,
                recipient_chat_id=owner_chat_id,
                search_profile_id=profile.id,
                discovery_intent_id=intent.id,
                profile_revision=profile.revision,
                relevance_class=OWNER_CANDIDATE_RELEVANCE_GATE,
                limit=limit,
            )
        summary.candidates_considered = len(candidates)

        for source in candidates:
            if source.platform != "telegram" or source.lifecycle_status != SourceStatus.CANDIDATE:
                continue
            address = telegram_candidate_address(source)
            if address is None:
                summary.unresolvable += 1
                continue

            summary.activity_probes += 1
            probe = await self._latest_message_at(
                user_client=user_client,
                governor=governor,
                lookup=address.lookup,
            )
            if probe.unresolvable:
                summary.unresolvable += 1
                continue
            latest_message_at = probe.latest_message_at
            if latest_message_at is None:
                summary.stale_or_empty += 1
                continue
            latest_message_at = _aware_utc(latest_message_at)
            now = _aware_utc(self._clock())
            if latest_message_at < now - FRESH_ACTIVITY_WINDOW:
                summary.stale_or_empty += 1
                continue
            summary.fresh_within_10_days += 1

            attempted_at = now
            async with self._database.transaction() as connection:
                result = await self._repository.reserve(
                    connection,
                    source_id=source.id,
                    recipient_chat_id=owner_chat_id,
                    source_identity_snapshot=_identity_snapshot(source),
                    source_url_snapshot=address.url,
                    expected_handle=address.expected_handle,
                    expected_canonical_url=address.expected_canonical_url,
                    latest_message_at=latest_message_at,
                    attempted_at=attempted_at,
                )
            if result.status is OwnerSourceCandidateReservationStatus.ALREADY_NOTIFIED:
                summary.already_notified += 1
                continue
            if result.status is OwnerSourceCandidateReservationStatus.NOT_CANDIDATE:
                summary.no_longer_candidate += 1
                continue
            if result.status is OwnerSourceCandidateReservationStatus.IDENTITY_CHANGED:
                summary.identity_changed += 1
                continue
            if result.status is OwnerSourceCandidateReservationStatus.SOURCE_NOT_FOUND:
                summary.source_not_found += 1
                continue
            reservation = result.reservation
            if reservation is None:
                raise RuntimeError("reserved notification result did not include a row")
            summary.reserved += 1

            try:
                sent_message = await bot_client.send_message(
                    owner_chat_id,
                    _notification_body(reservation.source, latest_message_at, now),
                    parse_mode="html",
                    link_preview=False,
                    buttons=[
                        [
                            self._button_factory(
                                "📲 Открыть канал",
                                address.url,
                            )
                        ]
                    ],
                )
                telegram_message_id = int(getattr(sent_message, "id"))
            except Exception as exc:
                async with self._database.transaction() as connection:
                    await self._repository.mark_failed(
                        connection,
                        notification_id=reservation.id,
                        failure_code=_failure_code(exc),
                        failed_at=_aware_utc(self._clock()),
                    )
                summary.failed += 1
                continue

            async with self._database.transaction() as connection:
                await self._repository.mark_sent(
                    connection,
                    notification_id=reservation.id,
                    telegram_message_id=telegram_message_id,
                    sent_at=_aware_utc(self._clock()),
                )
            summary.sent += 1

        return summary

    async def _latest_message_at(
        self,
        *,
        user_client: Any,
        governor: TelegramRequestGovernor,
        lookup: str,
    ) -> _ActivityProbe:
        try:
            entity = await governor.run(
                TelegramRequestCategory.ENTITY_ACCESS,
                lambda: user_client.get_entity(lookup),
            )
        except Exception:
            return _ActivityProbe(latest_message_at=None, unresolvable=True)

        try:
            async def read_latest() -> datetime | None:
                async for message in user_client.iter_messages(entity, limit=1):
                    date = getattr(message, "date", None)
                    if isinstance(date, datetime):
                        return date
                    return None
                return None

            latest = await governor.run(TelegramRequestCategory.HISTORY, read_latest)
        except Exception:
            return _ActivityProbe(latest_message_at=None)
        return _ActivityProbe(latest_message_at=latest)


def telegram_candidate_address(source: SourceRecord) -> TelegramCandidateAddress | None:
    handle = _safe_handle(source.handle)
    if handle is not None:
        return TelegramCandidateAddress(
            lookup=handle,
            url=f"https://t.me/{handle}",
            expected_handle=handle,
            expected_canonical_url=None,
        )
    canonical = _safe_telegram_channel_url(source.canonical_url)
    if canonical is None:
        return None
    return TelegramCandidateAddress(
        lookup=canonical,
        url=canonical,
        expected_handle=None,
        expected_canonical_url=canonical,
    )


def telegram_source_url(source: SourceRecord) -> str | None:
    address = telegram_candidate_address(source)
    return None if address is None else address.url


def _safe_telegram_channel_url(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"t.me", "telegram.me"}:
        return None
    if parsed.query or parsed.fragment:
        return None
    handle = _safe_handle(parsed.path.strip("/"))
    if handle is None:
        return None
    return f"https://t.me/{handle}"


def _safe_handle(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not _TELEGRAM_HANDLE_RE.fullmatch(candidate):
        return None
    return candidate.removeprefix("@")


def _notification_body(
    source: SourceRecord,
    latest_message_at: datetime,
    now: datetime,
) -> str:
    safe_handle = _safe_handle(source.handle)
    handle = f"@{safe_handle}" if safe_handle else "не указан"
    language = {"ru": "RU", "en": "EN"}.get(source.language or "", "не определён")
    age_days = max(0, (now.date() - latest_message_at.date()).days)
    return (
        "<b>Новый Telegram-кандидат для проверки</b>\n\n"
        f"<b>Источник:</b> {html.escape(source.display_name)}\n"
        f"<b>Handle:</b> {html.escape(handle)}\n"
        f"<b>Язык:</b> {html.escape(language)}\n"
        f"<b>Последнее сообщение:</b> {latest_message_at.date().isoformat()} "
        f"({age_days} дн. назад)\n"
        "<b>Статус:</b> candidate"
    )


def _identity_snapshot(source: SourceRecord) -> dict[str, Any]:
    return {
        "platform": source.platform,
        "external_id": source.external_id,
        "display_name": source.display_name,
        "handle": source.handle,
        "canonical_url": source.canonical_url,
        "language": source.language,
        "lifecycle_status": source.lifecycle_status.value,
    }


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _failure_code(error: Exception) -> str:
    name = error.__class__.__name__
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower()
    return normalized[:64] or "send_failed"
