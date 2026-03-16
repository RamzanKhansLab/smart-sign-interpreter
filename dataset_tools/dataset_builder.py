from __future__ import annotations

import csv
from pathlib import Path

FEATURE_COLUMNS = ["thumb", "index", "middle", "ring", "little"]
HEADER = FEATURE_COLUMNS + ["gesture"]


def ensure_dataset(dataset_path: Path) -> None:
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    if not dataset_path.exists():
        with dataset_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER)
            writer.writeheader()


def append_row(dataset_path: str | Path, row: dict) -> None:
    dataset_path = Path(dataset_path)
    ensure_dataset(dataset_path)

    with dataset_path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER)
        writer.writerow({key: row.get(key) for key in HEADER})


def build_from_raw(raw_path: str | Path, gesture: str, dataset_path: str | Path) -> int:
    raw_path = Path(raw_path)
    dataset_path = Path(dataset_path)
    ensure_dataset(dataset_path)

    if not raw_path.exists():
        raise FileNotFoundError(f"Raw data not found: {raw_path}")

    count = 0
    with raw_path.open("r", newline="") as handle, dataset_path.open(
        "a", newline=""
    ) as out_handle:
        reader = csv.reader(handle)
        writer = csv.DictWriter(out_handle, fieldnames=HEADER)
        for row in reader:
            if not row:
                continue
            if len(row) < len(FEATURE_COLUMNS):
                continue
            values = row[: len(FEATURE_COLUMNS)]
            data = dict(zip(FEATURE_COLUMNS, values))
            data["gesture"] = gesture
            writer.writerow(data)
            count += 1

    return count
