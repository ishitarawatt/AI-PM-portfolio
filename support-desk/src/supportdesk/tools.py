"""Backend tools the agents can act through: order store, action executor, approval queue, audit log.

In production these would be calls to your order system / identity provider. The executor
re-checks hard invariants itself (defense in depth), is idempotent, and audits every call.
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class Store:
    def __init__(self, data_dir: str | Path = DATA_DIR, audit_path: str | Path | None = None):
        d = Path(data_dir)
        self.orders: dict = json.loads((d / "orders.json").read_text())
        self.customers: dict = json.loads((d / "customers.json").read_text())
        self.kb: list = json.loads((d / "kb.json").read_text())
        self.audit: list[dict] = []
        self.approval_queue: list[dict] = []
        self._idempotency: dict[str, dict] = {}
        self.audit_path = Path(audit_path) if audit_path else None
        if self.audit_path:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def snapshot(self) -> dict:
        return copy.deepcopy(self.orders)

    def _log(self, entry: dict) -> None:
        entry = {"ts": round(time.time(), 3), **entry}
        self.audit.append(entry)
        if self.audit_path:
            with self.audit_path.open("a") as f:
                f.write(json.dumps(entry) + "\n")

    def queue_approval(self, ticket_id: str, action: dict) -> None:
        item = {"ticket_id": ticket_id, "action": action, "state": "pending"}
        self.approval_queue.append(item)
        self._log({"event": "approval_queued", **item})

    def execute(self, action: dict, idempotency_key: str, ticket_id: str) -> dict:
        if idempotency_key in self._idempotency:
            prior = dict(self._idempotency[idempotency_key])
            prior["duplicate"] = True
            return prior

        kind, p = action["type"], action.get("params", {})
        result: dict
        if kind == "refund":
            order = self.orders.get(p.get("order_id"))
            amount = float(p.get("amount", 0))
            refundable = round(order["total"] - order["refunded"], 2) if order else 0
            if not order or order["status"] != "delivered" or amount <= 0 or amount > refundable + 1e-9:
                result = {"ok": False, "detail": "invariant_violation: order not refundable for that amount"}
            else:
                order["refunded"] = round(order["refunded"] + amount, 2)
                result = {"ok": True, "detail": f"refunded {amount:.2f} on {order['id']}"}
        elif kind == "cancel_order":
            order = self.orders.get(p.get("order_id"))
            if not order or order["status"] != "processing":
                result = {"ok": False, "detail": "invariant_violation: order not cancellable"}
            else:
                order["status"] = "cancelled"
                result = {"ok": True, "detail": f"cancelled {order['id']}"}
        elif kind == "password_reset":
            ok = p.get("customer_id") in self.customers
            result = {"ok": ok, "detail": "reset link sent" if ok else "unknown customer"}
        else:
            result = {"ok": False, "detail": f"unknown action {kind!r}"}

        self._idempotency[idempotency_key] = result
        self._log({"event": "action", "ticket_id": ticket_id, "action": action,
                   "key": idempotency_key, **result})
        return result
