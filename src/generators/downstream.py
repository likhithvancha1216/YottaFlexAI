import random
from collections import defaultdict
from datetime import timedelta

from src.config import (
    Config, HIGH_SEVERITY_LATE_DAYS, MEDIUM_SEVERITY_LATE_DAYS,
)
from src.ids import plan_id, prod_id, not_id

APPLIED_STATUSES = ("AUTO_APPROVED", "APPROVED")
PRODUCTS = ["Pump assembly", "Motor unit", "Control cabinet", "Valve block"]
N_PLANNERS = 15
LINE_WINDOW = 120        # lines considered "nearby" when grouping parts into a job
LINKS_CHOICES = [1, 2, 3]
LINKS_WEIGHTS = [30, 50, 20]


# ---------------------------------------------------------------- InventoryPlan
def generate_inventory_plan(pos: list[dict], lines: list[dict],
                            changes: list[dict], approvals: list[dict]) -> list[dict]:
    po_by_id = {p["po_id"]: p for p in pos}
    decision_by_change = {a["change_id"]: a for a in approvals}

    applied_by_line = defaultdict(list)
    for c in changes:
        if c["status"] in APPLIED_STATUSES:
            applied_by_line[c["po_line_id"]].append(c)

    plans = []
    for line in lines:
        po = po_by_id[line["po_id"]]

        versions = [{
            "update_type": "BASELINE",
            "source_change_id": None,
            "expected_qty": line["ordered_qty"],
            "expected_date": line["requested_date"],
            "effective_from": po["order_date"],
        }]
        prev_from = po["order_date"]

        pending = sorted(applied_by_line.get(line["po_line_id"], []),
                         key=lambda c: c["revision_no"])
        for c in pending:
            decided = decision_by_change[c["change_id"]]["decision_date"]
            eff = max(decided, prev_from)      # versions never go back in time
            versions.append({
                "update_type": "CHANGE_APPLIED",
                "source_change_id": c["change_id"],
                "expected_qty": c["proposed_qty"],
                "expected_date": c["proposed_date"] or line["requested_date"],
                "effective_from": eff,
            })
            prev_from = eff

        for i, v in enumerate(versions):
            next_from = versions[i + 1]["effective_from"] if i + 1 < len(versions) else None
            plans.append({
                "plan_id": plan_id(line["po_line_id"], i + 1),
                "po_line_id": line["po_line_id"],
                "item_code": line["item_code"],
                "plan_version": i + 1,
                **v,
                "effective_to": next_from,
            })
    return plans


# -------------------------------------------------------------- ProductionOrder
def generate_production_orders(cfg: Config, rng: random.Random,
                               pos: list[dict], lines: list[dict]):
    po_by_id = {p["po_id"]: p for p in pos}
    remaining = {l["po_line_id"]: l["ordered_qty"] for l in lines}

    drafts = []
    for _ in range(cfg.n_production_orders):
        anchor = rng.randrange(len(lines))
        end = min(anchor + LINE_WINDOW, len(lines))
        k = min(rng.choices(LINKS_CHOICES, weights=LINKS_WEIGHTS)[0], end - anchor)

        links = []
        for i in rng.sample(range(anchor, end), k):
            line = lines[i]
            rem = remaining[line["po_line_id"]]
            if rem <= 0:
                continue
            alloc = min(rem, max(1, int(line["ordered_qty"] * rng.uniform(0.4, 0.8))))
            remaining[line["po_line_id"]] -= alloc
            links.append((line, alloc))
        if not links:
            continue

        drafts.append({
            "links": links,
            "product_name": rng.choice(PRODUCTS),
            "planner_id": f"PLN-{rng.randint(1, N_PLANNERS):03d}",
            "quantity_to_build": rng.randint(1, 20) * 10,
            "need_date": max(l["requested_date"] for l, _ in links)
                         + timedelta(days=rng.randint(0, 14)),
            "created_date": max(po_by_id[l["po_id"]]["order_date"] for l, _ in links),
        })

    drafts.sort(key=lambda d: (d["created_date"], d["need_date"],
                               d["links"][0][0]["po_line_id"]))

    production_orders, bridge = [], []
    for n, d in enumerate(drafts, start=1):
        pid = prod_id(n, cfg.year)
        production_orders.append({
            "production_order_id": pid,
            "product_name": d["product_name"],
            "planner_id": d["planner_id"],
            "quantity_to_build": d["quantity_to_build"],
            "need_date": d["need_date"],
            "created_date": d["created_date"],
            "status": "RELEASED" if d["need_date"] <= cfg.as_of_date else "PLANNED",
        })
        for line, alloc in d["links"]:
            bridge.append({
                "production_order_id": pid,
                "po_line_id": line["po_line_id"],
                "allocated_qty": alloc,
            })
    return production_orders, bridge


# ----------------------------------------------------------------- Notification
def _severity(days_late: int, shortfall_qty: int) -> str:
    if shortfall_qty > 0 or days_late > HIGH_SEVERITY_LATE_DAYS:
        return "HIGH"
    if days_late > MEDIUM_SEVERITY_LATE_DAYS:
        return "MEDIUM"
    return "LOW"


def generate_notifications(cfg: Config, plans: list[dict],
                           production_orders: list[dict], bridge: list[dict]):
    prod_by_id = {p["production_order_id"]: p for p in production_orders}
    links_by_line = defaultdict(list)
    for b in bridge:
        links_by_line[b["po_line_id"]].append(b)

    drafts = []
    for plan in plans:
        if plan["source_change_id"] is None:          # baseline: nothing changed
            continue
        for link in links_by_line.get(plan["po_line_id"], []):
            prod = prod_by_id[link["production_order_id"]]

            days_late = 0
            if plan["expected_qty"] > 0:
                days_late = max(0, (plan["expected_date"] - prod["need_date"]).days)
            shortfall = max(0, link["allocated_qty"] - plan["expected_qty"])
            if days_late == 0 and shortfall == 0:
                continue                              # this job is not affected

            if days_late and shortfall:
                impact = "DELAY_AND_SHORTFALL"
            elif days_late:
                impact = "DELAY"
            else:
                impact = "SHORTFALL"

            drafts.append({
                "change_id": plan["source_change_id"],
                "plan_id": plan["plan_id"],
                "po_line_id": plan["po_line_id"],
                "production_order_id": prod["production_order_id"],
                "recipient_planner_id": prod["planner_id"],
                "impact_type": impact,
                "days_late": days_late,
                "shortfall_qty": shortfall,
                "severity": _severity(days_late, shortfall),
                "created_date": max(plan["effective_from"], prod["created_date"]),
            })

    drafts.sort(key=lambda d: (d["created_date"], d["change_id"], d["production_order_id"]))

    notifications = []
    for n, d in enumerate(drafts, start=1):
        notifications.append({
            "notification_id": not_id(n, cfg.year),
            **d,
            "message": (f"{d['production_order_id']} at risk: {d['impact_type']} "
                        f"(late {d['days_late']}d, short {d['shortfall_qty']}) "
                        f"after change {d['change_id']}"),
            "status": "SENT",
        })
    return notifications