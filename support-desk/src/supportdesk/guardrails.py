"""Input guardrails (before any model sees the ticket) and the QA Critic (before any reply is sent).

Both are deterministic code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .schemas import Plan, QAReport

MAX_BODY_CHARS = 5_000

CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
ORDER_RE = re.compile(r"\bORD-\d{4}\b", re.IGNORECASE)
INJECTION_RE = re.compile("|".join([
    r"ignore (all |any )?(the |your )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (all |any )?(the |your )?(previous|prior|above|rules|policy)",
    r"\byou are now\b",
    r"\bnew instructions\b",
    r"system prompt",
    r"developer mode",
    r"override (the |your )?(policy|rules|limits?)",
    r"act as (an? )?(admin|administrator|supervisor|manager)",
    r"^\s*(system|assistant|developer)\s*:",
]), re.IGNORECASE)


@dataclass
class InputCheck:
    ok: bool
    subject: str
    body: str
    flags: list[str]


def check_ticket(subject: str, body: str) -> InputCheck:
    flags: list[str] = []
    body = (body or "").strip()
    subject = (subject or "").strip()[:200]
    if not body:
        return InputCheck(False, subject, body, ["empty_ticket"])
    if len(body) > MAX_BODY_CHARS:
        body, flags = body[:MAX_BODY_CHARS], flags + ["body_truncated"]

    kept = []
    for line in body.splitlines():
        if INJECTION_RE.search(line):
            flags.append("prompt_injection_removed")
            continue
        kept.append(line)
    body = "\n".join(kept).strip()
    if INJECTION_RE.search(subject):
        subject, flags = "", flags + ["prompt_injection_removed"]

    if CARD_RE.search(body) or CARD_RE.search(subject):
        flags.append("card_number_redacted")
    body, subject = CARD_RE.sub("[CARD]", body), CARD_RE.sub("[CARD]", subject)
    body, subject = EMAIL_RE.sub("[EMAIL]", body), EMAIL_RE.sub("[EMAIL]", subject)

    if not body:
        return InputCheck(False, subject, body, sorted(set(flags + ["empty_after_sanitization"])))
    return InputCheck(True, subject, body, sorted(set(flags)))


# ----------------------------------------------------------------------------- QA Critic
REFUND_CLAIM = re.compile(
    r"\b(?:i|we)(?:'ve| have)?\s+(?:just\s+|also\s+)?(?:issued|processed|sent)\s+(?:you\s+)?(?:a|your|the)?\s*(?:full\s+)?refund"
    r"|\b(?:i|we)(?:'ve| have)?\s+(?:just\s+|also\s+)?refunded")
CANCEL_CLAIM = re.compile(r"\b(?:i|we)(?:'ve| have)?\s+(?:just\s+)?cancell?ed")
RESET_CLAIM = re.compile(r"\b(?:i|we)(?:'ve| have)?\s+(?:just\s+)?sent\b[^.]{0,40}\breset")
MONEY_RE = re.compile(r"\$\s?(\d+(?:,\d{3})*(?:\.\d{1,2})?)")
MAX_REPLY_CHARS = 1_500


def claim_issues(reply: str, action: dict | None) -> list[str]:
    """Does the reply claim something happened that the action does not do?"""
    low = reply.lower()
    kind = action["type"] if action else None
    issues = []
    if REFUND_CLAIM.search(low) and kind != "refund":
        issues.append("Reply claims a refund was issued, but no refund action is approved.")
    if CANCEL_CLAIM.search(low) and kind != "cancel_order":
        issues.append("Reply claims an order was cancelled, but no cancel action is approved.")
    if RESET_CLAIM.search(low) and kind != "password_reset":
        issues.append("Reply claims a reset link was sent, but no reset action is approved.")
    return issues


def review(plan: Plan, intent: str, customer_id: str, kb_ids: list[str], store) -> QAReport:
    issues = claim_issues(plan.reply, plan.action)
    reply = plan.reply.strip()
    kind = plan.action["type"] if plan.action else None

    if not reply:
        issues.append("Reply is empty.")
    if len(reply) > MAX_REPLY_CHARS:
        issues.append("Reply is too long.")
    if kind == "refund":
        amount = float(plan.action["params"]["amount"])
        stated = {float(m.replace(",", "")) for m in MONEY_RE.findall(reply)}
        if "refund" not in reply.lower():
            issues.append("A refund will be issued but the reply doesn't tell the customer.")
        elif abs(amount) > 0 and not any(abs(s - amount) < 0.005 for s in stated):
            issues.append(f"Reply does not state the actual refund amount ({amount:.2f}).")
    for oid in ORDER_RE.findall(reply):
        order = store.orders.get(oid.upper())
        if not order or order["customer_id"] != customer_id:
            issues.append(f"Reply mentions an order that isn't this customer's: {oid}")
    if CARD_RE.search(reply) or EMAIL_RE.search(reply):
        issues.append("Reply contains a card number or email address.")
    unknown = [c for c in plan.cited_articles if c not in kb_ids]
    if unknown:
        issues.append(f"Reply cites articles that were not retrieved: {unknown}")
    if intent == "product_question" and not set(plan.cited_articles) & set(kb_ids):
        issues.append("Product answer is not grounded in any help-center article.")
    return QAReport(approved=not issues, issues=issues)
