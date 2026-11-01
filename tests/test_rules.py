from src.rules import evaluate


def test_exactly_at_threshold_is_auto_approved():
    d = evaluate(5.0, 10.0, 7, accepted_qty=450)
    assert d.outcome == "AUTO_APPROVED" and not d.needs_approval

def test_just_over_threshold_needs_approval():
    assert evaluate(5.01, 0.0, 0, accepted_qty=500).needs_approval

def test_single_breach_goes_to_planner():
    d = evaluate(0.0, 0.0, 10, accepted_qty=500)
    assert (d.outcome, d.approver_role) == ("APPROVED", "PLANNER")

def test_two_breaches_go_to_manager():
    d = evaluate(6.0, 0.0, 10, accepted_qty=500)
    assert d.approver_role == "OPS_MANAGER" and d.breaches == ("PRICE", "DATE")

def test_over_hard_limit_is_rejected():
    assert evaluate(0.0, 0.0, 22, accepted_qty=500).outcome == "REJECTED"

def test_declined_line_is_approved_by_manager():
    d = evaluate(0.0, 100.0, 0, accepted_qty=0)
    assert (d.outcome, d.approver_role) == ("APPROVED", "OPS_MANAGER")