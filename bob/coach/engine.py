"""Deterministic Coach Mode suggestion engine."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass

from bob.api.schemas import CoachSuggestion, Source
from bob.config import get_config
from bob.db.database import Database

MIN_CITED_CHUNKS = 2
MAX_SUGGESTIONS = 3
MIN_FEEDBACK_FOR_HEALTH = 3
ROUTINE_FOR_COVERAGE = "daily-checkin"
ROUTINE_FOR_STALENESS = "weekly-review"


@dataclass(frozen=True)
class SuggestionCandidate:
    """Internal candidate suggestion."""

    suggestion_type: str
    text: str
    why: str
    hypothesis: bool
    routine_action: str | None = None
    action: str | None = None
    target: str | None = None
    citations: list[Source] | None = None


def _normalize_text(text: str) -> str:
    """Normalize text for fingerprinting."""
    return " ".join(text.lower().split())


def _fingerprint(suggestion_type: str, text: str) -> str:
    """Hash suggestion type + normalized text."""
    base = f"{suggestion_type}:{_normalize_text(text)}"
    return hashlib.sha256(base.encode()).hexdigest()


def _coverage_suggestion(project: str | None, why: str) -> SuggestionCandidate:
    if project:
        text = (
            f'Add or index documents for this topic under project "{project}" '
            "so future answers can be grounded."
        )
    else:
        text = (
            "Add or index documents for this topic under the appropriate project tag "
            "so future answers can be grounded."
        )
    return SuggestionCandidate(
        suggestion_type="coverage_gaps",
        text=text,
        why=why,
        hypothesis=True,
        routine_action=ROUTINE_FOR_COVERAGE,
        citations=None,
    )


def _priority_from_ratio(value: float, scale: int = 10, *, min_value: int = 1) -> int:
    normalized = max(0.0, min(1.0, value))
    bucket = max(min_value, min(5, int(normalized * scale) or min_value))
    return 6 - bucket


def _priority_from_count(value: int, *, min_value: int = 1, max_value: int = 5) -> int:
    bucket = max(min_value, min(max_value, value))
    return max_value + min_value - bucket


def _staleness_value(buckets: list[dict[str, object]]) -> int:
    if not buckets:
        return 0
    return int(buckets[0].get("count", 0))


def _health_suggestion_candidates(
    *, db: Database, project: str | None
) -> list[tuple[int, SuggestionCandidate]]:
    config = get_config()
    candidates: list[tuple[int, SuggestionCandidate]] = []

    feedback_metrics = db.get_feedback_metrics(project=project)
    total_feedback = int(feedback_metrics.get("total", 0))
    not_found_frequency = float(feedback_metrics.get("not_found_frequency", 0.0))
    if total_feedback >= MIN_FEEDBACK_FOR_HEALTH and not_found_frequency > 0:
        percent = not_found_frequency * 100
        candidates.append(
            (
                _priority_from_ratio(not_found_frequency),
                SuggestionCandidate(
                    suggestion_type="health_not_found",
                    text=(
                        f"{percent:.1f}% of recent feedback entries were marked "
                        "\"didn't answer\". Run a Daily Check-in to capture missing context."
                    ),
                    why="Feedback logs show unanswered questions.",
                    hypothesis=True,
                    routine_action=ROUTINE_FOR_COVERAGE,
                ),
            )
        )

    repeated_questions = feedback_metrics.get("repeated_questions", [])
    if repeated_questions:
        top = repeated_questions[0]
        question = str(top.get("question") or "").strip()
        count = int(top.get("count", 0))
        if question and count > 1:
            candidates.append(
                (
                    _priority_from_count(count),
                SuggestionCandidate(
                    suggestion_type="health_repeated_questions",
                    text=(
                        f'The question "{question}" was asked {count} times in the last 48h. '
                        "Capture a decision or note so it is easier to retrieve."
                    ),
                    why="Repeated questions indicate a coverage gap.",
                    hypothesis=True,
                    action="run_query",
                    target=question,
                ),
            )
        )

    metadata_total = db.get_missing_metadata_total(project=project)
    if metadata_total > 0:
        metadata_deficits = db.get_documents_missing_metadata(limit=1, project=project)
        metadata_target = (
            str(metadata_deficits[0].get("source_path")) if metadata_deficits else ""
        )
        metadata_action = "open_file" if metadata_target else "open_health"
        candidates.append(
            (
                _priority_from_count(metadata_total),
                SuggestionCandidate(
                    suggestion_type="health_metadata",
                    text=(
                        f"{metadata_total} documents are missing required metadata "
                        "(project/date/language). Fixing metadata will improve retrieval quality."
                    ),
                    why="Health metrics show missing metadata fields.",
                    hypothesis=True,
                    action=metadata_action,
                    target=metadata_target or None,
                ),
            )
        )

    permission_metrics = db.get_permission_denial_metrics(project=project)
    permission_total = int(permission_metrics.get("total", 0))
    if permission_total > 0:
        candidates.append(
            (
                _priority_from_count(permission_total),
                SuggestionCandidate(
                    suggestion_type="health_permissions",
                    text=(
                        f"{permission_total} permission denials were logged recently. "
                        "Review Settings > Permissions to allow routine writes."
                    ),
                    why="Routine writes were blocked by current scope or path rules.",
                    hypothesis=True,
                    action="open_settings",
                ),
            )
        )

    threshold = config.health.low_volume_document_threshold
    project_counts = db.get_project_document_counts(project=project)
    low_volume_projects = [
        item for item in project_counts if int(item.get("document_count", 0)) < threshold
    ]
    if low_volume_projects:
        lowest = min(low_volume_projects, key=lambda item: int(item.get("document_count", 0)))
        project_label = (lowest.get("project") or "unknown") if lowest else "unknown"
        doc_count = int(lowest.get("document_count", 0))
        gap = max(0, threshold - doc_count)
        candidates.append(
            (
                _priority_from_count(gap),
                SuggestionCandidate(
                    suggestion_type="health_low_volume",
                    text=(
                        f'Project "{project_label}" has only {doc_count} documents '
                        f"(threshold {threshold}). Index more sources to improve coverage."
                    ),
                    why="Health metrics show low indexed volume.",
                    hypothesis=True,
                    action="open_indexing",
                    target=project_label,
                ),
            )
        )

    hit_rate_threshold = config.health.low_hit_rate_threshold
    search_stats = db.get_search_history_stats(
        window_hours=config.health.search_window_hours,
        min_count=config.health.min_searches_for_rate,
        project=project,
    )
    low_hit_rate_projects = [
        item for item in search_stats if float(item.get("hit_rate", 0.0)) < hit_rate_threshold
    ]
    if low_hit_rate_projects:
        lowest = min(low_hit_rate_projects, key=lambda item: float(item.get("hit_rate", 0.0)))
        project_label = (lowest.get("project") or "unknown") if lowest else "unknown"
        hit_rate = float(lowest.get("hit_rate", 0.0))
        severity = (
            max(0.0, (hit_rate_threshold - hit_rate) / hit_rate_threshold)
            if hit_rate_threshold > 0
            else 0.0
        )
        candidates.append(
            (
                _priority_from_ratio(severity),
                SuggestionCandidate(
                    suggestion_type="health_low_hit_rate",
                    text=(
                        f'Project "{project_label}" has {hit_rate * 100:.0f}% retrieval hit rate '
                        f"(threshold {hit_rate_threshold * 100:.0f}%). Add sources or adjust "
                        "queries to improve coverage."
                    ),
                    why="Recent searches returned few results.",
                    hypothesis=True,
                    action="open_indexing",
                    target=project_label,
                ),
            )
        )

    staleness_buckets = config.health.staleness_buckets_days
    stale_notes = db.get_stale_document_buckets(
        buckets_days=staleness_buckets, source_type="markdown", project=project
    )
    stale_decisions = db.get_stale_decision_buckets(
        buckets_days=staleness_buckets, project=project
    )
    notes_count = _staleness_value(stale_notes)
    decisions_count = _staleness_value(stale_decisions)
    if notes_count or decisions_count:
        priority = _priority_from_count(max(notes_count, decisions_count))
        candidates.append(
            (
                priority,
                SuggestionCandidate(
                    suggestion_type="health_staleness",
                    text=(
                        "Stale notes or decisions were detected. Run a Weekly Review to refresh "
                        "them."
                    ),
                    why="Health metrics show items older than the staleness thresholds.",
                    hypothesis=True,
                    routine_action=ROUTINE_FOR_STALENESS,
                ),
            )
        )

    ingestion_metrics = db.get_ingestion_error_metrics(
        project=project,
        window_hours=config.health.ingestion_error_window_hours,
        limit=config.health.ingestion_error_task_limit,
    )
    ingestion_total = int(ingestion_metrics.get("total", 0))
    if ingestion_total > 0:
        ingestion_recent = ingestion_metrics.get("recent", []) if ingestion_metrics else []
        ingestion_target = ""
        if ingestion_recent:
            ingestion_target = str(ingestion_recent[0].get("source_path") or "")
        ingestion_action = "open_file" if ingestion_target else "open_health"
        candidates.append(
            (
                _priority_from_count(ingestion_total),
                SuggestionCandidate(
                    suggestion_type="health_ingestion",
                    text=(
                        f"{ingestion_total} ingestion errors were logged recently. Review the "
                        "Health page to open failed files."
                    ),
                    why="Indexing errors reduce coverage.",
                    hypothesis=True,
                    action=ingestion_action,
                    target=ingestion_target or None,
                ),
            )
        )

    return candidates


def _allow_health_suggestions(
    *, not_found: bool, source_count: int, overall_confidence: str | None
) -> bool:
    if not_found or source_count < MIN_CITED_CHUNKS:
        return False
    if overall_confidence == "LOW":
        return False
    return True


def _select_staleness_citations(sources: Iterable[Source]) -> list[Source]:
    outdated = [source for source in sources if source.may_be_outdated]
    if outdated:
        return outdated[:2]
    return list(sources)[:1]


def _staleness_suggestion(sources: list[Source]) -> SuggestionCandidate:
    return SuggestionCandidate(
        suggestion_type="staleness",
        text="Consider re-checking this topic before acting on the answer.",
        why="Date confidence is LOW based on older source dates.",
        hypothesis=False,
        routine_action=ROUTINE_FOR_STALENESS,
        citations=_select_staleness_citations(sources),
    )


def _decision_without_rationale_sources(sources: list[Source]) -> list[Source]:
    pattern_decision = re.compile(r"\bdecision\b\s*:", re.IGNORECASE)
    pattern_rationale = re.compile(r"\brationale\b\s*:", re.IGNORECASE)
    matches: list[Source] = []
    for source in sources:
        snippet = source.snippet or ""
        if pattern_decision.search(snippet) and not pattern_rationale.search(snippet):
            matches.append(source)
    return matches


def _capture_hygiene_suggestion(sources: list[Source]) -> SuggestionCandidate:
    citations = sources[:2]
    return SuggestionCandidate(
        suggestion_type="capture_hygiene",
        text=(
            "Add a short Rationale block alongside Decision entries in the cited excerpts "
            "to preserve why the choice was made."
        ),
        why="Multiple Decision sections appear without a Rationale line in the cited snippets.",
        hypothesis=False,
        citations=citations,
    )


def generate_coach_suggestions(
    *,
    sources: list[Source],
    overall_confidence: str | None,
    not_found: bool,
    project: str | None,
    coach_enabled: bool,
    cooldown_days: int,
    db: Database,
    override_cooldown: bool = False,
) -> list[CoachSuggestion]:
    """Generate deterministic Coach Mode suggestions."""
    if not coach_enabled:
        return []

    project_key = project or "all"
    candidates: list[SuggestionCandidate] = []

    if not_found:
        candidates.append(_coverage_suggestion(project, "No sources matched this query."))
    else:
        if len(sources) < MIN_CITED_CHUNKS:
            candidates.append(
                _coverage_suggestion(project, f"Fewer than {MIN_CITED_CHUNKS} sources were cited.")
            )
        if overall_confidence == "LOW":
            candidates.append(_staleness_suggestion(sources))
        decision_without_rationale = _decision_without_rationale_sources(sources)
        if len(decision_without_rationale) >= 2:
            candidates.append(_capture_hygiene_suggestion(decision_without_rationale))

    # Gate: only coverage suggestions when evidence is thin or not found.
    if not_found or len(sources) < MIN_CITED_CHUNKS:
        candidates = [c for c in candidates if c.suggestion_type == "coverage_gaps"]

    # Gate: LOW confidence => at most one suggestion.
    if overall_confidence == "LOW" and candidates:
        staleness = [c for c in candidates if c.suggestion_type == "staleness"]
        candidates = staleness[:1] if staleness else candidates[:1]

    # Apply cooldown and dedupe by fingerprint.
    suggestions: list[CoachSuggestion] = []
    seen: set[str] = set()
    routine_actions: set[str] = set()
    for candidate in candidates:
        if not override_cooldown and db.is_suggestion_type_in_cooldown(
            project=project_key,
            suggestion_type=candidate.suggestion_type,
            cooldown_days=cooldown_days,
        ):
            continue

        suggestion_id = _fingerprint(candidate.suggestion_type, candidate.text)
        if suggestion_id in seen:
            continue
        seen.add(suggestion_id)

        suggestions.append(
            CoachSuggestion(
                id=suggestion_id,
                type=candidate.suggestion_type,
                text=candidate.text,
                why=candidate.why,
                hypothesis=candidate.hypothesis,
                routine_action=candidate.routine_action,
                action=candidate.action,
                target=candidate.target,
                citations=candidate.citations,
            )
        )
        if candidate.routine_action:
            routine_actions.add(candidate.routine_action)
        if len(suggestions) >= MAX_SUGGESTIONS:
            break

    if (
        len(suggestions) < MAX_SUGGESTIONS
        and _allow_health_suggestions(
            not_found=not_found,
            source_count=len(sources),
            overall_confidence=overall_confidence,
        )
    ):
        health_candidates = _health_suggestion_candidates(db=db, project=project)
        health_candidates.sort(
            key=lambda item: (item[0], 0 if item[1].routine_action else 1)
        )
        for _, candidate in health_candidates:
            if len(suggestions) >= MAX_SUGGESTIONS:
                break
            if candidate.routine_action and candidate.routine_action in routine_actions:
                continue
            if not override_cooldown and db.is_suggestion_type_in_cooldown(
                project=project_key,
                suggestion_type=candidate.suggestion_type,
                cooldown_days=cooldown_days,
            ):
                continue

            suggestion_id = _fingerprint(candidate.suggestion_type, candidate.text)
            if suggestion_id in seen:
                continue
            seen.add(suggestion_id)
            suggestions.append(
                CoachSuggestion(
                    id=suggestion_id,
                    type=candidate.suggestion_type,
                    text=candidate.text,
                    why=candidate.why,
                    hypothesis=candidate.hypothesis,
                    routine_action=candidate.routine_action,
                    action=candidate.action,
                    target=candidate.target,
                    citations=candidate.citations,
                )
            )
            if candidate.routine_action:
                routine_actions.add(candidate.routine_action)

    return suggestions
