# Launch Plan

## Gate 0: Before any customer sees it
- [ ] Live-model evals pass all safety gates (wrong action, false promise, PII = 0; escalation recall = 100%)
- [ ] Eval set grown to 150+ anonymized real tickets, labeled by the support team
- [ ] Finance signs off on the $100 auto-refund limit and the approval flow
- [ ] Support leads review 50 handoff summaries and agree they're useful
- [ ] Alerts wired; on-call owner named; kill switch tested

## Phase 1: Shadow mode (2 weeks)
The system runs on real tickets but **sends nothing and executes nothing**. Humans work as usual. Compare its decision to the human's on every ticket.
**Exit:** ≥ 95% agreement on action decisions, zero cases where it would have refunded when a human didn't.

## Phase 2: Draft assist (2 weeks)
Agents see the proposed reply and action and click to approve or edit. Measure edit rate and time saved.
**Exit:** < 15% of drafts materially edited; agents report it saves time.

## Phase 3: Autopilot for read-only intents (2 weeks)
Auto-send for order status, help-center questions and password resets. Money-moving intents stay in draft assist.

## Phase 4: Autopilot for refunds and cancellations (gradual)
5% → 25% → 100% of eligible tickets, with refund limit starting at $50 and raised to $100 after a clean week.
**Rollback trigger:** any invariant violation, reopen rate above human baseline, or CSAT drop > 5 pts.

## Controls
- **Kill switch:** one flag routes every ticket to `escalated` (customers still get the holding reply).
- **Per-intent flags** to turn automation on or off by intent.
- **Policy as config:** limits and windows change without a deploy, with an audit entry.
- **Canary** for any prompt or model change, compared on eval + live metrics.

## Communication
- Customers: replies are signed as an assistant, with "reply 'agent' to reach a person" in every message.
- Support team: the goal is to remove the repetitive queue, not headcount; involve them in labeling evals.
