import random
from datetime import timedelta
from src.config import Config
from src.ids import po_id, line_id

ITEMS = [
    ("ITM-1001", "Steel bracket", "EA", 40.00),
    ("ITM-1002", "Aluminium housing", "EA", 125.00),
    ("ITM-1003", "Copper wire spool", "EA", 310.00),
    ("ITM-1004", "Control board", "EA", 520.00),
    ("ITM-1005", "Rubber gasket", "EA", 8.50),
    ("ITM-1006", "Fastener kit", "EA", 22.00),
]
LINE_COUNT_CHOICES = [1, 2, 3]
LINE_COUNT_WEIGHTS = [60, 30, 10]
N_PLANNERS = 15


def generate_purchase_orders(cfg: Config, rng: random.Random, suppliers: list[dict]):
    active = [s for s in suppliers if s["status"] == "ACTIVE"]
    span = (cfg.end_date - cfg.start_date).days

    order_dates = sorted(
        cfg.start_date + timedelta(days=rng.randint(0, span))
        for _ in range(cfg.n_pos)
    )

    pos, lines = [], []
    for n, order_date in enumerate(order_dates, start=1):
        supplier = rng.choice(active)
        pid = po_id(n, cfg.year)
        n_lines = rng.choices(LINE_COUNT_CHOICES, weights=LINE_COUNT_WEIGHTS)[0]

        po_lines = []
        for ln in range(1, n_lines + 1):
            code, desc, uom, base_price = rng.choice(ITEMS)
            qty = rng.randint(1, 40) * 50
            price = round(base_price * rng.uniform(0.9, 1.1), 2)
            lead = supplier["standard_lead_time_days"] + rng.randint(0, 10)
            po_lines.append({
                "po_line_id": line_id(pid, ln),
                "po_id": pid,
                "line_number": ln,
                "item_code": code,
                "item_description": desc,
                "uom": uom,
                "ordered_qty": qty,
                "unit_price": price,
                "line_total": round(qty * price, 2),
                "requested_date": order_date + timedelta(days=lead),
                "status": "OPEN",
            })

        pos.append({
            "po_id": pid,
            "supplier_id": supplier["supplier_id"],
            "planner_id": f"PLN-{rng.randint(1, N_PLANNERS):03d}",
            "order_date": order_date,
            "currency": "USD",
            "status": "ISSUED",
            "total_amount": round(sum(l["line_total"] for l in po_lines), 2),
        })
        lines.extend(po_lines)

    return pos, lines