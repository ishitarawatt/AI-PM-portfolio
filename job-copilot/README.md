# Job Application Copilot

A multi-agent product that tailors your resume to a job posting **without inventing experience**, reports your honest skill gaps, and prepares you for the interview.

Five agents: **Analyzer → Tailor ⇄ Critic → Reviewer → Coach**, plus an optional **Cover Letter** writer with its own checker, wrapped in deterministic guardrails, full tracing, and an eval suite with CI-style gates.

The Critic (plain code) blocks any bullet that can't be traced to your resume, adds a number, or claims more than the original, such as upgrading "supported" to "led". An AI Reviewer then flags subtler exaggeration for you to double-check, without blocking.

**Short read:** [CASE_STUDY.md](CASE_STUDY.md): the problem, key decisions, what broke and how it was fixed.

## Try it in the browser
**[Open the live demo](https://ishitarawatt.github.io/AI-PM-portfolio/job-copilot/demo/)**, or open [`demo/index.html`](demo/index.html) in any browser. It runs the full pipeline in the page, shows which original bullet each tailored bullet came from, and lets you slip a problem into the first draft (a made-up bullet, "supported" inflated to "led", or an exaggerated cover letter) so you can watch the checks reject it. An **Evals** panel runs 8 cases against the same safety gates; opened inside Claude, it can run them on real Claude with your own account, no API key needed, and copy the results. When opened inside Claude, a live mode lets real Claude play the Analyzer, Tailor and Coach.

## Live results on real Claude
First live run, 7 Oct 2026, from the demo's Evals panel: real Claude played the Analyzer, Tailor, Reviewer, Coach and cover-letter writer; the Critic and letter checker are the same code as everywhere else. Raw output: [`evals/results/live-claude-2026-10-07.json`](evals/results/live-claude-2026-10-07.json).

| Gate | Result |
|---|---|
| Cases passing | **8 / 8** |
| Made-up content shown to the user | **0** |
| Overclaiming cover letters shown | **0** |
| Personal data leaked | **0** |
| Critic rejected Claude's own first draft (no faults injected) | **0 of 4** |
| Average time per case (excluding the blocked one) | ~12 s |

What this does and doesn't show: injected faults (a made-up bullet, "supported" → "led", an exaggerated letter) were all caught on top of real model output, and the Critic never rejected a faithful Claude draft, so no false alarms in this run. It is one run of 8 cases through the browser version of the pipeline; the Python `--live` suite and a larger labeled set are still to do.

## Quick start (no API key needed)
```bash
pip install -r requirements.txt          # pytest (+ anthropic for live mode)
PYTHONPATH=src python -m copilot.cli --resume examples/resume.txt --job examples/job.txt
PYTHONPATH=src python -m copilot.cli --resume examples/resume.txt --job examples/job.txt --cover-letter   # also write a checked cover letter
```

The cover letter is built only from bullets the Critic approved. A checker then confirms every number comes from your resume, "led"/"owned" only appear where your matching bullet says so, there are no boosters like "single-handedly", and skill gaps are never claimed as experience. If it still fails after one rewrite it is withheld, and your verified resume is still returned.

## Live mode (real Claude)
```bash
export ANTHROPIC_API_KEY=...             # optional: COPILOT_MODEL=claude-sonnet-5-5
PYTHONPATH=src python -m copilot.cli --resume examples/resume.txt --job examples/job.txt --live
```

## Verify
```bash
python -m pytest -q                          # 23 unit tests
PYTHONPATH=src python evals/run_evals.py     # 13 eval cases + safety gates (non-zero exit on failure)
```

> The offline runs use a deterministic **mock model** so the harness, guardrails and failure paths are testable and free. Live-model results are above; run `evals/run_evals.py --live` for the full Python suite.

## Layout
```
CASE_STUDY.md          one-page case study
docs/PRD.md            AI PRD: problem, users, metrics, risks
docs/ARCHITECTURE.md   agent design + flow diagram
docs/GUARDRAILS.md     risk → control → test table, known gaps
docs/MONITORING.md     telemetry, alerts, quality monitoring
docs/LAUNCH_PLAN.md    gates, phased rollout, kill switch
src/copilot/           agents, orchestrator, guardrails, tracing, LLM clients, CLI
evals/                 cases.json + run_evals.py (pass rate, fabrication rate, PII leak rate)
tests/                 unit tests
examples/              sample resume and job description
demo/index.html        browser demo (example engine + live Claude mode)
CLAUDE.md              context for Claude in new chats
```

## Statuses
`ok` result is verified · `needs_human` system could not verify, unverified resume withheld · `blocked` input unusable (reason in flags). CLI exit code: 0 / 2 / 2.
