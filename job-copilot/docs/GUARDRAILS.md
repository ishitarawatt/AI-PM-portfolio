# Guardrails

All guardrails live in `src/copilot/guardrails.py` and are **deterministic code**.

| # | Risk | Control | Where | Test |
|---|---|---|---|---|
| G1 | Fabricated experience | Every output bullet must match a source bullet (≥80% token overlap) and introduce **no new numbers**; claimed skills must appear in the source | Critic | `test_fabrication_detects_*`, eval `fabrication_*` |
| G1b | Inflated claims that keep the wording ("supported" → "led", added "entire") | Ownership-verb tiers (support < hands-on < lead) read from the opening verb plus any added verb; added scope words blocked | Critic | `test_verb_inflation_*`, `test_claim_reads_opening_verb_*`, eval `verb_inflation_*` |
| G1c | Subtler exaggeration (implied outcomes, vaguer → specific) | AI reviewer compares each bullet with its original; **advisory only**, shown as "double-check" notes; failure tolerated | Reviewer | `test_reviewer_*` |
| G2 | Prompt injection in JD | Lines matching injection patterns are dropped; run continues on the remainder; flag `prompt_injection_removed` | Input | `test_injection_line_removed_*`, eval `prompt_injection_in_jd` |
| G3 | PII exposure | Emails/phones redacted from the resume before any model call; evals assert none appear in output | Input | `test_resume_pii_not_in_output`, eval `pii_leak_rate` |
| G4 | Garbage in | JD < 40 chars or resume with no bullets → `blocked` with reason | Input | eval `*_blocked` |
| G5 | Oversized input / cost abuse | JD truncated at 12,000 chars; flag `jd_truncated` | Input | unit |
| G6 | Malformed model output | Parsed into typed dataclasses; 2 retries then escalate | Agents | `test_malformed_output_*` |
| G7 | Unverifiable result | Fail closed: resume withheld, status `needs_human` | Orchestrator | `test_persistent_fabrication_*` |
| G8 | Runaway loops/cost | Hard retry and critic-loop caps | Orchestrator | constants + tests |

## Known gaps (be honest about these)
- **Pattern-based injection detection is evadable** (paraphrase, other languages). Defense in depth is the point: the Analyzer's prompt marks JD text as data, and the critic validates outputs regardless of what the model was told.
- **Claim-strength rules are a word list.** They block the common inflations (ownership verbs, scope words) but not every phrasing. The AI reviewer covers some of the rest, advisory only because model judges raise false alarms. Measure its precision against human labels before letting it block anything.
- **Regex PII redaction** misses names and addresses. Use a dedicated PII service before handling real user data at scale.
- The resume header (name) is not sent to the model by design, but free-text sections could contain other identifiers.
