# Agent Architecture

```
ticket
  │
  ▼
[Input guardrails]  strip injection · redact card/email · size limits ──► blocked
  │
  ▼
[Triage agent · LLM]  intent · order_id · sentiment · confidence
  │  legal/chargeback · complaint · low confidence ──────────────────► ESCALATE
  │  order intent without order id / unknown order ─────────────────► AWAITING CUSTOMER
  │  order belongs to someone else ─────────────────────────────────► ESCALATE
  ▼
[Knowledge agent]  top help-center articles
  │
  ▼
┌──────────── revision loop (max 2 revisions) ────────────┐
│ [Resolver agent · LLM]  reply + proposed action          │
│        │                                                 │
│        ▼                                                 │
│ [Policy Guard · code]  denied ──► feedback to resolver ──┤
│        │ needs approval ─────────────────────────────────┼──► APPROVAL QUEUE (pending_approval)
│        ▼                                                 │
│ [QA Critic · code]     rejected ─► feedback to resolver ─┤
└────────┬─────────────────────────────────────────────────┘
         │ approved                       loop exhausted ──► ESCALATE (draft kept internal)
         ▼
[Executor · tool]  idempotent · re-checks invariants · audit log ──► RESOLVED
```

## Why these boundaries
| Decision | Reason |
|---|---|
| Resolver proposes, Policy Guard decides | Money movement must not depend on model judgment or on text a customer can write. |
| Policy Guard and QA are code | Deterministic, unit-testable, cannot be talked out of a decision. |
| Executor re-checks invariants | Defense in depth: even a policy bug can't over-refund or refund an undelivered order (a test found exactly this gap during build). |
| Idempotency keys | Retries and duplicate tickets can't double-refund. |
| Denials feed back to the Resolver | The customer still gets a helpful, policy-grounded answer instead of a dead end. |
| Templates for escalation, approval, and "ask for order number" | Safety-critical messages are fixed text, not generated. |
| Ownership checked before retrieval and drafting | Another customer's order details never enter the prompt. |
| One action per ticket | Keeps reasoning, policy checks, and audit simple in v1. |

## Statuses
`resolved` · `pending_approval` · `awaiting_customer` · `escalated` · `blocked`

## Swapping in production components
| Here | Production |
|---|---|
| `Store` JSON files | Order system / OMS API, identity provider |
| `approval_queue` list | Ticketing system task (Zendesk / Intercom) |
| `KnowledgeAgent` keyword scoring | Embedding search over the help center |
| `Tracer` JSONL | OpenTelemetry / Langfuse |
| `MockClient` | `AnthropicClient` (`--live`) |
