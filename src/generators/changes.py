import random
from datetime import timedelta
from src.config import Config, PENDING_WINDOW_DAYS
from src.ids import chg_id, apr_id
from src.rules import price_delta_pct, qty_shortfall_pct, date_slip_days, evaluate


def _approver_id(rng: random.Random, role: str, po: dict) -> str:
    if role == "SYSTEM":
        return "SYSTEM"
    if role == "PLANNER":
        return po["planner_id"]
    return f"MGR-{rng.randint(1, 3):03d}"


def generate_changes(cfg: Config, rng: random.Random, pos: list[dict],
                     lines: list[dict], acks: list[dict], promises: list[dict]):
    po_by_id = {p["po_id"]: p for p in pos}
    line_by_id = {l["po_line_id"]: l for l in lines}
    promise_by_ack = {p["ack_id"]: p for p in promises}
    pending_cutoff = cfg.as_of_date - timedelta(days=PENDING_WINDOW_DAYS)

    seq_by_po: dict[str, int] = {}
    last_chg_by_line: dict[str, str] = {}
    changes, approvals = [], []

    for ack in acks:
        line = line_by_id[ack["po_line_id"]]
        po = po_by_id[ack["po_id"]]
        prom = promise_by_ack.get(ack["ack_id"])

        price_pct = price_delta_pct(line["unit_price"], ack["confirmed_unit_price"])
        qty_pct = qty_shortfall_pct(line["ordered_qty"], ack["accepted_qty"])
        slip = date_slip_days(line["requested_date"], prom["promised_date"]) if prom else 0

        if price_pct == 0 and qty_pct == 0 and slip == 0:
            continue                                   # nothing changed

        seq_by_po[po["po_id"]] = seq_by_po.get(po["po_id"], 0) + 1
        cid = chg_id(po["po_id"], seq_by_po[po["po_id"]])
        d = evaluate(price_pct, qty_pct, slip, ack["accepted_qty"])

        if not d.needs_approval:
            status, decision_date = "AUTO_APPROVED", ack["ack_date"]
        elif ack["ack_date"] >= pending_cutoff:
            status, decision_date = "PENDING_APPROVAL", None
        else:
            status = d.outcome
            decision_date = ack["ack_date"] + timedelta(days=rng.randint(1, 4))

        changes.append({
            "change_id": cid,
            "po_id": po["po_id"],
            "po_line_id": line["po_line_id"],
            "ack_id": ack["ack_id"],
            "promise_id": prom["promise_id"] if prom else None,
            "revision_no": ack["revision_no"],
            "change_types": "|".join(
                t for t, v in (("PRICE", price_pct), ("QTY", qty_pct), ("DATE", slip)) if v != 0),
            "requested_unit_price": line["unit_price"],
            "proposed_unit_price": ack["confirmed_unit_price"],
            "price_delta_pct": price_pct,
            "requested_qty": line["ordered_qty"],
            "proposed_qty": ack["accepted_qty"],
            "qty_shortfall_pct": qty_pct,
            "requested_date": line["requested_date"],
            "proposed_date": prom["promised_date"] if prom else None,
            "date_slip_days": slip,
            "breached_rules": "|".join(d.breaches),
            "approval_required": d.needs_approval,
            "supersedes_change_id": last_chg_by_line.get(line["po_line_id"]),
            "created_date": ack["ack_date"],
            "status": status,
        })

        if decision_date is not None:
            approvals.append({
                "approval_id": apr_id(cid, 1),
                "change_id": cid,
                "approval_seq": 1,
                "approver_role": d.approver_role,
                "approver_id": _approver_id(rng, d.approver_role, po),
                "decision": status,
                "decision_date": decision_date,
                "reason": d.reason,
            })

        last_chg_by_line[line["po_line_id"]] = cid

    return changes, approvals