# Guardrails

| # | Risk | Control | Layer | Covered by |
|---|---|---|---|---|
| G1 | Unauthorized refund (wrong order, wrong customer) | Ownership check at routing and again in Policy Guard | Orchestrator + Policy | `someone_elses_order_escalates`, `test_policy_blocks_other_customers_order` |
| G2 | Over-refund | Amount ≤ refundable balance; executor re-checks | Policy + Executor | `rogue_refund_amount_blocked`, `test_executor_*` |
| G3 | Large spend without oversight | > $100 → approval queue, nothing executes | Policy | `large_refund_needs_approval` |
| G4 | Refund outside policy | 30-day window, delivered-only, no double refunds | Policy + Executor | `refund_outside_window_denied`, `already_refunded_denied` |
| G5 | Double execution | Idempotency key per ticket + action + target | Executor | `test_same_ticket_twice_never_double_refunds` |
| G6 | Action outside scope | Allow-list of 3 actions | Policy | `test_policy_rejects_unknown_action_*` |
| G7 | Prompt injection in ticket | Pattern-strip lines, flag; policy limits independent of text | Input + Policy | `prompt_injection_ignored` |
| G8 | False promises ("I've refunded you") | Claims must match the approved action; refund amount must be stated exactly | QA Critic | `false_promise_*`, `test_qa_catches_*` |
| G9 | Ungrounded policy answers | Product answers must cite a retrieved article; no unretrieved citations | QA Critic | `warranty_question_grounded`, `test_qa_requires_grounding_*` |
| G10 | Data leakage | Redact card/email on input; QA blocks other customers' order ids, cards, emails in replies | Input + QA | `card_number_redacted`, eval `pii_leak_rate` |
| G11 | Situations a bot shouldn't handle | Legal/chargeback, complaints, low confidence → human | Triage routing | `legal_threat_escalates`, `vague_ticket_escalates` |
| G12 | Unverifiable output | Bounded revisions, then escalate; draft kept internal | Orchestrator | `persistent_false_promise_escalates` |
| G13 | Malformed model output | Typed parsing, 2 retries, then escalate | Agents | `test_malformed_model_output_*` |

## Known limits (stated plainly)
- Regex injection and claim detection can be evaded by paraphrasing. Mitigation: the dangerous outcomes (moving money, leaking orders) are blocked by code that never reads the ticket's wording.
- Redaction covers cards and emails only. Add a PII service (names, addresses, phone numbers) before real traffic.
- QA checks facts the system can verify (actions, amounts, order ids, citations). It does not judge tone or helpfulness; that needs an LLM judge plus human sampling.
- The approval queue has no SLA enforcement or reviewer UI in v1.
