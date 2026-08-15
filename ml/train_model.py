from __future__ import annotations

import argparse
from collections import Counter
import math
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier

from .dataset_loader import load_dataset, load_dataset_from_google_sheets
from .evaluate_model import evaluate_model

MODEL_REGISTRY = {
    "knn": lambda random_state: KNeighborsClassifier(n_neighbors=3),
    "decision_tree": lambda random_state: DecisionTreeClassifier(
        max_depth=5, random_state=random_state
    ),
    "random_forest": lambda random_state: RandomForestClassifier(
        n_estimators=20, max_depth=6, random_state=random_state
    ),
}


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
    """
    Train and save a gesture recognition model.

    Args:
        dataset_path: Path to local CSV dataset
        model_path: Path to save the trained model
        model_type: Type of model to train
        test_size: Test set fraction
        random_state: Random seed
        google_credentials_path: Path to Google credentials JSON
        google_spreadsheet_id: Google Sheets spreadsheet ID

    Returns:
        Dictionary with training metrics
    """
    # Load dataset from Google Sheets if credentials provided, otherwise from local CSV
    if google_credentials_path and google_spreadsheet_id:
        print("📊 Loading dataset from Google Sheets...")
        X, y, _ = load_dataset_from_google_sheets(
            google_credentials_path, google_spreadsheet_id
        )
    elif dataset_path:
        print(f"📊 Loading dataset from {dataset_path}...")
        X, y, _ = load_dataset(dataset_path)
    else:
        raise ValueError(
            "Either dataset_path or (google_credentials_path and google_spreadsheet_id) must be provided"
        )

    if len(set(y)) < 2:
        raise ValueError("Dataset must contain at least two gesture classes")

    counts = Counter(y)
    n_samples = len(y)
    n_classes = len(counts)
    n_test = math.ceil(test_size * n_samples)
    n_train = n_samples - n_test
    can_split = (
        n_samples >= 5
        and min(counts.values()) >= 2
        and n_test >= n_classes
        and n_train >= n_classes
    )

    if can_split:
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=test_size,
            random_state=random_state,
            stratify=y,
        )
    else:
        X_train, X_test, y_train, y_test = X, X, y, y

    model = build_model(model_type, random_state)
    model.fit(X_train, y_train)
    accuracy, report = evaluate_model(model, X_test, y_test)

    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)

    return {
        "accuracy": accuracy,
        "report": report,
        "model_path": str(model_path),
    }


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
