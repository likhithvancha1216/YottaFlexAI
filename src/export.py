
import csv
import json
from pathlib import Path
from typing import Any


def _serialize_value(value: Any) -> Any:
    """Convert Python values into CSV-compatible values."""

    if value is None:
        return ""

    if hasattr(value, "isoformat"):
        return value.isoformat()

    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, default=str)

    return value


def write_csv(file_path: Path, records: list[dict]) -> None:
    """Write a list of dictionaries to a CSV file."""

    if not records:
        file_path.write_text("", encoding="utf-8")
        return

    # Preserve column order based on the first appearance of each key.
    fieldnames = list(
        dict.fromkeys(
            key
            for record in records
            for key in record.keys()
        )
    )

    with file_path.open(
        mode="w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
            extrasaction="raise",
        )

        writer.writeheader()

        for record in records:
            serialized_record = {
                key: _serialize_value(value)
                for key, value in record.items()
            }
            writer.writerow(serialized_record)


def export_datasets(
    datasets: dict[str, list[dict]],
    output_dir: str | Path = "output",
) -> None:
    """Export all generated datasets into separate CSV files."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    for dataset_name, records in datasets.items():
        if not dataset_name.replace("_", "").isalnum():
            raise ValueError(
                f"Invalid dataset name: {dataset_name}"
            )

        file_path = destination / f"{dataset_name}.csv"

        write_csv(file_path, records)

        print(
            f"Exported {dataset_name}.csv "
            f"({len(records)} records)"
        )

    print(f"\nAll datasets exported to: {destination.resolve()}")