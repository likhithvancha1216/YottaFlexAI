from src.ids import (
    po_id,
    ack_id,
    chg_id,
    apr_id,
    not_id,
    supplier_id,
    line_id,
    promise_id,
    plan_id,
    prod_id,
)


def test_primary_entity_ids():
    assert po_id(1) == "PO-2026-000001"
    assert supplier_id(1) == "SUP-0001"
    assert not_id(5) == "NOT-2026-000005"
    assert prod_id(12) == "PRD-2026-000012"


def test_related_entity_ids():
    po = "PO-2026-000001"
    line = "PO-2026-000001-L01"
    change = "CHG-PO-2026-000001-000001"

    assert ack_id(po, 1) == "ACK-PO-2026-000001-01"
    assert chg_id(po, 1) == change
    assert apr_id(change, 2) == "APR-CHG-PO-2026-000001-000001-02"
    assert line_id(po, 1) == line
    assert promise_id(line, 1) == "PRM-PO-2026-000001-L01-01"
    assert plan_id(line, 2) == "INV-PO-2026-000001-L01-02"


def test_custom_year_in_ids():
    assert po_id(25, year=2030) == "PO-2030-000025"
    assert not_id(8, year=2031) == "NOT-2031-000008"
    assert prod_id(9, year=2032) == "PRD-2032-000009"
