# AI PM Portfolio: Multi-Agent Products

Two working multi-agent products, each with an AI PRD, agent architecture, eval suite with release gates, guardrails, monitoring, and a launch plan.

| | [Support Desk](support-desk/) | [Job Application Copilot](job-copilot/) |
|---|---|---|
| **Problem** | Routine support tickets wait hours for a human to click a button | Tailoring a resume takes an hour; AI tools invent experience |
| **Agents** | Triage · Knowledge · Resolver · Policy Guard · QA Critic · Executor | Analyzer · Tailor · Critic · Reviewer · Coach · Cover Letter |
| **Takes real actions?** | Yes: refunds, cancellations, password resets | No: drafts only |
| **Browser demo** | [`support-desk/demo/index.html`](support-desk/demo/index.html) | [`job-copilot/demo/index.html`](job-copilot/demo/index.html) (with live evals) |
| **Hardest risk** | Moving money wrongly | Fabricated experience |
| **Key design call** | LLMs propose, code decides; > $100 goes to a human | Critic is code and blocks inflated claims; an AI reviewer only advises |
| **Evals (offline)** | 19 cases, all gates pass | 13 cases, all gates pass |
| **Unit tests** | 16 | 23 |
| **Case study** | [CASE_STUDY.md](support-desk/CASE_STUDY.md) | [CASE_STUDY.md](job-copilot/CASE_STUDY.md) |

## The shared idea
Both products follow the same pattern, which is the point of the portfolio:

1. **Split work by risk, not by convenience.** Generation is done by LLM agents; anything that must be true (policy, facts, amounts) is checked by deterministic code.
2. **Fail closed.** When the system can't verify its own output, a human gets it, and the customer never sees the unverified version.
3. **Bounded autonomy.** Every retry and revision loop has a hard cap.
4. **Evals are release gates, not a report.** Safety metrics must be exactly zero to ship.
5. **Observable by default.** Every agent step is traced; every action is audited.

## Try them
Download the repo and open either `demo/index.html` in a browser: no install, no API key.

## Run everything (no API key needed)
```bash
pip install pytest
cd support-desk && python -m pytest -q && PYTHONPATH=src python evals/run_evals.py && cd ..
cd job-copilot  && python -m pytest -q && PYTHONPATH=src python evals/run_evals.py && cd ..
```
Add `--live` (with `ANTHROPIC_API_KEY`) to run against real Claude.

## Honest limitations
Offline evals use a deterministic mock model with fault injection. They prove the orchestration and safety net work, **not** live-model quality. Live eval results are the next milestone; see each project's `docs/LAUNCH_PLAN.md` for the gates.
