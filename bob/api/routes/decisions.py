"""Decisions endpoint for viewing decision history and chains."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from bob.extract.decisions import (
    StoredDecision,
    get_decision,
    get_decisions_superseded_by,
    get_supersession_chain,
)


class DecisionDetail(BaseModel):
    """API representation of a stored decision."""

    id: int
    chunk_id: int
    decision_text: str
    context: str | None
    decision_type: str | None
    status: str
    superseded_by: int | None
    decision_date: datetime | None
    confidence: float
    extracted_at: datetime
    source_path: str | None
    project: str | None


class DecisionHistoryResponse(BaseModel):
    """Response for GET /decisions/{id}/history."""

    decision: DecisionDetail
    predecessors: list[DecisionDetail] = Field(
        default_factory=list,
        description="Decisions that this decision superseded (oldest first)",
    )
    successors: list[DecisionDetail] = Field(
        default_factory=list,
        description="Decisions that supersede this decision (oldest first)",
    )


router = APIRouter()


def _to_detail(d: StoredDecision) -> DecisionDetail:
    """Convert a StoredDecision to API DecisionDetail."""
    return DecisionDetail(
        id=d.id,
        chunk_id=d.chunk_id,
        decision_text=d.decision_text,
        context=d.context,
        decision_type=d.decision_type,
        status=d.status,
        superseded_by=d.superseded_by,
        decision_date=d.decision_date,
        confidence=d.confidence,
        extracted_at=d.extracted_at,
        source_path=d.source_path,
        project=d.project,
    )


@router.get("/decisions/{decision_id}/history", response_model=DecisionHistoryResponse)
def get_decision_history(decision_id: int) -> DecisionHistoryResponse:
    """Get the supersession history for a decision.

    Returns the decision along with:
    - predecessors: earlier decisions that this decision superseded
    - successors: later decisions that supersede this decision

    Args:
        decision_id: ID of the decision.

    Returns:
        Decision with its supersession chain.

    Raises:
        HTTPException: 404 if decision not found.
    """
    decision = get_decision(decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    # Get the full chain starting from this decision
    chain = get_supersession_chain(decision_id)

    # Find predecessors: decisions that this decision superseded
    predecessors: list[StoredDecision] = []
    superseded = get_decisions_superseded_by(decision_id)
    for superseded_decision in superseded:
        # Recursively get the chain of what each superseded decision replaced
        sub_chain = get_supersession_chain(superseded_decision.id)
        for d in sub_chain:
            if d.id != decision_id and d.id not in {p.id for p in predecessors}:
                predecessors.append(d)

    # Get successors: decisions that supersede this one
    successors: list[StoredDecision] = []
    if len(chain) > 1:
        # chain[0] is the current decision, chain[1:] are successors
        for d in chain[1:]:
            if d.id != decision_id:
                successors.append(d)

    # Sort predecessors by date (oldest first)
    predecessors.sort(
        key=lambda d: d.decision_date or d.extracted_at,
    )

    # Successors are already in order from the chain

    return DecisionHistoryResponse(
        decision=_to_detail(decision),
        predecessors=[_to_detail(d) for d in predecessors],
        successors=[_to_detail(d) for d in successors],
    )
