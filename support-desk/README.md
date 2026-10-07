# Support Desk

A multi-agent system that **resolves** routine customer support tickets end to end (refunds, cancellations, order status, password resets, help-center questions) and hands everything else to a human with a clean summary.

**Core principle: LLMs propose, code disposes.** The Resolver agent can only *suggest* an action. A deterministic Policy Guard decides, a QA Critic checks the reply, and an idempotent Executor acts and audits.

```
Triage (LLM) → Knowledge → Resolver (LLM) ⇄ Policy Guard + QA Critic → Executor | Approval queue | Human
```

## Quick start (no API key)
```bash
pip install -r requirements.txt
PYTHONPATH=src python -m supportdesk.cli batch data/inbox.json        # 11 tickets + dashboard
PYTHONPATH=src python -m supportdesk.cli ticket --customer C1 --body "Order ORD-1001 arrived broken"
```

## Live mode (real Claude)
```bash
export ANTHROPIC_API_KEY=...            # optional: SUPPORTDESK_MODEL=claude-sonnet-5-5
PYTHONPATH=src python -m supportdesk.cli --live batch data/inbox.json
PYTHONPATH=src python evals/run_evals.py --live
```

## Verify
```bash
python -m pytest -q                         # 16 unit tests
PYTHONPATH=src python evals/run_evals.py    # 19 eval tickets + release gates
```
Offline results (mock model): 19/19 pass · wrong-action rate 0 · false-promise rate 0 · PII leak 0 · escalation recall 100% · auto-resolution 63%.

> The offline model is a deterministic mock with fault injection (false promises, rogue refund amounts) so the safety net can be tested for free. It validates the **system**, not live-model quality. Run `--live` evals before relying on it.

## What it shows
- **Real actions under policy:** 30-day window, delivered-only, no double refunds, $100 auto-limit with approval queue
- **Defense in depth:** ownership checked twice; executor re-checks invariants; idempotency keys
- **Self-correction:** policy denials and QA rejections feed back to the Resolver (bounded), else escalate
- **Safe escalation:** fixed holding replies; unverified drafts stay internal
- **Observability:** per-step traces, audit log, batch dashboard

## Layout
```
docs/       PRD · ARCHITECTURE · GUARDRAILS · MONITORING · LAUNCH_PLAN
src/supportdesk/
  agents.py        Triage, Knowledge, Resolver
  policy.py        Policy Guard (refund window, limits, ownership, allow-list)
  guardrails.py    input sanitization + QA Critic
  tools.py         order store, idempotent executor, approval queue, audit log
  orchestrator.py  routing, revision loop, escalation
  monitoring.py    tracing + dashboard
  llm.py           Anthropic client + offline mock
  cli.py
data/       sample orders, customers, help center, inbox
evals/      19 cases + harness with release gates
tests/      unit tests
```
Sample data uses a fixed "today" of 2026-10-07 (`SUPPORTDESK_TODAY` to override) so results are reproducible.
