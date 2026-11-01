import random
from src.config import Config
from src.ids import supplier_id

COUNTRIES = ["India", "China", "Germany", "Vietnam", "Mexico", "USA"]
STATUSES = ["ACTIVE", "ACTIVE", "ACTIVE", "ON_HOLD"]   # weighted: mostly active

def generate_suppliers(cfg: Config, rng: random.Random) -> list[dict]:
    rows = []
    for n in range(1, cfg.n_suppliers + 1):
        reliability = round(rng.betavariate(5, 2), 3)      # skews high, 0..1
        rows.append({
            "supplier_id": supplier_id(n),
            "supplier_name": f"Supplier {n:04d} Ltd",
            "country": rng.choice(COUNTRIES),
            "standard_lead_time_days": rng.randint(7, 60),
            "reliability_score": reliability,
            "status": rng.choice(STATUSES),
        })
    return rows