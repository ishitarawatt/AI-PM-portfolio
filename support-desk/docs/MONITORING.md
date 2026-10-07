# Monitoring Plan

## Emitted today
- **Traces** (`logs/traces.jsonl`): one span per step (`input_guardrails`, `triage`, `knowledge`, `resolver`, `policy_guard`, `qa_critic`, `executor`) with `trace_id, status, retries, in/out tokens, latency_ms, cost_usd`. No ticket text.
- **Audit log** (`logs/audit.jsonl`): every executed or refused action and every approval request, with idempotency key and result.
- **Batch dashboard** (`cli batch`): status mix, auto-resolution rate, actions executed, $ refunded, approvals pending, escalations by reason, policy denials, QA rejections, injection attempts, p50/p95 latency, cost.

## Alerts for launch
| Signal | Threshold | Likely cause |
|---|---|---|
| Executor `invariant_violation` | **any** | Policy bug; page on-call |
| $ refunded per hour | > 2× trailing week | Abuse or policy regression |
| QA rejection rate | > 10% of drafts | Prompt/model regression |
| Policy denial rate | sudden 2× change | Model proposing bad actions, or policy change |
| Escalation rate | < 20% or > 50% | Over-automation or a broken triage |
| `ownership_mismatch` | spike | Account-takeover / social-engineering attempts |
| Injection flags | spike | Active probing |
| p95 ticket latency | > 20 s live | Provider latency or retries |
| LLM retries per ticket | > 0.3 | Output-format drift |

## Quality loop
1. Weekly `evals/run_evals.py --live` on a frozen set; deploys blocked on any gate failure.
2. Sample 25 auto-resolved and 25 denial replies per week for human review (tone, correctness).
3. Track reopen rate and CSAT for auto-resolved tickets vs. human-resolved.
4. Every escalation reviewed by a human becomes a candidate eval case.
5. Re-run evals on any model, prompt, policy, or help-center change.
