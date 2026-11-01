from dataclasses import dataclass
from datetime import date

SEED = 20261022


@dataclass(frozen=True)
class Config:
    seed: int = SEED
    n_pos: int = 10_000
    n_suppliers: int = 200
    year: int = 2026
    start_date: date = date(2026, 1, 1)
    end_date: date = date(2026, 12, 31)
    as_of_date: date = date(2027, 1, 15)  # "today" inside the simulated world
    production_order_ratio: float = 0.30  # production orders per PO

    @property
    def n_production_orders(self) -> int:
        return int(self.n_pos * self.production_order_ratio)


# Approval thresholds (above these, a human must approve)
PRICE_CHANGE_PCT_LIMIT = 5.0
QTY_CHANGE_PCT_LIMIT = 10.0
DATE_SLIP_DAYS_LIMIT = 7

# Hard limits (above these, the change is rejected)
PRICE_CHANGE_PCT_HARD = 10.0
QTY_CHANGE_PCT_HARD = 30.0
DATE_SLIP_DAYS_HARD = 21

# A change that needs approval and was raised within this many days
# of as_of_date is still undecided (PENDING_APPROVAL)
PENDING_WINDOW_DAYS = 14

# Notification severity (days a production order's supply is late)
HIGH_SEVERITY_LATE_DAYS = 14
MEDIUM_SEVERITY_LATE_DAYS = 7