"""LLM clients: real Anthropic client and a deterministic offline mock with fault injection."""
from __future__ import annotations

import json
import os
import re
from typing import Protocol

ORDER_RE = re.compile(r"\bORD-\d{4}\b", re.IGNORECASE)


class LLMClient(Protocol):
    def complete(self, role: str, system: str, user: str) -> str: ...


def extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in model output")
    return json.loads(match.group(0))


class AnthropicClient:
    def __init__(self, model: str | None = None, max_tokens: int = 1200):
        import anthropic  # lazy: offline mode needs no SDK

        self._client = anthropic.Anthropic()
        self.model = model or os.getenv("SUPPORTDESK_MODEL", "claude-sonnet-5-5")
        self.max_tokens = max_tokens

    def complete(self, role: str, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=system,
            messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


# ---------------------------------------------------------------------------- offline mock
ANGRY = ("furious", "terrible", "worst", "angry", "unacceptable", "ridiculous")
ESCALATE_WORDS = ("lawyer", "legal action", "sue", "chargeback", "attorney")
INTENT_RULES = [
    ("password_reset", ("password", "log in", "login", "locked out", "sign in")),
    ("cancel_order", ("cancel", "cancellation")),
    ("refund", ("refund", "money back", "broken", "damaged", "defective", "faulty")),
    ("order_status", ("where is", "where's", "tracking", "status", "not arrived", "hasn't arrived", "late")),
    ("product_question", ("warranty", "return policy", "do you ship", "how long", "international")),
]


def _has(low: str, words) -> bool:
    return any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low) for w in words)


class MockClient:
    """Keyword-rule stand-in for an LLM so the system runs and is testable with no API key.

    Fault injection for testing the safety net:
      overpromise_first_n  resolver falsely claims a refund on its first N calls
      rogue_first_n        resolver proposes a $999 refund on its first N refund calls
    """

    def __init__(self, overpromise_first_n: int = 0, rogue_first_n: int = 0):
        self.overpromise_first_n = overpromise_first_n
        self.rogue_first_n = rogue_first_n
        self.resolver_calls = 0

    def complete(self, role: str, system: str, user: str) -> str:
        handler = getattr(self, f"_{role}", None)
        if handler is None:
            raise ValueError(f"mock has no role {role!r}")
        return json.dumps(handler(json.loads(user)))

    def _triage(self, p: dict) -> dict:
        t = p["ticket"]
        text = f"{t['subject']}\n{t['body']}"
        low = text.lower()
        m = ORDER_RE.search(text)
        order_id = m.group(0).upper() if m else None
        sentiment = "angry" if _has(low, ANGRY) or "!!!" in text else "calm"
        if _has(low, ESCALATE_WORDS):
            return {"intent": "complaint", "order_id": order_id, "sentiment": "angry",
                    "confidence": 0.95, "escalate": True, "escalate_reason": "legal_or_chargeback_threat"}
        for intent, words in INTENT_RULES:
            if _has(low, words):
                return {"intent": intent, "order_id": order_id, "sentiment": sentiment,
                        "confidence": 0.9, "escalate": False, "escalate_reason": None}
        return {"intent": "other", "order_id": order_id, "sentiment": sentiment,
                "confidence": 0.3, "escalate": False, "escalate_reason": None}

    @staticmethod
    def _denial(name: str, oid: str, reasons: list[dict], kb: list[dict], n_articles: int = 1) -> str:
        why = " and ".join(r["message"] for r in reasons)
        guidance = " ".join(a["text"] for a in kb[:n_articles])
        return f"Hi {name}, I looked into order {oid}. I'm not able to do that because {why}. {guidance}"

    def _resolver(self, p: dict) -> dict:
        self.resolver_calls += 1
        tri, order, kb, name = p["triage"], p.get("order"), p.get("kb", []), p["customer_name"]
        reasons = p.get("policy_feedback") or []
        codes = {r["code"] for r in reasons}
        kb_ids = [a["id"] for a in kb]
        oid = order["id"] if order else None
        intent, action, cited = tri["intent"], None, kb_ids[:1]

        if intent == "refund" and order:
            if reasons and "amount_exceeds_refundable" not in codes:
                reply = self._denial(name, oid, reasons, kb)
            else:
                amount = round(order["total"] - order["refunded"], 2)
                if self.resolver_calls <= self.rogue_first_n:
                    amount = 999.0
                action = {"type": "refund", "params": {"order_id": oid, "amount": amount}}
                reply = (f"Hi {name}, I'm sorry about the trouble with order {oid}. I've issued a refund of "
                         f"${amount:.2f} to your original payment method. It should appear within 5-7 business days.")
        elif intent == "cancel_order" and order:
            if reasons:  # cancel denied: explain, and point to the returns article too
                reply, cited = self._denial(name, oid, reasons, kb, n_articles=2), kb_ids[:2]
            else:
                action = {"type": "cancel_order", "params": {"order_id": oid}}
                reply = f"Hi {name}, I've cancelled order {oid}. You won't be charged for it."
        elif intent == "password_reset":
            action = {"type": "password_reset", "params": {"customer_id": p["customer_id"]}}
            reply = (f"Hi {name}, I've sent a password reset link to the email address on your account. "
                     "The link expires after 1 hour.")
        elif intent == "order_status" and order:
            detail = {
                "delivered": f"was delivered on {order.get('delivered_on')}",
                "shipped": "has shipped and is on its way. Standard shipping takes 3-5 business days, "
                           "and the tracking link is in your shipping email",
                "processing": "is being prepared and will ship soon",
                "cancelled": "was cancelled",
            }.get(order["status"], f"is {order['status']}")
            reply = f"Hi {name}, order {oid} {detail}."
        elif intent == "product_question" and kb:
            reply = f"Hi {name}, here's what our help center says: {kb[0]['text']}"
        else:
            reply, cited = f"Hi {name}, thanks for getting in touch. Could you tell me a bit more?", []

        if self.resolver_calls <= self.overpromise_first_n:
            reply += " I've also issued a full refund for your trouble."
        return {"reply": reply, "action": action, "cited_articles": cited}
