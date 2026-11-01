
import copy
from datetime import timedelta

from src.ids import plan_id


ANOMALY_UNAPPROVED_INVENTORY = "UNAPPROVED_CHANGE_UPDATES_INVENTORY"
ANOMALY_WRONG_PO_LINE = "ACK_POINTS_TO_WRONG_PO_LINE"
ANOMALY_INVALID_PROMISE_DATE = "PROMISED_DATE_BEFORE_ORDER_DATE"
ANOMALY_OLDER_REVISION_OVERWRITES_NEWER = (
    "OLDER_REVISION_OVERWRITES_NEWER"
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def inject_anomalies(
    pos: list[dict],
    lines: list[dict],
    acks: list[dict],
    promises: list[dict],
    changes: list[dict],
    plans: list[dict],
) -> dict:

    anomalous_acks = copy.deepcopy(acks)
    anomalous_promises = copy.deepcopy(promises)
    anomalous_changes = copy.deepcopy(changes)
    anomalous_plans = copy.deepcopy(plans)

    ground_truth = []

    po_by_id = {p["po_id"]: p for p in pos}

    plan_by_change = {
        p["source_change_id"]: p
        for p in anomalous_plans
        if p["source_change_id"] is not None
    }

    # --------------------------------------------------
    # ANOMALY 1: Unapproved change updates inventory
    # --------------------------------------------------

    candidates = [
        c for c in anomalous_changes
        if c["status"] in ("REJECTED", "PENDING_APPROVAL")
    ]

    _require(
        bool(candidates),
        "No rejected or pending change available for anomaly 1."
    )

    change = candidates[0]
    line_id_value = change["po_line_id"]

    baseline_rows = [
        p for p in anomalous_plans
        if p["po_line_id"] == line_id_value
        and p["update_type"] == "BASELINE"
    ]

    _require(bool(baseline_rows), "Baseline plan not found.")

    baseline = baseline_rows[0]

    existing = [
        p for p in anomalous_plans
        if p["po_line_id"] == line_id_value
    ]

    latest = max(existing, key=lambda p: p["plan_version"])

    version = max(p["plan_version"] for p in existing) + 1

    effective_date = max(
        change["created_date"],
        latest["effective_from"],
    )

    latest["effective_to"] = effective_date

    bad_plan = copy.deepcopy(baseline)

    bad_plan.update({
        "plan_id": plan_id(line_id_value, version),
        "plan_version": version,
        "update_type": "CHANGE_APPLIED",
        "source_change_id": change["change_id"],
        "expected_qty": change["proposed_qty"],
        "expected_date": (
            change["proposed_date"] or change["requested_date"]
        ),
        "effective_from": effective_date,
        "effective_to": None,
    })

    anomalous_plans.append(bad_plan)

    ground_truth.append({
        "anomaly_id": "ANOM-001",
        "anomaly_type": ANOMALY_UNAPPROVED_INVENTORY,
        "entity_type": "inventory_plan",
        "record_id": bad_plan["plan_id"],
        "related_record_id": change["change_id"],
        "description": (
            "Inventory updated from a rejected or pending change."
        ),
    })

    # --------------------------------------------------
    # ANOMALY 2: ACK points to wrong PO line
    # --------------------------------------------------

    _require(
        len(anomalous_acks) > 0 and len(lines) > 1,
        "Insufficient ACK or PO line records for anomaly 2."
    )

    ack = anomalous_acks[0]

    wrong_line = next(
        (
            line for line in lines
            if line["po_line_id"] != ack["po_line_id"]
            and line["po_id"] != ack["po_id"]
        ),
        None,
    )

    _require(wrong_line is not None, "Different PO line not found.")

    ack["po_line_id"] = wrong_line["po_line_id"]

    ground_truth.append({
        "anomaly_id": "ANOM-002",
        "anomaly_type": ANOMALY_WRONG_PO_LINE,
        "entity_type": "acknowledgement",
        "record_id": ack["ack_id"],
        "related_record_id": wrong_line["po_line_id"],
        "description": (
            "ACK references a PO line belonging to another PO."
        ),
    })

    # --------------------------------------------------
    # ANOMALY 3: Promised date before order date
    # --------------------------------------------------

    _require(
        bool(anomalous_promises),
        "No promise records available for anomaly 3."
    )

    promise = anomalous_promises[0]

    ack_for_promise = next(
        (
            a for a in anomalous_acks
            if a["ack_id"] == promise["ack_id"]
        ),
        None,
    )

    _require(
        ack_for_promise is not None,
        "Promise acknowledgement not found."
    )

    po = po_by_id.get(ack_for_promise["po_id"])

    _require(po is not None, "Promise purchase order not found.")

    promise["promised_date"] = (
        po["order_date"] - timedelta(days=1)
    )

    ground_truth.append({
        "anomaly_id": "ANOM-003",
        "anomaly_type": ANOMALY_INVALID_PROMISE_DATE,
        "entity_type": "promise",
        "record_id": promise["promise_id"],
        "related_record_id": ack_for_promise["po_id"],
        "description": (
            "Promised date is earlier than the PO order date."
        ),
    })

    # --------------------------------------------------
    # ANOMALY 4: Older revision overwrites newer revision
    # --------------------------------------------------

    revision_groups = {}

    for change in anomalous_changes:
        if change["change_id"] not in plan_by_change:
            continue

        revision_groups.setdefault(
            change["po_line_id"], []
        ).append(change)

    revision_pair = None

    for group in revision_groups.values():

        group.sort(key=lambda c: c["revision_no"])

        for older, newer in zip(group, group[1:]):

            if older["revision_no"] < newer["revision_no"]:
                revision_pair = (older, newer)
                break

        if revision_pair is not None:
            break

    _require(
        revision_pair is not None,
        "Two applied revisions for the same PO line are required "
        "for anomaly 4."
    )

    older_change, newer_change = revision_pair

    older_plan = plan_by_change[older_change["change_id"]]
    newer_plan = plan_by_change[newer_change["change_id"]]

    older_date = older_plan["effective_from"]
    newer_date = newer_plan["effective_from"]

    older_plan["effective_from"] = newer_date
    newer_plan["effective_from"] = older_date

    same_line_plans = [
        p for p in anomalous_plans
        if p["po_line_id"] == older_change["po_line_id"]
    ]

    same_line_plans.sort(key=lambda p: p["plan_version"])

    for index, plan in enumerate(same_line_plans):

        if index + 1 < len(same_line_plans):
            plan["effective_to"] = (
                same_line_plans[index + 1]["effective_from"]
            )
        else:
            plan["effective_to"] = None

    ground_truth.append({
        "anomaly_id": "ANOM-004",
        "anomaly_type": ANOMALY_OLDER_REVISION_OVERWRITES_NEWER,
        "entity_type": "inventory_plan",
        "record_id": older_plan["plan_id"],
        "related_record_id": newer_plan["plan_id"],
        "description": (
            f"Revision {older_change['revision_no']} takes effect "
            f"after revision {newer_change['revision_no']}."
        ),
    })

    # --------------------------------------------------
    # Return all anomalous datasets
    # --------------------------------------------------

    return {
        "acks": anomalous_acks,
        "promises": anomalous_promises,
        "changes": anomalous_changes,
        "plans": anomalous_plans,
        "ground_truth": ground_truth,
    }