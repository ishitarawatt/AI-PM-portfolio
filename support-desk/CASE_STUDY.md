# Case Study: Support Desk

**AI proposes, code decides.**
A multi-agent system that resolves routine customer-support tickets end to end, including refunds, and hands everything else to a person with a clean summary.

## The problem
Most support tickets are routine: where's my order, refund a damaged item, cancel, reset a password. Each still waits hours for a person to look up the order, check the policy and click a button. Chatbots don't fix this. They can *talk* about refunds but can't safely *do* them, and when they guess at policy or say "I've refunded you" without doing it, they create new tickets and real financial risk.

The product question: **how much can AI resolve on its own, without ever being trusted with a decision that moves money?**

## What I built
```
Guardrails → Triage → Knowledge → Resolver ⇄ Policy Guard + QA Critic → Executor | Approval queue | Human
```
| Agent | Kind | Job |
|---|---|---|
| Triage | AI | Intent, order number, sentiment, confidence, escalation signals |
| Knowledge | Retrieval | Finds the help-center articles that govern the answer |
| Resolver | AI | Drafts the reply and *proposes* at most one action |
| **Policy Guard** | **Code** | Decides: allowed, needs a person, or denied |
| **QA Critic** | **Code** | Blocks replies that over-promise, misstate amounts, leak data or aren't grounded |
| **Executor** | **Tool** | Acts once (idempotent), re-checks hard limits itself, logs everything |

## Four decisions that shaped it
**1. The AI can only propose.** The Resolver suggests one of three allow-listed actions. Whether it happens is decided by plain code: refunds only on the ticket owner's delivered orders, within 30 days, never above the refundable balance. A manipulated or confused model can at most *ask*.

**2. Spend above a limit needs a person.** Refunds over $100 go to an approval queue; nothing executes until someone approves. The limit is policy, not model judgment, and the launch plan starts it lower ($50) and raises it after a clean week.

**3. Denials feed back, so customers still get an answer.** When the Policy Guard says no ("it has already shipped"), the reason goes back to the Resolver, which writes a kind, policy-grounded explanation instead of a dead end. Bounded to two revisions; after that, a person takes over.

**4. Safety-critical messages are templates.** "A specialist will reply within 24 hours", "your refund needs a quick review": these are fixed text, never generated, so they can't promise something the system won't do.

## What broke, and what I designed against
**Found by a test during the build:**
- **The Executor trusted the Policy Guard too much.** A unit test showed the Executor would refund an order that hadn't been delivered if anything ever slipped past policy. Fix: the Executor re-checks its own hard limits (delivered, amount within balance). Defense in depth, not a single gate.

**Designed in from the start, and covered by tests:**
- **Duplicate tickets mustn't double-refund.** A second ticket for the same broken item is common. Idempotency keys plus a policy check on the remaining balance handle it. In the sample inbox, the second refund request for the same order is now denied and explained.
- **A rogue amount mustn't need luck to catch.** Tests inject a $999 refund on a $45 order. The Policy Guard denies it, the reason goes back, the Resolver proposes the correct $45, and only that executes.

## How it's measured
Safety metrics are release gates: any value above zero blocks a deploy.

| Metric | Gate | Current (offline) |
|---|---|---|
| Eval tickets passing | 100% | 19 / 19 |
| Wrong or unauthorized actions | 0 | 0 |
| Replies promising something that didn't happen | 0 | 0 |
| Card numbers leaked | 0 | 0 |
| Must-escalate tickets that reached a person | 100% | 100% |
| Resolved without a person | 50-65% target | 63% |

Plus 16 unit tests. The browser demo is a JavaScript port of the same logic; on the 11-ticket sample inbox it matches the Python system ticket for ticket (status and customer reply). As with the Copilot, **offline runs use a deterministic stand-in model with injected faults: they prove the safety net, not live-model quality.**

Auto-resolution is a target band, not something to maximize: pushing it higher usually means escalating less, which trades safety for a vanity number.

## What I'd do next
1. Live evals on a real model, plus 150+ labeled real tickets across intents.
2. Shadow mode first: run on real tickets, send nothing, compare every decision with the human's (see [`docs/LAUNCH_PLAN.md`](docs/LAUNCH_PLAN.md)).
3. Embedding-based retrieval with its own retrieval eval, and multi-turn replies for "awaiting customer" tickets.

## What I learned
Agent design is mostly deciding **who is allowed to decide**. Language models are great at reading messy tickets and writing kind replies; they shouldn't be the last word on money. Putting the decision in code also made the system easy to test: every rule became a unit test, and every "what if the model does something weird" became an injected fault in the evals.

---
Code, tests and evals: this folder · Browser demo: [`demo/index.html`](demo/index.html) · Full PRD: [`docs/PRD.md`](docs/PRD.md)
