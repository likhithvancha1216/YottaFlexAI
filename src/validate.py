
"""Validate the CSV datasets exported by the supplier acknowledgement generator.

Run from the project root:
    python -m src.validate

Optional:
    python -m src.validate --input-dir output
"""

import argparse
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path


EXPECTED_COLUMNS = {
    "suppliers": [
        "supplier_id", "supplier_name", "country",
        "standard_lead_time_days", "reliability_score", "status",
    ],
    "purchase_orders": [
        "po_id", "supplier_id", "planner_id", "order_date",
        "currency", "status", "total_amount",
    ],
    "po_lines": [
        "po_line_id", "po_id", "line_number", "item_code",
        "item_description", "uom", "ordered_qty", "unit_price",
        "line_total", "requested_date", "status",
    ],
    "acknowledgements": [
        "ack_id", "po_id", "po_line_id", "revision_no",
        "ack_date", "accepted_qty", "rejected_qty",
        "confirmed_unit_price", "ack_status",
    ],
    "promises": [
        "promise_id", "po_line_id", "ack_id", "revision_no",
        "promised_date", "effective_from",
    ],
    "changes": [
        "change_id", "po_id", "po_line_id", "ack_id",
        "promise_id", "revision_no", "change_types",
        "requested_unit_price", "proposed_unit_price",
        "price_delta_pct", "requested_qty", "proposed_qty",
        "qty_shortfall_pct", "requested_date", "proposed_date",
        "date_slip_days", "breached_rules", "approval_required",
        "supersedes_change_id", "created_date", "status",
    ],
    "approvals": [
        "approval_id", "change_id", "approval_seq",
        "approver_role", "approver_id", "decision",
        "decision_date", "reason",
    ],
    "inventory_plan": [
        "plan_id", "po_line_id", "item_code", "plan_version",
        "update_type", "source_change_id", "expected_qty",
        "expected_date", "effective_from", "effective_to",
    ],
    "production_orders": [
        "production_order_id", "product_name", "planner_id",
        "quantity_to_build", "need_date", "created_date", "status",
    ],
    "production_order_po_line": [
        "production_order_id", "po_line_id", "allocated_qty",
    ],
    "notifications": [
        "notification_id", "change_id", "plan_id", "po_line_id",
        "production_order_id", "recipient_planner_id", "impact_type",
        "days_late", "shortfall_qty", "severity", "created_date",
        "message", "status",
    ],
    "ground_truth": [
        "anomaly_id", "anomaly_type", "entity_type",
        "record_id", "related_record_id", "description",
    ],
}

PRIMARY_KEYS = {
    "suppliers": "supplier_id",
    "purchase_orders": "po_id",
    "po_lines": "po_line_id",
    "acknowledgements": "ack_id",
    "promises": "promise_id",
    "changes": "change_id",
    "approvals": "approval_id",
    "inventory_plan": "plan_id",
    "production_orders": "production_order_id",
    "notifications": "notification_id",
    "ground_truth": "anomaly_id",
}

EXPECTED_ANOMALIES = {
    "UNAPPROVED_CHANGE_UPDATES_INVENTORY",
    "ACK_POINTS_TO_WRONG_PO_LINE",
    "PROMISED_DATE_BEFORE_ORDER_DATE",
    "OLDER_REVISION_OVERWRITES_NEWER",
}

APPLIED_STATUSES = {"AUTO_APPROVED", "APPROVED"}


class ValidationReport:
    """Collect validation errors and warnings."""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.checks_passed = 0

    def passed(self):
        self.checks_passed += 1

    def error(self, message):
        self.errors.append(message)

    def warning(self, message):
        self.warnings.append(message)

    def print_summary(self):
        print("\n" + "=" * 65)
        print("DATA VALIDATION SUMMARY")
        print("=" * 65)
        print(f"Checks passed : {self.checks_passed}")
        print(f"Errors        : {len(self.errors)}")
        print(f"Warnings      : {len(self.warnings)}")

        if self.errors:
            print("\nVALIDATION ERRORS")
            for number, message in enumerate(self.errors, start=1):
                print(f"{number}. {message}")

        if self.warnings:
            print("\nWARNINGS")
            for number, message in enumerate(self.warnings, start=1):
                print(f"{number}. {message}")

        if not self.errors:
            print("\nResult: VALIDATION PASSED")
        else:
            print("\nResult: VALIDATION FAILED")

        print("=" * 65)


def read_csv_file(path):
    """Read a CSV file and return its rows as dictionaries."""

    with path.open(
        mode="r",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        reader = csv.DictReader(csv_file)

        if reader.fieldnames is None:
            return [], []

        rows = list(reader)
        return reader.fieldnames, rows


def parse_date(value):
    """Convert an ISO date string into a date object."""

    if value is None or value == "":
        return None

    return date.fromisoformat(value[:10])


def parse_number(value, field_name):
    """Convert a CSV value into a float."""

    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"Expected a numeric value for '{field_name}', got {value!r}"
        )


def parse_integer(value, field_name):
    """Convert a CSV value into an integer."""

    number = parse_number(value, field_name)

    if not number.is_integer():
        raise ValueError(
            f"Expected an integer for '{field_name}', got {value!r}"
        )

    return int(number)


def load_datasets(input_dir, report):
    """Load all expected CSV datasets and check their columns."""

    datasets = {}

    for dataset_name, expected_columns in EXPECTED_COLUMNS.items():
        path = input_dir / f"{dataset_name}.csv"

        if not path.exists():
            report.error(f"Missing dataset file: {path}")
            datasets[dataset_name] = []
            continue

        try:
            actual_columns, rows = read_csv_file(path)
        except (OSError, csv.Error, UnicodeError) as exc:
            report.error(
                f"Could not read {path.name}: {exc}"
            )
            datasets[dataset_name] = []
            continue

        if actual_columns != expected_columns:
            report.error(
                f"{path.name} has an unexpected column structure. "
                f"Expected: {expected_columns}; found: {actual_columns}"
            )
        else:
            report.passed()

        datasets[dataset_name] = rows
        print(f"Loaded {path.name}: {len(rows):,} rows")

    return datasets


def check_primary_keys(datasets, report):
    """Check that primary-key fields are present and unique."""

    for dataset_name, key_name in PRIMARY_KEYS.items():
        rows = datasets.get(dataset_name, [])
        seen = set()

        for row_number, row in enumerate(rows, start=2):
            value = row.get(key_name, "")

            if not value:
                report.error(
                    f"{dataset_name}.csv row {row_number}: "
                    f"missing {key_name}"
                )
                continue

            if value in seen:
                report.error(
                    f"{dataset_name}.csv: duplicate {key_name}={value}"
                )
            else:
                seen.add(value)

        if rows:
            report.passed()


def check_foreign_keys(datasets, report):
    """Check that references point to records in the parent datasets."""

    suppliers = {
        row["supplier_id"] for row in datasets["suppliers"]
    }
    pos = {
        row["po_id"] for row in datasets["purchase_orders"]
    }
    lines = {
        row["po_line_id"]: row for row in datasets["po_lines"]
    }
    acks = {
        row["ack_id"]: row for row in datasets["acknowledgements"]
    }
    promises = {
        row["promise_id"] for row in datasets["promises"]
    }
    changes = {
        row["change_id"] for row in datasets["changes"]
    }
    plans = {
        row["plan_id"] for row in datasets["inventory_plan"]
    }
    production_orders = {
        row["production_order_id"]: row
        for row in datasets["production_orders"]
    }

    # Supplier -> Purchase Order
    for row in datasets["purchase_orders"]:
        if row["supplier_id"] not in suppliers:
            report.error(
                f"PO {row['po_id']} references missing supplier "
                f"{row['supplier_id']}"
            )

    # Purchase Order -> PO Line
    for row in datasets["po_lines"]:
        if row["po_id"] not in pos:
            report.error(
                f"PO line {row['po_line_id']} references missing PO "
                f"{row['po_id']}"
            )

    # Acknowledgement -> PO and PO Line
    for row in datasets["acknowledgements"]:
        if row["po_id"] not in pos:
            report.error(
                f"ACK {row['ack_id']} references missing PO {row['po_id']}"
            )

        if row["po_line_id"] not in lines:
            report.error(
                f"ACK {row['ack_id']} references missing PO line "
                f"{row['po_line_id']}"
            )

    # Promise -> PO Line and Acknowledgement
    for row in datasets["promises"]:
        if row["po_line_id"] not in lines:
            report.error(
                f"Promise {row['promise_id']} references missing PO line "
                f"{row['po_line_id']}"
            )

        if row["ack_id"] not in acks:
            report.error(
                f"Promise {row['promise_id']} references missing ACK "
                f"{row['ack_id']}"
            )

    # Change -> PO, PO Line, ACK, optional Promise and optional predecessor
    for row in datasets["changes"]:
        if row["po_id"] not in pos:
            report.error(
                f"Change {row['change_id']} references missing PO "
                f"{row['po_id']}"
            )

        if row["po_line_id"] not in lines:
            report.error(
                f"Change {row['change_id']} references missing PO line "
                f"{row['po_line_id']}"
            )

        if row["ack_id"] not in acks:
            report.error(
                f"Change {row['change_id']} references missing ACK "
                f"{row['ack_id']}"
            )

        if row["promise_id"] and row["promise_id"] not in promises:
            report.error(
                f"Change {row['change_id']} references missing Promise "
                f"{row['promise_id']}"
            )

    # Approval -> Change
    for row in datasets["approvals"]:
        if row["change_id"] not in changes:
            report.error(
                f"Approval {row['approval_id']} references missing change "
                f"{row['change_id']}"
            )

    # Inventory Plan -> PO Line and optional Change
    for row in datasets["inventory_plan"]:
        if row["po_line_id"] not in lines:
            report.error(
                f"Plan {row['plan_id']} references missing PO line "
                f"{row['po_line_id']}"
            )

        if (
            row["source_change_id"]
            and row["source_change_id"] not in changes
        ):
            report.error(
                f"Plan {row['plan_id']} references missing change "
                f"{row['source_change_id']}"
            )

    # Production Order bridge -> Production Order and PO Line
    for row in datasets["production_order_po_line"]:
        if row["production_order_id"] not in production_orders:
            report.error(
                "Production-order bridge references missing production order "
                f"{row['production_order_id']}"
            )

        if row["po_line_id"] not in lines:
            report.error(
                "Production-order bridge references missing PO line "
                f"{row['po_line_id']}"
            )

    # Notification -> Change, Plan, PO Line and Production Order
    for row in datasets["notifications"]:
        if row["change_id"] not in changes:
            report.error(
                f"Notification {row['notification_id']} references "
                f"missing change {row['change_id']}"
            )

        if row["plan_id"] not in plans:
            report.error(
                f"Notification {row['notification_id']} references "
                f"missing plan {row['plan_id']}"
            )

        if row["po_line_id"] not in lines:
            report.error(
                f"Notification {row['notification_id']} references "
                f"missing PO line {row['po_line_id']}"
            )

        if row["production_order_id"] not in production_orders:
            report.error(
                f"Notification {row['notification_id']} references "
                "missing production order "
                f"{row['production_order_id']}"
            )

    report.passed()


def check_acknowledgement_line_consistency(datasets, report):
    """Check that an acknowledgement's PO matches its referenced PO line."""

    lines = {
        row["po_line_id"]: row for row in datasets["po_lines"]
    }

    anomaly_ids = {
        row["record_id"]
        for row in datasets["ground_truth"]
        if row["anomaly_type"] == "ACK_POINTS_TO_WRONG_PO_LINE"
    }

    for row in datasets["acknowledgements"]:
        if row["ack_id"] in anomaly_ids:
            continue

        line = lines.get(row["po_line_id"])

        if line and line["po_id"] != row["po_id"]:
            report.error(
                f"ACK {row['ack_id']} has PO {row['po_id']} but its "
                f"PO line belongs to {line['po_id']}"
            )

    report.passed()


def check_approval_consistency(datasets, report):
    """Check that change statuses agree with approval records."""

    approvals_by_change = defaultdict(list)

    for approval in datasets["approvals"]:
        approvals_by_change[approval["change_id"]].append(approval)

    for change in datasets["changes"]:
        change_id = change["change_id"]
        status = change["status"]
        approval_rows = approvals_by_change.get(change_id, [])

        if status == "PENDING_APPROVAL":
            if approval_rows:
                report.error(
                    f"Pending change {change_id} unexpectedly has "
                    "an approval record"
                )
            continue

        if len(approval_rows) != 1:
            report.error(
                f"Decided change {change_id} should have exactly one "
                f"approval record; found {len(approval_rows)}"
            )
            continue

        if approval_rows[0]["decision"] != status:
            report.error(
                f"Change {change_id} status {status} does not match "
                f"approval decision {approval_rows[0]['decision']}"
            )

    report.passed()


def check_change_supersede_chains(datasets, report):
    """Check that superseded changes belong to the same line and are older."""

    changes_by_id = {
        row["change_id"]: row for row in datasets["changes"]
    }

    for change in datasets["changes"]:
        previous_id = change["supersedes_change_id"]

        if not previous_id:
            continue

        previous = changes_by_id.get(previous_id)

        if previous is None:
            report.error(
                f"Change {change['change_id']} supersedes missing change "
                f"{previous_id}"
            )
            continue

        if previous["po_line_id"] != change["po_line_id"]:
            report.error(
                f"Change {change['change_id']} supersedes a change "
                "from a different PO line"
            )

        try:
            old_revision = parse_integer(
                previous["revision_no"], "revision_no"
            )
            new_revision = parse_integer(
                change["revision_no"], "revision_no"
            )
        except ValueError as exc:
            report.error(str(exc))
            continue

        if old_revision >= new_revision:
            report.error(
                f"Change {change['change_id']} does not have a newer "
                "revision than its predecessor"
            )

    report.passed()


def check_inventory_plans(datasets, report):
    """Check plan versions, intervals and approved-change sourcing."""

    changes_by_id = {
        row["change_id"]: row for row in datasets["changes"]
    }

    anomaly_types = {
        "UNAPPROVED_CHANGE_UPDATES_INVENTORY",
        "OLDER_REVISION_OVERWRITES_NEWER",
    }

    anomaly_ids = set()
    anomaly_related_ids = set()

    for anomaly in datasets["ground_truth"]:
        if anomaly["anomaly_type"] in anomaly_types:
            anomaly_ids.add(anomaly["record_id"])
            if anomaly["related_record_id"]:
                anomaly_related_ids.add(anomaly["related_record_id"])

    plans_by_line = defaultdict(list)

    for plan in datasets["inventory_plan"]:
        plans_by_line[plan["po_line_id"]].append(plan)

        source_change_id = plan["source_change_id"]

        if source_change_id:
            source_change = changes_by_id.get(source_change_id)

            if (
                source_change
                and source_change["status"] not in APPLIED_STATUSES
                and plan["plan_id"] not in anomaly_ids
                and source_change_id not in anomaly_ids
                and plan["po_line_id"] not in anomaly_related_ids
            ):
                report.error(
                    f"Plan {plan['plan_id']} is sourced from "
                    f"unapproved change {source_change_id}"
                )

    for line_id, rows in plans_by_line.items():
        rows.sort(
            key=lambda row: parse_integer(
                row["plan_version"], "plan_version"
            )
        )

        # Skip the version-order checks for a line explicitly labelled
        # with the older-revision-overwrites-newer anomaly.
        if line_id in anomaly_related_ids or any(
            row["plan_id"] in anomaly_ids for row in rows
        ):
            continue

        versions = []

        for row in rows:
            try:
                versions.append(
                    parse_integer(row["plan_version"], "plan_version")
                )
            except ValueError as exc:
                report.error(str(exc))

        if versions and versions != list(range(1, len(versions) + 1)):
            report.error(
                f"PO line {line_id} has non-contiguous plan versions: "
                f"{versions}"
            )

        if rows and rows[0]["update_type"] != "BASELINE":
            report.error(
                f"PO line {line_id} does not start with a BASELINE plan"
            )

        for previous, current in zip(rows, rows[1:]):
            if previous["effective_to"] != current["effective_from"]:
                report.error(
                    f"PO line {line_id} has a gap or overlap between "
                    f"plan versions {previous['plan_version']} and "
                    f"{current['plan_version']}"
                )

        if rows and rows[-1]["effective_to"]:
            report.error(
                f"Latest plan version for PO line {line_id} "
                "should have an empty effective_to"
            )

    report.passed()


def check_allocation_limits(datasets, report):
    """Ensure production allocations do not exceed ordered quantities."""

    ordered_quantities = {}

    for line in datasets["po_lines"]:
        try:
            ordered_quantities[line["po_line_id"]] = parse_integer(
                line["ordered_qty"], "ordered_qty"
            )
        except ValueError as exc:
            report.error(str(exc))

    allocated_quantities = defaultdict(int)

    for bridge in datasets["production_order_po_line"]:
        try:
            allocated = parse_integer(
                bridge["allocated_qty"], "allocated_qty"
            )
        except ValueError as exc:
            report.error(str(exc))
            continue

        if allocated <= 0:
            report.error(
                f"Allocation for PO line {bridge['po_line_id']} "
                "must be positive"
            )

        allocated_quantities[bridge["po_line_id"]] += allocated

    for line_id, allocated in allocated_quantities.items():
        ordered = ordered_quantities.get(line_id)

        if ordered is not None and allocated > ordered:
            report.error(
                f"PO line {line_id} has allocated quantity {allocated}, "
                f"greater than ordered quantity {ordered}"
            )

    report.passed()


def check_notification_consistency(datasets, report):
    """Check notification recipients and impact values."""

    production_orders = {
        row["production_order_id"]: row
        for row in datasets["production_orders"]
    }

    for notification in datasets["notifications"]:
        production_order = production_orders.get(
            notification["production_order_id"]
        )

        if production_order is None:
            continue

        if (
            notification["recipient_planner_id"]
            != production_order["planner_id"]
        ):
            report.error(
                f"Notification {notification['notification_id']} "
                "is assigned to the wrong planner"
            )

        try:
            days_late = parse_integer(
                notification["days_late"], "days_late"
            )
            shortfall = parse_integer(
                notification["shortfall_qty"], "shortfall_qty"
            )
        except ValueError as exc:
            report.error(str(exc))
            continue

        if days_late < 0 or shortfall < 0:
            report.error(
                f"Notification {notification['notification_id']} "
                "contains a negative impact value"
            )

        if days_late == 0 and shortfall == 0:
            report.error(
                f"Notification {notification['notification_id']} "
                "has no delay or quantity shortfall"
            )

    report.passed()


def check_numeric_and_date_values(datasets, report):
    """Check important numeric and date fields for valid values."""

    numeric_fields = {
        "suppliers": [
            "standard_lead_time_days", "reliability_score",
        ],
        "purchase_orders": ["total_amount"],
        "po_lines": [
            "line_number", "ordered_qty", "unit_price", "line_total",
        ],
        "acknowledgements": [
            "revision_no", "accepted_qty", "rejected_qty",
            "confirmed_unit_price",
        ],
        "promises": ["revision_no"],
        "changes": [
            "revision_no", "requested_unit_price",
            "proposed_unit_price", "price_delta_pct",
            "requested_qty", "proposed_qty",
            "qty_shortfall_pct", "date_slip_days",
        ],
        "approvals": ["approval_seq"],
        "inventory_plan": ["plan_version", "expected_qty"],
        "production_orders": ["quantity_to_build"],
        "production_order_po_line": ["allocated_qty"],
        "notifications": ["days_late", "shortfall_qty"],
    }

    date_fields = {
        "purchase_orders": ["order_date"],
        "po_lines": ["requested_date"],
        "acknowledgements": ["ack_date"],
        "promises": ["promised_date", "effective_from"],
        "changes": ["requested_date", "proposed_date", "created_date"],
        "approvals": ["decision_date"],
        "inventory_plan": [
            "expected_date", "effective_from", "effective_to",
        ],
        "production_orders": ["need_date", "created_date"],
        "notifications": ["created_date"],
    }

    for dataset_name, fields in numeric_fields.items():
        for row_number, row in enumerate(
            datasets[dataset_name], start=2
        ):
            for field in fields:
                value = row.get(field, "")

                if value == "":
                    continue

                try:
                    parse_number(value, field)
                except ValueError as exc:
                    report.error(
                        f"{dataset_name}.csv row {row_number}: {exc}"
                    )

    for dataset_name, fields in date_fields.items():
        for row_number, row in enumerate(
            datasets[dataset_name], start=2
        ):
            for field in fields:
                value = row.get(field, "")

                if value == "":
                    continue

                try:
                    parse_date(value)
                except (ValueError, TypeError):
                    report.error(
                        f"{dataset_name}.csv row {row_number}: "
                        f"invalid date in {field}: {value!r}"
                    )

    report.passed()


def check_ground_truth(datasets, report):
    """Confirm that the four required anomaly labels are present."""

    ground_truth = datasets["ground_truth"]

    found_types = {
        row["anomaly_type"] for row in ground_truth
    }

    missing_types = EXPECTED_ANOMALIES - found_types
    unexpected_types = found_types - EXPECTED_ANOMALIES

    if missing_types:
        report.error(
            "Missing required anomaly types: "
            + ", ".join(sorted(missing_types))
        )

    if unexpected_types:
        report.warning(
            "Additional anomaly types found: "
            + ", ".join(sorted(unexpected_types))
        )

    if len(ground_truth) != 4:
        report.warning(
            f"Expected 4 ground-truth rows for the four injected anomalies; "
            f"found {len(ground_truth)}"
        )

    if not missing_types:
        report.passed()


def print_dataset_counts(datasets):
    """Print a compact row-count report."""

    print("\nDATASET ROW COUNTS")
    print("-" * 45)

    for name in EXPECTED_COLUMNS:
        print(f"{name:30} {len(datasets.get(name, [])):>10,}")


def validate(input_dir):
    """Run all validation checks against the exported datasets."""

    report = ValidationReport()
    input_dir = Path(input_dir)

    print("=" * 65)
    print("SUPPLIER ACKNOWLEDGEMENT DATA VALIDATOR")
    print("=" * 65)
    print(f"Input directory: {input_dir.resolve()}\n")

    if not input_dir.exists():
        report.error(f"Input directory does not exist: {input_dir}")
        report.print_summary()
        return False

    datasets = load_datasets(input_dir, report)

    print_dataset_counts(datasets)

    check_primary_keys(datasets, report)
    check_foreign_keys(datasets, report)
    check_acknowledgement_line_consistency(datasets, report)
    check_approval_consistency(datasets, report)
    check_change_supersede_chains(datasets, report)
    check_inventory_plans(datasets, report)
    check_allocation_limits(datasets, report)
    check_notification_consistency(datasets, report)
    check_numeric_and_date_values(datasets, report)
    check_ground_truth(datasets, report)

    report.print_summary()
    return len(report.errors) == 0


def main():
    parser = argparse.ArgumentParser(
        description="Validate supplier acknowledgement CSV datasets."
    )
    parser.add_argument(
        "--input-dir",
        default="output",
        help="Directory containing the exported CSV files.",
    )

    args = parser.parse_args()
    success = validate(args.input_dir)

    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()