"""Typed contracts passed between agents."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

INTENTS = ["refund", "cancel_order", "order_status", "password_reset",
           "product_question", "complaint", "other"]
ORDER_INTENTS = {"refund", "cancel_order", "order_status"}


@dataclass
class Ticket:
    id: str
    customer_id: str
    subject: str
    body: str


@dataclass
class Triage:
    intent: str
    order_id: str | None
    sentiment: str
    confidence: float
    escalate: bool = False
    escalate_reason: str | None = None


@dataclass
class Plan:
    reply: str
    action: dict | None          # {"type": ..., "params": {...}} or None
    cited_articles: list[str]


@dataclass
class PolicyDecision:
    allowed: bool
    requires_approval: bool = False
    reasons: list[dict] = field(default_factory=list)   # [{"code": ..., "message": ...}]


@dataclass
class QAReport:
    approved: bool
    issues: list[str] = field(default_factory=list)


@dataclass
class Resolution:
    ticket_id: str
    status: str   # resolved | pending_approval | awaiting_customer | escalated | blocked
    customer_reply: str = ""
    action_executed: dict | None = None
    pending_action: dict | None = None
    triage: Triage | None = None
    kb_used: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    handoff: dict | None = None   # internal summary for the human agent on escalation
    trace_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
