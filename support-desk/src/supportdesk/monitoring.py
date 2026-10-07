"""Tracing: one JSON line per agent step, plus run-level aggregation for a dashboard.

Span fields map 1:1 onto OpenTelemetry / Langfuse; swap `_emit` to ship them there.
Token counts are approximate (chars / 4) and prices illustrative.
"""
from __future__ import annotations

import json
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

PRICE_PER_MTOK = (3.0, 15.0)   # illustrative $ per 1M tokens (input, output)


def approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class Tracer:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.spans: list[dict] = []
        self._lock = Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_trace_id() -> str:
        return uuid.uuid4().hex[:12]

    @contextmanager
    def span(self, trace_id: str, agent: str, input_text: str = "", llm: bool = False):
        rec = {"trace_id": trace_id, "agent": agent, "status": "ok", "retries": 0,
               "in_tokens": approx_tokens(input_text) if llm else 0, "out_tokens": 0}
        start = time.perf_counter()
        try:
            yield rec
        except Exception as e:
            rec["status"], rec["error"] = "error", f"{type(e).__name__}: {e}"
            raise
        finally:
            rec["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
            rec["cost_usd"] = round((rec["in_tokens"] * PRICE_PER_MTOK[0]
                                     + rec["out_tokens"] * PRICE_PER_MTOK[1]) / 1e6, 6)
            with self._lock:
                self.spans.append(rec)
                if self.path:
                    with self.path.open("a") as f:
                        f.write(json.dumps(rec) + "\n")

    def summary(self) -> dict:
        n = len(self.spans)
        if not n:
            return {"spans": 0}
        per_trace: dict[str, float] = {}
        for s in self.spans:
            per_trace[s["trace_id"]] = per_trace.get(s["trace_id"], 0) + s["latency_ms"]
        lat = sorted(per_trace.values())
        return {
            "spans": n,
            "span_error_rate": round(sum(s["status"] == "error" for s in self.spans) / n, 4),
            "ticket_p50_ms": round(lat[len(lat) // 2], 2),
            "ticket_p95_ms": round(lat[min(len(lat) - 1, int(len(lat) * 0.95))], 2),
            "total_cost_usd": round(sum(s["cost_usd"] for s in self.spans), 6),
            "llm_retries": sum(s["retries"] for s in self.spans),
        }


def dashboard(results: list, store, tracer: Tracer) -> dict:
    """Business-level view of a batch run."""
    n = len(results)
    status = Counter(r.status for r in results)
    reasons = Counter(r.handoff["reason"] for r in results if r.handoff)
    refunds = [r.action_executed for r in results
               if r.action_executed and r.action_executed["type"] == "refund"]
    return {
        "tickets": n,
        "by_status": dict(status),
        "auto_resolution_rate": round(status.get("resolved", 0) / n, 3) if n else 0,
        "actions_executed": Counter(r.action_executed["type"] for r in results if r.action_executed),
        "refunded_usd": round(sum(a["params"]["amount"] for a in refunds), 2),
        "approvals_pending": len(store.approval_queue),
        "escalations_by_reason": dict(reasons),
        "policy_denials": sum(any(f.startswith("policy_denied") for f in r.flags) for r in results),
        "qa_rejections": sum(f == "qa_rejected" for r in results for f in r.flags),
        "injection_attempts": sum("prompt_injection_removed" in r.flags for r in results),
        **tracer.summary(),
    }
