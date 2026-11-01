import random
from src.config import Config
from src.generators.suppliers import generate_suppliers
from src.generators.purchase_orders import generate_purchase_orders
from src.generators.acknowledgements import generate_acknowledgements

def build(seed=20261022, n=200):
    cfg = Config(seed=seed, n_pos=n)
    rng = random.Random(seed)
    sup = generate_suppliers(cfg, rng)
    pos, lines = generate_purchase_orders(cfg, rng, sup)
    acks, prom = generate_acknowledgements(cfg, rng, sup, pos, lines)
    return pos, lines, acks, prom

def test_po_total_equals_sum_of_lines():
    pos, lines, _, _ = build()
    for po in pos:
        s = round(sum(l["line_total"] for l in lines if l["po_id"] == po["po_id"]), 2)
        assert po["total_amount"] == s

def test_ack_quantities_reconcile():
    _, lines, acks, _ = build()
    ordered = {l["po_line_id"]: l["ordered_qty"] for l in lines}
    for a in acks:
        assert a["accepted_qty"] + a["rejected_qty"] == ordered[a["po_line_id"]]

def test_same_seed_same_output():
    assert build() == build()