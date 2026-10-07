"""Orchestrator.

input guardrails -> Triage -> routing checks -> Knowledge -> Resolver
   -> Policy Guard -> QA Critic (revise loop, bounded) -> execute | queue for approval | escalate
"""
from __future__ import annotations

import json

from .agents import KnowledgeAgent, ResolverAgent, TriageAgent
from .guardrails import check_ticket, review
from .llm import LLMClient
from .monitoring import Tracer, approx_tokens
from .policy import TODAY, evaluate
from .schemas import ORDER_INTENTS, Resolution, Ticket
from .tools import Store

MAX_LLM_RETRIES = 2     # malformed-output retries per LLM call
MAX_REVISIONS = 2       # resolver re-drafts after a policy or QA rejection
MIN_CONFIDENCE = 0.6

ESCALATION_REPLY = ("Hi {name}, thanks for reaching out. I've passed your message to a specialist on "
                    "our team, who will get back to you within 24 hours.")
APPROVAL_REPLY = ("Hi {name}, thanks for the details on order {oid}. Because of the amount, your refund "
                  "needs a quick review by our team. You'll hear back within 24 hours.")
ASK_ORDER_REPLY = ("Hi {name}, happy to help. Could you share your order number? It starts with ORD- "
                   "and is in your confirmation email.")
NOT_FOUND_REPLY = ("Hi {name}, I couldn't find order {oid} on your account. Could you double-check the "
                   "number in your confirmation email?")


class AgentFailure(RuntimeError):
    pass


class Orchestrator:
    def __init__(self, llm: LLMClient, store: Store, tracer: Tracer | None = None, today=TODAY):
        self.store, self.today = store, today
        self.tracer = tracer or Tracer()
        self.triage = TriageAgent(llm)
        self.knowledge = KnowledgeAgent(store.kb)
        self.resolver = ResolverAgent(llm)

    # -- helpers -------------------------------------------------------------------------
    def _llm_call(self, trace_id: str, name: str, fn, input_text: str):
        last = None
        for attempt in range(MAX_LLM_RETRIES + 1):
            try:
                with self.tracer.span(trace_id, name, input_text, llm=True) as rec:
                    rec["retries"] = attempt
                    out = fn()
                    rec["out_tokens"] = approx_tokens(json.dumps(out.__dict__, default=str))
                    return out
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
                last = e
        raise AgentFailure(f"{name} failed after {MAX_LLM_RETRIES + 1} attempts: {last}")

    def _escalate(self, res: Resolution, ticket: Ticket, name: str, reason: str, draft: str | None = None):
        res.status = "escalated"
        res.customer_reply = ESCALATION_REPLY.format(name=name)
        res.handoff = {
            "reason": reason,
            "intent": res.triage.intent if res.triage else None,
            "order_id": res.triage.order_id if res.triage else None,
            "sentiment": res.triage.sentiment if res.triage else None,
            "ticket": {"subject": ticket.subject, "body": ticket.body},   # already sanitized
            "unverified_draft": draft,   # internal only, never sent to the customer
            "flags": list(res.flags),
        }
        return res

    # -- main ----------------------------------------------------------------------------
    def run(self, ticket: Ticket) -> Resolution:
        trace_id = self.tracer.new_trace_id()
        res = Resolution(ticket_id=ticket.id, status="resolved", trace_id=trace_id)

        customer = self.store.customers.get(ticket.customer_id)
        if not customer:
            res.status, res.flags = "blocked", ["unknown_customer"]
            return res
        name = customer["name"].split()[0]

        with self.tracer.span(trace_id, "input_guardrails"):
            chk = check_ticket(ticket.subject, ticket.body)
        res.flags += chk.flags
        if not chk.ok:
            res.status = "blocked"
            return res
        clean = Ticket(ticket.id, ticket.customer_id, chk.subject, chk.body)

        try:
            tri = self._llm_call(trace_id, "triage", lambda: self.triage.run(clean), clean.body)
            res.triage = tri
            if tri.escalate:
                return self._escalate(res, clean, name, tri.escalate_reason or "triage_requested")
            if tri.intent == "complaint":
                return self._escalate(res, clean, name, "complaint")
            if tri.confidence < MIN_CONFIDENCE:
                return self._escalate(res, clean, name, "low_confidence")

            order = None
            if tri.order_id:
                found = self.store.orders.get(tri.order_id)
                if found is None and tri.intent in ORDER_INTENTS:
                    res.status, res.flags = "awaiting_customer", res.flags + ["order_not_found"]
                    res.customer_reply = NOT_FOUND_REPLY.format(name=name, oid=tri.order_id)
                    return res
                if found is not None and found["customer_id"] != ticket.customer_id:
                    res.flags.append("ownership_mismatch")
                    return self._escalate(res, clean, name, "ownership_mismatch")
                order = found
            elif tri.intent in ORDER_INTENTS:
                res.status, res.flags = "awaiting_customer", res.flags + ["missing_order_id"]
                res.customer_reply = ASK_ORDER_REPLY.format(name=name)
                return res

            with self.tracer.span(trace_id, "knowledge"):
                kb = self.knowledge.run(clean, tri)
            res.kb_used = [a["id"] for a in kb]

            feedback: dict = {}
            plan = None
            for _ in range(MAX_REVISIONS + 1):
                plan = self._llm_call(
                    trace_id, "resolver",
                    lambda: self.resolver.run(clean, tri, order, kb, name, feedback), clean.body)

                with self.tracer.span(trace_id, "policy_guard"):
                    decision = evaluate(plan.action, ticket.customer_id, self.store, self.today)
                if not decision.allowed:
                    res.flags.append("policy_denied:" + ",".join(r["code"] for r in decision.reasons))
                    feedback = {"policy_feedback": decision.reasons}
                    continue

                if decision.requires_approval:
                    self.store.queue_approval(ticket.id, plan.action)
                    res.status, res.pending_action = "pending_approval", plan.action
                    res.customer_reply = APPROVAL_REPLY.format(
                        name=name, oid=plan.action["params"].get("order_id", "your order"))
                    return res

                with self.tracer.span(trace_id, "qa_critic"):
                    qa = review(plan, tri.intent, ticket.customer_id, res.kb_used, self.store)
                if not qa.approved:
                    res.flags.append("qa_rejected")
                    feedback = {"qa_feedback": qa.issues}
                    continue

                if plan.action:
                    key = f"{ticket.id}:{plan.action['type']}:" + str(
                        plan.action["params"].get("order_id") or plan.action["params"].get("customer_id"))
                    with self.tracer.span(trace_id, "executor"):
                        result = self.store.execute(plan.action, key, ticket.id)
                    if not result["ok"]:
                        res.flags.append("action_failed")
                        return self._escalate(res, clean, name, "action_failed", plan.reply)
                    if result.get("duplicate"):
                        res.flags.append("duplicate_action_suppressed")
                    res.action_executed = plan.action

                res.status, res.customer_reply = "resolved", plan.reply
                return res

            return self._escalate(res, clean, name, "revision_limit", plan.reply if plan else None)
        except AgentFailure as e:
            res.flags.append(f"agent_failure: {e}")
            return self._escalate(res, clean, name, "agent_failure")
