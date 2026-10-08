from __future__ import annotations

import csv
import hashlib
import json
import math
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from app.services.model_metrics import classification_metrics, confusion_matrix_png


def _as_float(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
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
        self._lock = threading.RLock()
        self.reports_path = self.model_path.with_suffix(".reports")
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
        with self._lock:
            self.model = None
            if delete_file:
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

                arr = np.array(
                    [0.0 if v is None else v for v in vec], dtype=float
                ).reshape(1, -1)
                prediction = self.model.predict(arr)

            if len(prediction) == 0:
                return None
            return str(prediction[0])
        except Exception:
            return None

    def _load_dataset(self, dataset_path: str | Path):
        with Path(dataset_path).open("r", newline="", encoding="utf-8-sig") as handle:
            return self._rows_to_dataset(list(csv.DictReader(handle)))

    def _rows_to_dataset(self, rows: list[dict], *, require_two_classes=True):
        X, y = [], []
        names = ("thumb", "index", "middle", "ring", "little")
        for row in rows:
            label = (row.get("gesture") or "").strip()
            if not label:
                continue
            payload = {}
            for key in ("channels", "imu"):
                raw = row.get(key) or "{}"
                try:
                    payload[key] = json.loads(raw) if isinstance(raw, str) else raw
                except (ValueError, TypeError):
                    payload[key] = {}
            # Retain support for original CSVs with five direct feature columns.
            if "channels" not in row:
                payload["channels"] = {
                    f"s{i}": row.get(f"s{i}", row.get(name))
                    for i, name in enumerate(names, start=1)
                }
            features = payload_to_features(payload)
            if features:
                X.append(features)
                y.append(label)
        if not X:
            raise ValueError("Dataset has no usable samples")
        if require_two_classes and len(set(y)) < 2:
            raise ValueError("Dataset must contain at least two gesture classes")
        return X, y

    def _load_dataset_from_google_sheets(
        self, credentials_path: str, spreadsheet_id: str
    ):
        from app.services.google_sheets_service import GoogleSheetsService

        sheets = GoogleSheetsService(credentials_path, spreadsheet_id)
        return self._rows_to_dataset(sheets.get_all_rows())

    def retrain(
        self,
        dataset_path: str | Path = None,
        model_type: str = "knn",
        test_size: float = 0.2,
        random_state: int = 42,
        google_credentials_path: str = None,
        google_spreadsheet_id: str = None,
        rows: list[dict] | None = None,
        dataset_source: str | None = None,
    ) -> dict:
        """
        Retrain the model with the given dataset.

        Args:
            dataset_path: Local CSV dataset path
            model_type: Type of model to train
            test_size: Test set fraction
            random_state: Random seed
            google_credentials_path: Google Sheets credentials path
            google_spreadsheet_id: Google Sheets ID
        """
        started = time.perf_counter()
        model_type = (model_type or "knn").strip().lower()
        if not 0 < test_size < 1:
            raise ValueError("test_size must be between 0 and 1")
        if model_type not in MODEL_REGISTRY:
            raise ValueError(
                f"Unsupported model type: {model_type}. "
                f"Choose one of: {sorted(MODEL_REGISTRY.keys())}"
            )

        # Load from Google Sheets if credentials provided, otherwise from local CSV
        if rows is not None:
            X, y = self._rows_to_dataset(rows)
        elif google_credentials_path and google_spreadsheet_id:
            print("📊 Loading dataset from Google Sheets...")
            X, y = self._load_dataset_from_google_sheets(
                google_credentials_path, google_spreadsheet_id
            )
        elif dataset_path:
            print(f"📊 Loading dataset from {dataset_path}...")
            X, y = self._load_dataset(dataset_path)
        else:
            raise ValueError(
                "Provide dataset_path or both google_credentials_path "
                "and google_spreadsheet_id"
            )

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
        if model_type == "knn":
            pipeline.set_params(clf__n_neighbors=min(3, len(X_train)))
        pipeline.fit(X_train, y_train)

        y_pred = pipeline.predict(X_test)
        metrics = classification_metrics(y_test, y_pred, sorted(set(y)))
        metrics.update(
            {
                "run_id": uuid4().hex,
                "trained_at": datetime.now(timezone.utc).isoformat(),
                "model_path": str(self.model_path),
                "samples": n_samples,
                "train_samples": len(y_train),
                "test_samples": len(y_test) if can_split else 0,
                "feature_count": len(pipeline.named_steps["vectorizer"].feature_names_),
                "model_type": model_type,
                "dataset_source": dataset_source
                or ("google_sheets" if google_spreadsheet_id else "local_csv"),
                "class_distribution": dict(counts),
                "random_state": random_state,
                "test_size": test_size,
                "training_seconds": time.perf_counter() - started,
                "evaluation_kind": "holdout" if can_split else "training_only",
                "evaluation_label": (
                    "Held-out test set" if can_split else "Training data only"
                ),
                "warning": (
                    None
                    if can_split
                    else (
                        "Too few samples per class for the requested stratified split. "
                        "These scores and this matrix use training data and do not "
                        "measure "
                        "generalization. Collect more samples per class and retrain."
                    )
                ),
            }
        )
        # Embed the exact evaluation in the model, so metrics and model stay paired.
        pipeline.training_metrics_ = metrics
        with self._lock:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.model_path.with_name(
                self.model_path.name + "." + metrics["run_id"] + ".tmp"
            )
            try:
                joblib.dump(pipeline, temporary)
                self._save_report(metrics)
                temporary.replace(self.model_path)
            finally:
                temporary.unlink(missing_ok=True)
            self.model = pipeline
            self._predict_mode = "dict"
        return metrics

    def _save_report(self, metrics: dict) -> None:
        self.reports_path.mkdir(parents=True, exist_ok=True)
        target = self.reports_path / (metrics["run_id"] + ".json")
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(metrics, indent=2, allow_nan=False), encoding="utf-8"
        )
        temporary.replace(target)
        # Keep an exportable Matplotlib artifact for the ML project report.
        png = self.reports_path / (metrics["run_id"] + ".png")
        temporary_png = png.with_suffix(".png.tmp")
        temporary_png.write_bytes(confusion_matrix_png(metrics))
        temporary_png.replace(png)

    def performance(self, recorder) -> dict:
        with self._lock:
            # Refresh from disk also picks up models trained through the CLI.
            if self.model_path.exists():
                self.load()
            else:
                self.model = None
            current = getattr(self.model, "training_metrics_", None)
            message = None
            if self.model is not None and current is None:
                try:
                    current = self._evaluate_existing(recorder)
                    if not (self.reports_path / (current["run_id"] + ".json")).exists():
                        self._save_report(current)
                except (ValueError, FileNotFoundError) as exc:
                    message = f"This older model has no saved evaluation. {exc}"
            runs = []
            for path in self.reports_path.glob("*.json"):
                try:
                    runs.append(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    continue
            if current:
                runs = [run for run in runs if run["run_id"] != current["run_id"]]
                runs.append(current)
            runs.sort(key=lambda run: run["trained_at"], reverse=True)
            return {
                "model_loaded": self.loaded,
                "active_run_id": current["run_id"] if current else None,
                "runs": runs,
                "message": message,
                "refreshed_at": datetime.now(timezone.utc).isoformat(),
            }

    def _evaluate_existing(self, recorder) -> dict:
        X, y = self._rows_to_dataset(recorder.read_rows(), require_two_classes=False)
        fingerprint = hashlib.sha256(self.model_path.read_bytes())
        fingerprint.update(json.dumps([X, y], sort_keys=True).encode("utf-8"))
        if self._predict_mode == "dict":
            predictions = self.model.predict(X)
        else:
            names = ("thumb", "index", "middle", "ring", "little")
            vectors = [
                [
                    row.get(f"ch:s{i}", row.get(f"ch:{name}", 0.0))
                    for i, name in enumerate(names, start=1)
                ]
                for row in X
            ]
            predictions = self.model.predict(vectors)
        metrics = classification_metrics(
            y, predictions, sorted(set(y) | set(map(str, predictions)))
        )
        classifier = (
            self.model.named_steps.get("clf")
            if isinstance(self.model, Pipeline)
            else self.model
        )
        metrics.update(
            {
                "run_id": fingerprint.hexdigest()[:32],
                # Original training time and split cannot be recovered from old pickles.
                "trained_at": datetime.fromtimestamp(
                    self.model_path.stat().st_mtime, timezone.utc
                ).isoformat(),
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "model_type": type(classifier).__name__,
                "samples": len(y),
                "train_samples": None,
                "test_samples": None,
                "feature_count": getattr(classifier, "n_features_in_", None),
                "class_distribution": dict(Counter(y)),
                "dataset_source": (
                    "google_sheets" if recorder.use_google_sheets else "local_csv"
                ),
                "evaluation_kind": "current_dataset",
                "evaluation_label": "Existing model on current dataset",
                "warning": "The original test split was not saved. This evaluates "
                "the existing model "
                "on the current dataset, which may include its training samples. "
                "It is not a held-out test score. Retrain to save a "
                "reproducible evaluation.",
            }
        )
        return metrics

    def get_report(self, run_id: str, recorder) -> dict:
        # Only identifiers generated here are accepted as filenames.
        if len(run_id) != 32 or any(char not in "0123456789abcdef" for char in run_id):
            raise FileNotFoundError("Evaluation not found")
        path = self.reports_path / (run_id + ".json")
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        current = getattr(self.model, "training_metrics_", None)
        if current and current["run_id"] == run_id:
            return current
        raise FileNotFoundError("Evaluation not found")
