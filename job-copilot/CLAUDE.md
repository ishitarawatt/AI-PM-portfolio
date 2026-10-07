# Job Application Copilot: context for Claude

Multi-agent Python app that tailors a resume to a job posting **without inventing experience**.
Part of the AI-PM-portfolio repo. Work only inside `job-copilot/` unless asked otherwise.

## Architecture
Guardrails → Analyzer (LLM) → Tailor (LLM) ⇄ Critic (code) → Reviewer (LLM, advisory) → Coach (LLM)
- `src/copilot/guardrails.py`: PII redaction, prompt-injection stripping, fabrication + claim-strength checks (verb tiers, scope words)
- `src/copilot/agents.py`: agent prompts + typed parsing; the Critic is deterministic code by design
- `src/copilot/orchestrator.py`: retries (2), critic loop (1), fail closed (`needs_human`, resume withheld)
- `src/copilot/llm.py`: `AnthropicClient` (live) and `MockClient` (offline, fault injection)
- `src/copilot/monitoring.py`: JSONL tracing
- `evals/`: cases + harness with release gates (pass rate 1.0, fabrication 0, PII leak 0)
- `demo/index.html`: browser demo (JS port of the pipeline; live mode calls Claude). Keep its Critic logic in sync with `guardrails.py`.
- `docs/`: PRD, architecture, guardrails, monitoring, launch plan

## Rules
- Before and after any change: `python -m pytest -q` and `PYTHONPATH=src python evals/run_evals.py` must pass.
- Never weaken the Critic or the fail-closed behavior to make a test pass.
- Every new failure mode gets an eval case in `evals/cases.json`.
- Update the matching doc in `docs/` when behavior changes.

## Next up
1. Run `evals/run_evals.py --live` with a real API key and record results in README.
2. Measure the Reviewer's precision on labeled pairs before considering letting it block.
3. Cover-letter agent that reuses the same Critic.
4. One-page case study.
