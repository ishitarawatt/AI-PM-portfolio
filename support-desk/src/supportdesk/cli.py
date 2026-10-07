"""CLI.

  python -m supportdesk.cli ticket --customer C1 --body "My order ORD-1001 arrived broken"
  python -m supportdesk.cli batch data/inbox.json
Add --live to use the real Anthropic API (needs ANTHROPIC_API_KEY).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .llm import AnthropicClient, MockClient
from .monitoring import Tracer, dashboard
from .orchestrator import Orchestrator
from .schemas import Ticket
from .tools import Store


def _render(r) -> str:
    lines = [f"[{r.ticket_id}] {r.status.upper()}  trace={r.trace_id}"]
    if r.triage:
        lines.append(f"  triage : {r.triage.intent} | order={r.triage.order_id} | "
                     f"{r.triage.sentiment} | conf={r.triage.confidence:.2f}")
    if r.kb_used:
        lines.append(f"  kb     : {', '.join(r.kb_used)}")
    if r.action_executed:
        lines.append(f"  action : {json.dumps(r.action_executed)}")
    if r.pending_action:
        lines.append(f"  pending: {json.dumps(r.pending_action)} (awaiting human approval)")
    if r.flags:
        lines.append(f"  flags  : {', '.join(r.flags)}")
    if r.handoff:
        lines.append(f"  handoff: reason={r.handoff['reason']}")
    if r.customer_reply:
        lines.append(f"  reply  : {r.customer_reply}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Support Desk multi-agent resolver")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--logs", default="logs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("ticket")
    t.add_argument("--customer", required=True)
    t.add_argument("--subject", default="")
    t.add_argument("--body", required=True)
    b = sub.add_parser("batch")
    b.add_argument("inbox", type=Path)
    args = ap.parse_args(argv)

    logs = Path(args.logs)
    store = Store(audit_path=logs / "audit.jsonl")
    tracer = Tracer(logs / "traces.jsonl")
    llm = AnthropicClient() if args.live else MockClient()
    orch = Orchestrator(llm, store, tracer)

    if args.cmd == "ticket":
        tickets = [Ticket("T-cli", args.customer, args.subject, args.body)]
    else:
        tickets = [Ticket(**t) for t in json.loads(args.inbox.read_text())]

    results = [orch.run(tk) for tk in tickets]
    for r in results:
        print(_render(r), end="\n\n")
    if args.cmd == "batch":
        print("== DASHBOARD ==")
        print(json.dumps(dashboard(results, store, tracer), indent=2))
        if store.approval_queue:
            print("\n== APPROVAL QUEUE ==")
            for item in store.approval_queue:
                print(f"  {item['ticket_id']}: {json.dumps(item['action'])}")
    print(f"\nAudit log: {logs / 'audit.jsonl'}   Traces: {logs / 'traces.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
