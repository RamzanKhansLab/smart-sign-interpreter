from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier


def _as_float(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except Exception:
        return None


def payload_to_features(payload: dict) -> dict[str, float]:
    features: dict[str, float] = {}

    channels = payload.get("channels")
    if isinstance(channels, list):
        channels = {f"s{i + 1}": v for i, v in enumerate(channels)}

    if isinstance(channels, dict):
        for key, value in channels.items():
            v = _as_float(value)
            if v is None:
                continue
            features[f"ch:{key}"] = v

    imu = payload.get("imu")
    if isinstance(imu, dict):
        for key in ("ax", "ay", "az", "gx", "gy", "gz"):
            v = _as_float(imu.get(key))
            if v is None:
                continue
            features[f"imu:{key}"] = v

    return features


MODEL_REGISTRY = {
    "knn": lambda random_state: KNeighborsClassifier(n_neighbors=3),
    "decision_tree": lambda random_state: DecisionTreeClassifier(
        max_depth=6, random_state=random_state
    ),
    "random_forest": lambda random_state: RandomForestClassifier(
        n_estimators=50, max_depth=10, random_state=random_state
    ),
}


class MLService:
    def __init__(self, model_path: str | Path, allow_missing: bool) -> None:
        self.model_path = Path(model_path)
        self.allow_missing = allow_missing
        self.model = None
        self._predict_mode = "dict"  # "dict" (new) or "legacy" (5-sensor vector)
        self.load()

    def load(self) -> None:
        if not self.model_path.exists():
            if self.allow_missing:
                self.model = None
                return
            raise FileNotFoundError(f"Model not found: {self.model_path}")

        model = joblib.load(self.model_path)
        self.model = model

        self._predict_mode = "legacy"
        try:
            if isinstance(model, Pipeline) and "vectorizer" in model.named_steps:
                if isinstance(model.named_steps["vectorizer"], DictVectorizer):
                    self._predict_mode = "dict"
        except Exception:
            self._predict_mode = "legacy"

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def reset(self, delete_file: bool = True) -> None:
        self.model = None
        if delete_file and self.model_path.exists():
            self.model_path.unlink(missing_ok=True)

    def predict(self, payload: dict) -> str | None:
        if self.model is None:
            return None

        try:
            if self._predict_mode == "dict":
                features = payload_to_features(payload)
                if not features:
                    return None
                prediction = self.model.predict([features])
            else:
                channels = payload.get("channels")
                if isinstance(channels, dict):
                    vec = [
                        _as_float(channels.get("s1")),
                        _as_float(channels.get("s2")),
                        _as_float(channels.get("s3")),
                        _as_float(channels.get("s4")),
                        _as_float(channels.get("s5")),
                    ]
                elif isinstance(channels, list):
                    vec = [
                        _as_float(channels[0]) if len(channels) > 0 else None,
                        _as_float(channels[1]) if len(channels) > 1 else None,
                        _as_float(channels[2]) if len(channels) > 2 else None,
                        _as_float(channels[3]) if len(channels) > 3 else None,
                        _as_float(channels[4]) if len(channels) > 4 else None,
                    ]
                else:
                    return None

                if any(v is None for v in vec[:3]):
                    return None

                arr = np.array([0.0 if v is None else v for v in vec], dtype=float).reshape(
                    1, -1
                )
                prediction = self.model.predict(arr)

            if len(prediction) == 0:
                return None
            return str(prediction[0])
        except Exception:
            return None

    def _load_dataset(self, dataset_path: str | Path):
        dataset_path = Path(dataset_path)
        if not dataset_path.is_file():
            raise FileNotFoundError(f"Dataset not found: {dataset_path}")

        X: list[dict[str, float]] = []
        y: list[str] = []

        with dataset_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row:
                    continue
                label = (row.get("gesture") or "").strip()
                if not label:
                    continue

                channels_raw = row.get("channels") or "{}"
                imu_raw = row.get("imu") or "{}"
                try:
                    channels = json.loads(channels_raw)
                except Exception:
                    channels = {}
                try:
                    imu = json.loads(imu_raw)
                except Exception:
                    imu = {}

                features = payload_to_features({"channels": channels, "imu": imu})
                if not features:
                    continue
                X.append(features)
                y.append(label)

        if not X:
            raise ValueError("Dataset has no usable samples")
        if len(set(y)) < 2:
            raise ValueError("Dataset must contain at least two gesture classes")
        return X, y

    def retrain(
        self,
        dataset_path: str | Path,
        model_type: str = "knn",
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> dict:
        model_type = (model_type or "knn").lower()
        if model_type not in MODEL_REGISTRY:
            raise ValueError(
                f"Unsupported model type: {model_type}. "
                f"Choose one of: {sorted(MODEL_REGISTRY.keys())}"
            )

        X, y = self._load_dataset(dataset_path)

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

        pipeline = Pipeline(
            steps=[
                ("vectorizer", DictVectorizer(sparse=False)),
                ("scaler", StandardScaler()),
                ("clf", MODEL_REGISTRY[model_type](random_state)),
            ]
        )
        pipeline.fit(X_train, y_train)

        y_pred = pipeline.predict(X_test)
        accuracy = float(accuracy_score(y_test, y_pred))
        report = classification_report(y_test, y_pred, zero_division=0)

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, self.model_path)
        self.model = pipeline
        self._predict_mode = "dict"

        return {
            "accuracy": accuracy,
            "report": report,
            "model_path": str(self.model_path),
            "samples": n_samples,
            "classes": sorted(set(y)),
            "feature_count": len(pipeline.named_steps["vectorizer"].feature_names_),
            "model_type": model_type,
        }
