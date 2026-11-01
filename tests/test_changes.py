import random
from src.config import Config
from src.generators.suppliers import generate_suppliers
from src.generators.purchase_orders import generate_purchase_orders
from src.generators.acknowledgements import generate_acknowledgements
from src.generators.changes import generate_changes


def build_all(seed=20261022, n=300):
    cfg = Config(seed=seed, n_pos=n)
    rng = random.Random(seed)
    sup = generate_suppliers(cfg, rng)
    pos, lines = generate_purchase_orders(cfg, rng, sup)
    acks, prom = generate_acknowledgements(cfg, rng, sup, pos, lines)
    chg, apr = generate_changes(cfg, rng, pos, lines, acks, prom)
    return pos, lines, acks, prom, chg, apr


def test_change_foreign_keys_exist():
    _, lines, acks, _, chg, _ = build_all()
    line_ids = {l["po_line_id"] for l in lines}
    ack_ids = {a["ack_id"] for a in acks}
    for c in chg:
        assert c["po_line_id"] in line_ids and c["ack_id"] in ack_ids

def test_status_matches_approval_rows():
    *_, chg, apr = build_all()
    decided = {a["change_id"]: a for a in apr}
    for c in chg:
        if c["status"] == "PENDING_APPROVAL":
            assert c["change_id"] not in decided
        else:
            assert decided[c["change_id"]]["decision"] == c["status"]

def test_superseded_change_is_same_line_and_older():
    *_, chg, _ = build_all()
    by_id = {c["change_id"]: c for c in chg}
    for c in chg:
        if c["supersedes_change_id"]:
            old = by_id[c["supersedes_change_id"]]
            assert old["po_line_id"] == c["po_line_id"]
            assert old["revision_no"] < c["revision_no"]