
import argparse
import random

from src.config import Config, SEED

from src.export import export_datasets

from src.generators.suppliers import generate_suppliers
from src.generators.purchase_orders import generate_purchase_orders
from src.generators.acknowledgements import generate_acknowledgements
from src.generators.changes import generate_changes

from src.generators.downstream import (
    generate_inventory_plan,
    generate_production_orders,
    generate_notifications,
)

from src.generators.anomalies import inject_anomalies


def main():
    parser = argparse.ArgumentParser(
        description="Generate supplier acknowledgement datasets."
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help="Random seed for reproducible data generation.",
    )

    parser.add_argument(
        "--n-pos",
        type=int,
        default=10_000,
        help="Number of purchase orders to generate.",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Directory where CSV files will be saved.",
    )

    args = parser.parse_args()

    # ---------------------------------------------------------
    # 1. Initialize configuration and random generator
    # ---------------------------------------------------------

    cfg = Config(
        seed=args.seed,
        n_pos=args.n_pos,
    )

    rng = random.Random(cfg.seed)

    print("\nStarting Supplier Acknowledgement Generator...")
    print(f"Seed: {cfg.seed}")
    print(f"Purchase orders requested: {cfg.n_pos}")

    # ---------------------------------------------------------
    # 2. Generate suppliers
    # ---------------------------------------------------------

    suppliers = generate_suppliers(cfg, rng)

    # ---------------------------------------------------------
    # 3. Generate purchase orders and PO lines
    # ---------------------------------------------------------

    pos, lines = generate_purchase_orders(
        cfg,
        rng,
        suppliers,
    )

    # ---------------------------------------------------------
    # 4. Generate acknowledgements and promises
    # ---------------------------------------------------------

    acks, promises = generate_acknowledgements(
        cfg,
        rng,
        suppliers,
        pos,
        lines,
    )

    # ---------------------------------------------------------
    # 5. Generate change requests and approvals
    # ---------------------------------------------------------

    changes, approvals = generate_changes(
        cfg,
        rng,
        pos,
        lines,
        acks,
        promises,
    )

    # ---------------------------------------------------------
    # 6. Generate normal inventory plans
    # ---------------------------------------------------------

    plans = generate_inventory_plan(
        pos,
        lines,
        changes,
        approvals,
    )

    # ---------------------------------------------------------
    # 7. Generate production orders and PO-line bridge
    # ---------------------------------------------------------

    production_orders, production_order_po_line = (
        generate_production_orders(
            cfg,
            rng,
            pos,
            lines,
        )
    )

    # ---------------------------------------------------------
    # 8. Generate notifications from the normal inventory plan
    # ---------------------------------------------------------

    notifications = generate_notifications(
        cfg,
        plans,
        production_orders,
        production_order_po_line,
    )

    # ---------------------------------------------------------
    # 9. Inject the four labelled anomalies
    # ---------------------------------------------------------

    anomaly_data = inject_anomalies(
        pos,
        lines,
        acks,
        promises,
        changes,
        plans,
    )

    # Use the anomaly-injected copies for final export.
    acks = anomaly_data["acks"]
    promises = anomaly_data["promises"]
    changes = anomaly_data["changes"]
    plans = anomaly_data["plans"]
    ground_truth = anomaly_data["ground_truth"]

    # ---------------------------------------------------------
    # 10. Collect all datasets for CSV export
    # ---------------------------------------------------------

    datasets = {
        "suppliers": suppliers,
        "purchase_orders": pos,
        "po_lines": lines,
        "acknowledgements": acks,
        "promises": promises,
        "changes": changes,
        "approvals": approvals,
        "inventory_plan": plans,
        "production_orders": production_orders,
        "production_order_po_line": production_order_po_line,
        "notifications": notifications,
        "ground_truth": ground_truth,
    }

    # ---------------------------------------------------------
    # 11. Export all datasets
    # ---------------------------------------------------------

    print("\nExporting generated datasets...")

    export_datasets(
        datasets,
        output_dir=args.output_dir,
    )

    # ---------------------------------------------------------
    # 12. Display final record counts
    # ---------------------------------------------------------

    print("\n========== GENERATION SUMMARY ==========")

    for dataset_name, records in datasets.items():
        print(f"{dataset_name}: {len(records)}")

    print("----------------------------------------")
    print(f"Total datasets: {len(datasets)}")
    print(f"Labelled anomalies: {len(ground_truth)}")
    print("Generation completed successfully.")
    print("========================================")


if __name__ == "__main__":
    main()