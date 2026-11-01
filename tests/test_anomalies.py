
import random

from src.config import Config
from src.generators.suppliers import generate_suppliers
from src.generators.purchase_orders import generate_purchase_orders
from src.generators.acknowledgements import generate_acknowledgements
from src.generators.changes import generate_changes
from src.generators.downstream import generate_inventory_plan
from src.generators.anomalies import (
    inject_anomalies,
    ANOMALY_UNAPPROVED_INVENTORY,
    ANOMALY_WRONG_PO_LINE,
    ANOMALY_INVALID_PROMISE_DATE,
    ANOMALY_OLDER_REVISION_OVERWRITES_NEWER,
)


def build_anomalous_data(seed=20261022, n=1000):
    """Build normal project data and inject the four labelled anomalies."""

    cfg = Config(seed=seed, n_pos=n)
    rng = random.Random(seed)

    suppliers = generate_suppliers(cfg, rng)

    pos, lines = generate_purchase_orders(
        cfg, rng, suppliers
    )

    acks, promises = generate_acknowledgements(
        cfg, rng, suppliers, pos, lines
    )

    changes, approvals = generate_changes(
        cfg, rng, pos, lines, acks, promises
    )

    plans = generate_inventory_plan(
        pos, lines, changes, approvals
    )

    result = inject_anomalies(
        pos, lines, acks, promises, changes, plans
    )

    # Keep the original parent records available for validation.
    result["pos"] = pos
    result["lines"] = lines

    return result


def test_all_four_anomalies_are_labelled():
    data = build_anomalous_data()

    actual_types = {
        item["anomaly_type"]
        for item in data["ground_truth"]
    }

    expected_types = {
        ANOMALY_UNAPPROVED_INVENTORY,
        ANOMALY_WRONG_PO_LINE,
        ANOMALY_INVALID_PROMISE_DATE,
        ANOMALY_OLDER_REVISION_OVERWRITES_NEWER,
    }

    assert actual_types == expected_types
    assert len(data["ground_truth"]) == 4


def test_unapproved_change_updates_inventory_plan():
    data = build_anomalous_data()

    plans_by_id = {
        plan["plan_id"]: plan
        for plan in data["plans"]
    }

    changes_by_id = {
        change["change_id"]: change
        for change in data["changes"]
    }

    anomaly = next(
        item for item in data["ground_truth"]
        if item["anomaly_type"] == ANOMALY_UNAPPROVED_INVENTORY
    )

    bad_plan = plans_by_id[anomaly["record_id"]]

    related_change = changes_by_id[
        anomaly["related_record_id"]
    ]

    assert bad_plan["source_change_id"] == related_change["change_id"]

    assert related_change["status"] in (
        "REJECTED",
        "PENDING_APPROVAL",
    )


def test_acknowledgement_points_to_wrong_po_line():
    data = build_anomalous_data()

    acks_by_id = {
        ack["ack_id"]: ack
        for ack in data["acks"]
    }

    lines_by_id = {
        line["po_line_id"]: line
        for line in data["lines"]
    }

    anomaly = next(
        item for item in data["ground_truth"]
        if item["anomaly_type"] == ANOMALY_WRONG_PO_LINE
    )

    bad_ack = acks_by_id[anomaly["record_id"]]

    wrong_line = lines_by_id[bad_ack["po_line_id"]]

    # The referenced PO line must belong to a different PO.
    assert wrong_line["po_id"] != bad_ack["po_id"]


def test_promised_date_is_before_po_order_date():
    data = build_anomalous_data()

    promises_by_id = {
        promise["promise_id"]: promise
        for promise in data["promises"]
    }

    pos_by_id = {
        po["po_id"]: po
        for po in data["pos"]
    }

    anomaly = next(
        item for item in data["ground_truth"]
        if item["anomaly_type"] == ANOMALY_INVALID_PROMISE_DATE
    )

    bad_promise = promises_by_id[anomaly["record_id"]]

    related_po = pos_by_id[anomaly["related_record_id"]]

    assert bad_promise["promised_date"] < related_po["order_date"]


def test_older_revision_overwrites_newer_revision():
    data = build_anomalous_data()

    plans_by_id = {
        plan["plan_id"]: plan
        for plan in data["plans"]
    }

    changes_by_id = {
        change["change_id"]: change
        for change in data["changes"]
    }

    anomaly = next(
        item for item in data["ground_truth"]
        if item["anomaly_type"]
        == ANOMALY_OLDER_REVISION_OVERWRITES_NEWER
    )

    older_plan = plans_by_id[anomaly["record_id"]]

    newer_plan = plans_by_id[anomaly["related_record_id"]]

    older_change = changes_by_id[
        older_plan["source_change_id"]
    ]

    newer_change = changes_by_id[
        newer_plan["source_change_id"]
    ]

    # The older revision must have a lower revision number.
    assert older_change["revision_no"] < newer_change["revision_no"]

    # The injected anomaly makes the older revision effective later.
    assert older_plan["effective_from"] > newer_plan["effective_from"]