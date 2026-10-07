# AI PRD: Support Desk, a multi-agent ticket resolver

**Status:** Draft v1 · **Owner:** (you) · **Date:** 2026-10-07

## 1. Problem
An online electronics store gets thousands of tickets a week. About 60% are routine (where's my order, refund a damaged item, cancel, password reset), but each one still waits hours in a queue for a human who looks up the order, checks policy, and clicks a button. Customers wait; agents burn out on repetitive work; complex cases sit behind easy ones.

Plain chatbots don't fix this. They can *talk* about refunds but can't safely *do* them, and when they guess at policy or claim "I've refunded you" without doing it, they create more tickets and real financial risk.

## 2. Users
| User | Need |
|---|---|
| **Customer** | A correct answer or a finished action in minutes, not hours |
| **Support agent** | Routine tickets handled; hard ones arrive with a clean summary |
| **Support lead / finance** | Spending stays within policy; every action is auditable |

## 3. Solution
A team of agents that resolves routine tickets end to end and hands everything else to a human with context:

| Agent | Kind | Job |
|---|---|---|
| Triage | LLM | Intent, order id, sentiment, confidence, escalation signals |
| Knowledge | Retrieval | Pulls the help-center articles that govern the answer |
| Resolver | LLM | Drafts the reply and *proposes* at most one action |
| Policy Guard | Code | Decides whether the action is allowed, needs approval, or is denied |
| QA Critic | Code | Blocks replies that over-promise, misstate amounts, leak data, or aren't grounded |
| Executor | Tool | Runs approved actions idempotently with an audit log |

**Core principle: LLMs propose, code disposes.** No model output can move money on its own.

## 4. Scope
**In v1:** refunds (≤ $100 auto, larger to an approval queue), cancellations of unshipped orders, order status, password reset links, help-center questions, escalation with handoff.
**Out of v1:** address changes, exchanges, multi-order tickets, multi-turn conversation memory, voice, languages other than English.

## 5. User stories and acceptance criteria
1. *Damaged item, small order* → refunded automatically. **AC:** amount equals the refundable balance; reply states the exact amount; action in the audit log.
2. *Refund over $100* → **AC:** nothing executes; request lands in the approval queue; customer told to expect a reply in 24 h.
3. *Request against policy* (shipped cancel, >30 days, already refunded) → **AC:** no action; kind explanation that cites the policy.
4. *Someone asks about another customer's order* → **AC:** escalated as `ownership_mismatch`; reply reveals nothing about the order.
5. *Legal threat / chargeback / vague ticket* → **AC:** escalated with reason and sanitized handoff.
6. *Ticket contains injected instructions* → **AC:** instructions stripped and flagged; policy limits unchanged.
7. *The model writes something untrue* → **AC:** QA rejects it; one bounded revision; otherwise escalate and the draft never reaches the customer.

## 6. Success metrics
| Metric | Target | Type |
|---|---|---|
| Wrong / unauthorized action rate | **0** (release gate) | Safety |
| False-promise rate in sent replies | **0** (release gate) | Safety |
| PII leak rate | **0** (release gate) | Safety |
| Escalation recall on must-escalate tickets | **100%** (release gate) | Safety |
| Auto-resolution rate | 50-65% of all tickets | Value |
| Median time to resolution (auto) | < 2 min vs ~6 h baseline | Value |
| Reopen rate on auto-resolved tickets | ≤ human baseline | Quality |
| CSAT on auto-resolved tickets | ≥ human baseline | Quality |
| Approval-queue turnaround | < 24 h | Ops |
| Cost per resolved ticket | < $0.05 model cost | Economics |

Auto-resolution is deliberately capped as a *target*, not maximized: pushing it higher usually means escalating less, which trades safety for a vanity number.

## 7. AI-specific requirements
- **Autonomy boundary:** agents may only call three allow-listed actions. Spend above $100 always needs a human.
- **Determinism where it matters:** policy, QA and execution are code with unit tests.
- **Fail closed:** any unresolved doubt → escalate with a safe holding reply.
- **Grounding:** product answers must cite a retrieved help article.
- **Privacy:** card numbers and emails redacted before any model call; traces store sizes, not text.
- **Observability:** every step traced; every action and approval audited.

## 8. Risks and open questions
- Offline evals use a deterministic mock model: they prove the harness and the safety net, **not** live model quality. Live evals are a launch gate.
- Keyword retrieval won't scale past a small help center; move to embeddings plus a retrieval eval.
- Regex-based injection and false-promise detection can be evaded by rephrasing. The design relies on defense in depth: even a fully manipulated resolver can only *propose* an action the Policy Guard will check.
- Customers may resent automated denials. Watch reopen rate and CSAT on denial replies specifically.
