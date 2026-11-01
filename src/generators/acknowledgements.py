import random
from datetime import timedelta
from src.config import Config
from src.ids import ack_id, promise_id


def ack_status(accepted: int, ordered: int) -> str:
    if accepted == ordered:
        return "ACCEPTED"
    if accepted == 0:
        return "REJECTED"
    return "PARTIALLY_ACCEPTED"


def _slip_days(rng: random.Random, risk: float) -> int:
    if rng.random() < 0.15 + 0.6 * risk:
        return rng.randint(1, 5 + int(risk * 30))
    return 0


def _accepted_qty(rng: random.Random, ordered: int, risk: float) -> int:
    roll = rng.random()
    if roll < 0.02 + 0.05 * risk:
        return 0                                   # full rejection
    if roll < 0.10 + 0.25 * risk:
        return int(ordered * rng.uniform(0.4, 0.95))   # partial
    return ordered                                 # full acceptance


def generate_acknowledgements(cfg: Config, rng: random.Random,
                              suppliers: list[dict], pos: list[dict],
                              lines: list[dict]):
    sup = {s["supplier_id"]: s for s in suppliers}
    po_by_id = {p["po_id"]: p for p in pos}
    seq_by_po: dict[str, int] = {}

    acks, promises = [], []

    for line in lines:
        po = po_by_id[line["po_id"]]
        supplier = sup[po["supplier_id"]]
        risk = 1 - supplier["reliability_score"]

        # supplier silence: no rows at all for this line
        if rng.random() < 0.03 + 0.20 * risk:
            continue

        ordered = line["ordered_qty"]
        accepted = _accepted_qty(rng, ordered, risk)
        price = line["unit_price"]
        if rng.random() < 0.08 + 0.10 * risk:
            price = round(price * (1 + rng.uniform(0.01, 0.12)), 2)

        ack_date = po["order_date"] + timedelta(days=rng.randint(1, 3 + int(risk * 10)))
        promised = line["requested_date"] + timedelta(days=_slip_days(rng, risk))
        n_revisions = 2 if rng.random() < 0.5 * risk else 1

        for rev in range(1, n_revisions + 1):
            if rev > 1:
                ack_date += timedelta(days=rng.randint(3, 15))
                promised += timedelta(days=rng.randint(1, 10))

            seq_by_po[po["po_id"]] = seq_by_po.get(po["po_id"], 0) + 1
            acks.append({
                "ack_id": ack_id(po["po_id"], seq_by_po[po["po_id"]]),
                "po_id": po["po_id"],
                "po_line_id": line["po_line_id"],
                "revision_no": rev,
                "ack_date": ack_date,
                "accepted_qty": accepted,
                "rejected_qty": ordered - accepted,
                "confirmed_unit_price": price,
                "ack_status": ack_status(accepted, ordered),
            })

            if accepted > 0:
                promises.append({
                    "promise_id": promise_id(line["po_line_id"], rev),
                    "po_line_id": line["po_line_id"],
                    "ack_id": acks[-1]["ack_id"],
                    "revision_no": rev,
                    "promised_date": promised,
                    "effective_from": ack_date,
                })

    return acks, promises