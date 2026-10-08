from __future__ import annotations

import argparse
from pathlib import Path

from app.services.ml_service import MODEL_REGISTRY, MLService


def build_model(model_type: str, random_state: int):
    model_type = model_type.lower()
    if model_type not in MODEL_REGISTRY:
        raise ValueError(f"Unsupported model type: {model_type}")
    return MODEL_REGISTRY[model_type](random_state)


def train_and_save(
    dataset_path: str = None,
    model_path: str = None,
    model_type: str = "knn",
    test_size: float = 0.2,
    random_state: int = 42,
    google_credentials_path: str = None,
    google_spreadsheet_id: str = None,
):
    """Share the web trainer's feature pipeline and persisted evaluation artifacts."""
    service = MLService(model_path, allow_missing=True)
    metrics = service.retrain(
        dataset_path=dataset_path,
        model_type=model_type,
        test_size=test_size,
        random_state=random_state,
        google_credentials_path=google_credentials_path,
        google_spreadsheet_id=google_spreadsheet_id,
    )
    # Preserve the command-line helper's existing structured report contract.
    return {**metrics, "report": metrics["classification_report"]}


def main():
    base_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Train a lightweight gesture classifier."
    )
    parser.add_argument(
        "--dataset",
        default=str(base_dir / "data" / "datasets" / "gesture_dataset.csv"),
        help="Path to dataset CSV",
    )
    parser.add_argument(
        "--model-path",
        default=str(base_dir / "models" / "gesture_model.pkl"),
        help="Output model path",
    )
    parser.add_argument(
        "--model-type",
        default="knn",
        choices=sorted(MODEL_REGISTRY.keys()),
        help="Model type",
    )
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)

    args = parser.parse_args()
    metrics = train_and_save(
        dataset_path=args.dataset,
        model_path=args.model_path,
        model_type=args.model_type,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    print(f"Model saved to {metrics['model_path']}")
    print(f"Accuracy: {metrics['accuracy']:.4f}")


if __name__ == "__main__":
    main()
