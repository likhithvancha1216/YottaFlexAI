import random
from collections import defaultdict

from src.config import Config
from src.generators.suppliers import generate_suppliers
from src.generators.purchase_orders import generate_purchase_orders
from src.generators.acknowledgements import generate_acknowledgements
from src.generators.changes import generate_changes
from src.generators.downstream import (
    generate_inventory_plan, generate_production_orders, generate_notifications,
)


def build(seed=20261022, n=300):
    cfg = Config(seed=seed, n_pos=n)
    rng = random.Random(seed)
    sup = generate_suppliers(cfg, rng)
    pos, lines = generate_purchase_orders(cfg, rng, sup)
    acks, prom = generate_acknowledgements(cfg, rng, sup, pos, lines)
    chg, apr = generate_changes(cfg, rng, pos, lines, acks, prom)
    plans = generate_inventory_plan(pos, lines, chg, apr)
    prods, bridge = generate_production_orders(cfg, rng, pos, lines)
    notes = generate_notifications(cfg, plans, prods, bridge)
    return dict(lines=lines, chg=chg, plans=plans, prods=prods,
                bridge=bridge, notes=notes)


def test_only_approved_changes_create_plan_rows():
    d = build()
    status = {c["change_id"]: c["status"] for c in d["chg"]}
    for p in d["plans"]:
        if p["source_change_id"] is not None:
            assert status[p["source_change_id"]] in ("AUTO_APPROVED", "APPROVED")


def test_plan_versions_are_contiguous_and_closed():
    d = build()
    by_line = defaultdict(list)
    for p in d["plans"]:
        by_line[p["po_line_id"]].append(p)
    assert len(by_line) == len(d["lines"])          # every line has a plan
    for rows in by_line.values():
        rows.sort(key=lambda r: r["plan_version"])
        assert [r["plan_version"] for r in rows] == list(range(1, len(rows) + 1))
        assert rows[0]["update_type"] == "BASELINE"
        for a, b in zip(rows, rows[1:]):
            assert a["effective_to"] == b["effective_from"]
        assert rows[-1]["effective_to"] is None


def test_allocations_never_exceed_ordered_qty():
    d = build()
    ordered = {l["po_line_id"]: l["ordered_qty"] for l in d["lines"]}
    used = defaultdict(int)
    for b in d["bridge"]:
        used[b["po_line_id"]] += b["allocated_qty"]
    for line_id, qty in used.items():
        assert qty <= ordered[line_id]


def test_notifications_have_valid_parents_and_right_recipient():
    d = build()
    plan_ids = {p["plan_id"] for p in d["plans"]}
    prod = {p["production_order_id"]: p for p in d["prods"]}
    for n in d["notes"]:
        assert n["plan_id"] in plan_ids
        assert n["recipient_planner_id"] == prod[n["production_order_id"]]["planner_id"]
        assert n["days_late"] > 0 or n["shortfall_qty"] > 0


def test_same_seed_same_output():
    assert build() == build()