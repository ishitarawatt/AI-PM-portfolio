# Case Study: Job Application Copilot

**Tailored to the job. Truthful to you.**
A multi-agent product that rewrites a resume for a specific job posting, writes a cover letter and preps the interview, without inventing experience.

## The problem
Tailoring a resume for each application takes 30-60 minutes, so most people don't do it. The obvious shortcut, pasting everything into a chatbot, has a worse failure: language models embellish. "Supported a launch" quietly becomes "Led a launch", a team of 4 becomes 15. The candidate may not notice, but an interviewer will, and one invented claim can end a candidacy.

So the product question wasn't "can AI rewrite a resume?" It was **"can AI rewrite a resume in a way the candidate can trust without re-checking every line?"**

## What I built
```
Guardrails → Analyzer → Tailor ⇄ Critic → Reviewer → Coach → (Cover Letter ⇄ Letter checker)
```
| Agent | Kind | Job |
|---|---|---|
| Analyzer | AI | Reads the posting: required skills, seniority, responsibilities |
| Tailor | AI | Reorders and lightly rephrases the candidate's own bullets for this role |
| **Critic** | **Code** | Blocks any bullet it can't trace to the resume, any new number, any stronger claim |
| Reviewer | AI, advisory | Flags subtler exaggeration for the candidate to double-check |
| Coach | AI | Interview questions on real strengths, honest talking points on gaps |
| Cover Letter | AI, optional | Written only from Critic-approved bullets, then checked by code |

## Four decisions that shaped it
**1. The verifier is code, not a model.** Asking a model to catch its own class of mistake is weak evidence. The Critic is deterministic: every tailored bullet must match one original bullet (80%+ word overlap), add no numbers, and claim no more ownership than the source (*supported < built < led*). It's auditable, free to run, and can't be talked out of a decision.

**2. Fail closed.** If the Tailor can't produce a draft the Critic approves after one retry with feedback, the user gets *no* resume and a clear reason, never an unverified one. Same for the cover letter: it's withheld, while the verified resume still comes back.

**3. Rules gate, AI advises.** Some exaggeration can't be caught by rules ("vague made to sound specific"). I added an AI Reviewer, but it only flags; it can't block. A check that can raise false alarms shouldn't gate a user until its precision is measured. That measurement is on the roadmap, not assumed.

**4. Honest gaps are a feature.** The product shows which required skills the resume *doesn't* evidence and coaches how to talk about them, instead of papering over them.

## What broke, and what I changed
Each of these was found by a test or a check, not by luck:
- **The overlap rule had a hole.** "Supported the migration of 40 customers" → "Led the migration of 40 customers" changes one word in ten, so it passed at 90% overlap. Fix: ownership-verb tiers in the Critic, plus blocked scope words like "entire" and "single-handedly".
- **The fix misread nouns as verbs.** In "Supported *the launch*", the rule treated "launch" as the claim. Fix: read the bullet's opening verb, plus any verb the rewrite adds ("Supported *and led*…").
- **The letter checker was fooled by shared words.** "I led the launch of a billing portal" matched a *different* bullet that started with "Owned" via generic words like "customers". Fix: compare each sentence with the single bullet it most resembles.

Each fix shipped with a regression test.

## How it's measured
Evals are release gates, not a report: any safety metric above zero fails the build.

| Metric | Gate | Offline (stand-in model) | Live (real Claude) |
|---|---|---|---|
| Eval cases passing | 100% | 13 / 13 | 8 / 8 |
| Fabrication shown in resumes | 0 | 0 | 0 |
| Fabrication shown in cover letters | 0 | 0 | 0 |
| Personal data leaked to output | 0 | 0 | 0 |
| Critic rejected the model's own faithful draft | (watch) | n/a | 0 of 4 |

The offline suite (plus 23 unit tests) uses a deterministic stand-in model with deliberate faults to prove the safety net catches them. The live run used real Claude for every AI agent, injected the same faults on top of its real output, and all were caught; the Critic also never rejected a faithful Claude draft, so no false alarms. **It's one run of 8 cases** through the browser version of the pipeline, so it's a first signal, not a benchmark ([raw results](evals/results/live-claude-2026-10-07.json)).

## What I'd do next
1. Grow the live eval set to 100+ real resume/posting pairs and run it on every prompt or model change; the first live run (8/8, 0 false rejections) is too small to generalise.
2. Label 100 tailored-vs-original bullet pairs to measure the Reviewer's precision before letting it block anything.
3. Phased launch from [`docs/LAUNCH_PLAN.md`](docs/LAUNCH_PLAN.md): dogfood, then a 100-user beta, with "zero fabrications reached a user" as the go/no-go gate.

## What I learned
The interesting work wasn't the prompts. It was deciding **where the model is allowed to be creative and where it must be checked**, and building the checks so they fail loudly. Every bug above was a gap between "looks right" and "provably right", and evals with fault injection were what made those gaps visible.

---
**[Try the live demo](https://ishitarawatt.github.io/AI-PM-portfolio/job-copilot/demo/)** · Code, tests and evals: this folder · Full PRD: [`docs/PRD.md`](docs/PRD.md)
