# Support Desk

A multi-agent system that **resolves** routine customer support tickets end to end (refunds, cancellations, order status, password resets, help-center questions) and hands everything else to a human with a clean summary.

**Core principle: LLMs propose, code disposes.** The Resolver agent can only *suggest* an action. A deterministic Policy Guard decides, a QA Critic checks the reply, and an idempotent Executor acts and audits.

```
Triage (LLM) → Knowledge → Resolver (LLM) ⇄ Policy Guard + QA Critic → Executor | Approval queue | Human
```

**Short read:** [CASE_STUDY.md](CASE_STUDY.md): the problem, key decisions, what broke and what was designed against.

## Try it in the browser
**[Open the live demo](https://ishitarawatt.github.io/AI-PM-portfolio/support-desk/demo/)**, or open [`demo/index.html`](demo/index.html) in any browser. It processes the 11-ticket sample inbox, shows each ticket's journey through the agents, updates the order book as refunds and cancellations happen, and has an **approval queue** where you approve or reject refunds over $100, plus a full audit log. You can write your own tickets and slip in a rogue $999 refund or a false "I've refunded you" to watch the checks catch them. It's a JavaScript port of the same logic and matches the Python system ticket for ticket on the sample inbox. Opened inside Claude, a live mode lets real Claude play Triage and Resolver.

The demo also has an **Evals panel** (the 19 test cases and release gates, run in the browser on the example engine), reply-as-the-customer on tickets the AI asked for more information, inbox search and filters, CSV export of tickets and the audit log, reject reasons on approvals, and a refund-limit slider to watch the Policy Guard react. The Evals panel checks the guardrails, not live-model quality.

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
CASE_STUDY.md  one-page case study
demo/       browser demo (example + live engine)
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
