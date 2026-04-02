from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from dataset_tools.dataset_builder import build_from_raw


def main():
    parser = argparse.ArgumentParser(description="Label raw gesture data.")
    parser.add_argument("--input", required=True, help="Path to raw CSV file")
    parser.add_argument("--gesture", required=True, help="Gesture label")
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "datasets" / "gesture_dataset.csv"),
        help="Output dataset CSV",
    )

    args = parser.parse_args()
    count = build_from_raw(args.input, args.gesture, args.output)
    print(f"Labeled {count} rows to {args.output}")


if __name__ == "__main__":
    main()
