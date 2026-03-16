from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from .train_model import train_and_save


def compute_hash(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def retrain_if_needed(
    dataset_path: Path,
    model_path: Path,
    hash_path: Path,
    model_type: str,
    test_size: float,
    random_state: int,
    force: bool,
):
    dataset_hash = compute_hash(dataset_path)
    if not force and hash_path.is_file():
        existing = hash_path.read_text().strip()
        if existing == dataset_hash:
            return False, None

    metrics = train_and_save(
        dataset_path=str(dataset_path),
        model_path=str(model_path),
        model_type=model_type,
        test_size=test_size,
        random_state=random_state,
    )
    hash_path.write_text(dataset_hash)
    return True, metrics


def main():
    base_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Retrain model when dataset changes.")
    parser.add_argument(
        "--dataset",
        default=str(base_dir / "data" / "dataset.csv"),
        help="Path to dataset CSV",
    )
    parser.add_argument(
        "--model-path",
        default=str(base_dir / "models" / "gesture_model.pkl"),
        help="Path to model output",
    )
    parser.add_argument(
        "--hash-path",
        default=str(base_dir / "models" / "dataset.sha256"),
        help="Where to store dataset hash",
    )
    parser.add_argument(
        "--model-type",
        default="knn",
        choices=["knn", "decision_tree", "random_forest"],
    )
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--force", action="store_true")

    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    model_path = Path(args.model_path)
    hash_path = Path(args.hash_path)

    retrained, metrics = retrain_if_needed(
        dataset_path=dataset_path,
        model_path=model_path,
        hash_path=hash_path,
        model_type=args.model_type,
        test_size=args.test_size,
        random_state=args.random_state,
        force=args.force,
    )

    if not retrained:
        print("Dataset unchanged. Skipping retrain.")
        return

    print(f"Model saved to {metrics['model_path']}")
    print(f"Accuracy: {metrics['accuracy']:.4f}")


if __name__ == "__main__":
    main()
