from dataclasses import dataclass
from src.config import (
    PRICE_CHANGE_PCT_LIMIT, QTY_CHANGE_PCT_LIMIT, DATE_SLIP_DAYS_LIMIT,
    PRICE_CHANGE_PCT_HARD, QTY_CHANGE_PCT_HARD, DATE_SLIP_DAYS_HARD,
)


def price_delta_pct(requested: float, proposed: float) -> float:
    return round((proposed - requested) / requested * 100, 2)


def qty_shortfall_pct(ordered: int, accepted: int) -> float:
    return round((ordered - accepted) / ordered * 100, 2)


def date_slip_days(requested_date, promised_date) -> int:
    return (promised_date - requested_date).days


@dataclass(frozen=True)
class Decision:
    needs_approval: bool
    breaches: tuple          # e.g. ("PRICE", "DATE")
    outcome: str             # AUTO_APPROVED | APPROVED | REJECTED
    approver_role: str       # SYSTEM | PLANNER | OPS_MANAGER
    reason: str


def evaluate(price_pct: float, qty_pct: float, slip_days: int,
             accepted_qty: int) -> Decision:
    breaches = []
    if abs(price_pct) > PRICE_CHANGE_PCT_LIMIT:
        breaches.append("PRICE")
    if qty_pct > QTY_CHANGE_PCT_LIMIT:
        breaches.append("QTY")
    if slip_days > DATE_SLIP_DAYS_LIMIT:
        breaches.append("DATE")
    breaches = tuple(breaches)

    if not breaches:
        return Decision(False, (), "AUTO_APPROVED", "SYSTEM",
                        "all deltas within thresholds")

    if accepted_qty == 0:
        return Decision(True, breaches, "APPROVED", "OPS_MANAGER",
                        "supplier declined line; loss of supply confirmed")

    over_hard = (abs(price_pct) > PRICE_CHANGE_PCT_HARD
                 or qty_pct > QTY_CHANGE_PCT_HARD
                 or slip_days > DATE_SLIP_DAYS_HARD)
    if over_hard:
        return Decision(True, breaches, "REJECTED", "OPS_MANAGER",
                        "exceeds hard limit; supplier terms not accepted")

    role = "PLANNER" if len(breaches) == 1 else "OPS_MANAGER"
    return Decision(True, breaches, "APPROVED", role,
                    f"breached {'+'.join(breaches)} within hard limits")