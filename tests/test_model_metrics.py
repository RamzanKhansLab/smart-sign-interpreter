from __future__ import annotations

import json

import joblib
import numpy as np
import pytest
from sklearn.tree import DecisionTreeClassifier

from app.services.dataset_recorder import DatasetRecorder
from app.services.ml_service import MLService
from app.services.model_metrics import classification_metrics, confusion_matrix_png
from ml.train_model import train_and_save


def training_rows(per_class=15):
    return [
        {
            "gesture": label,
            "channels": json.dumps(
                {"s1": base + i, "s2": base + i / 2, "s3": base - i}
            ),
            "imu": "{}",
        }
        for label, base in (("HELLO", 0), ("THANK_YOU", 100), ("YES", 200))
        for i in range(per_class)
    ]


@pytest.mark.parametrize("model_type", ["knn", "decision_tree", "random_forest"])
def test_training_metrics_persist_and_predict(tmp_path, model_type):
    path = tmp_path / "model.pkl"
    service = MLService(path, True)
    metrics = service.retrain(rows=training_rows(), model_type=model_type)
    assert metrics["evaluation_kind"] == "holdout"
    assert metrics["train_samples"] == 36
    assert metrics["test_samples"] == 9
    assert np.asarray(metrics["confusion_matrix"]).sum() == 9
    assert sum(row["support"] for row in metrics["per_class"]) == 9
    assert metrics["accuracy"] == 1.0
    assert metrics["precision"] == metrics["recall"] == metrics["f1"] == 1.0
    assert (
        (service.reports_path / (metrics["run_id"] + ".png"))
        .read_bytes()
        .startswith(b"\x89PNG\r\n\x1a\n")
    )
    restored = MLService(path, True)
    recorder = DatasetRecorder(tmp_path / "unused.csv")
    assert restored.performance(recorder)["runs"][0] == metrics
    assert (
        restored.predict({"channels": {"s1": 100, "s2": 100, "s3": 100}}) == "THANK_YOU"
    )


def test_confusion_matrix_orientation_and_metrics():
    metrics = classification_metrics(
        ["A", "A", "B", "B"], ["A", "B", "B", "B"], ["A", "B"]
    )
    assert metrics["confusion_matrix"] == [[1, 1], [0, 2]]
    assert metrics["accuracy"] == 0.75
    assert metrics["precision"] == pytest.approx((1 + 2 / 3) / 2)
    assert metrics["recall"] == 0.75
    assert metrics["f1"] == pytest.approx((2 / 3 + 0.8) / 2)
    metrics.update(model_type="knn", evaluation_label="Held-out test set")
    assert confusion_matrix_png(metrics).startswith(b"\x89PNG")


def test_labels_can_match_classification_report_summary_names():
    metrics = classification_metrics(
        ["accuracy", "macro avg"], ["accuracy", "accuracy"], ["accuracy", "macro avg"]
    )
    assert metrics["per_class"][0]["precision"] == 0.5
    assert metrics["per_class"][1]["recall"] == 0.0


def test_small_dataset_is_explicitly_training_only(tmp_path):
    service = MLService(tmp_path / "model.pkl", True)
    rows = training_rows(1)[:2]
    metrics = service.retrain(rows=rows)
    assert metrics["evaluation_kind"] == "training_only"
    assert metrics["test_samples"] == 0
    assert metrics["evaluation_samples"] == 2
    assert metrics["warning"]
    assert service.model.named_steps["clf"].n_neighbors == 2


def test_metrics_history_refresh_reset_and_png_endpoints(client, app):
    service = app.state.ml_service
    assert client.get("/api/model/metrics").json()["runs"] == []
    first = service.retrain(rows=training_rows(), model_type="knn")
    second = service.retrain(rows=training_rows(), model_type="decision_tree")
    response = client.get("/api/model/metrics")
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["active_run_id"] == second["run_id"]
    assert {run["run_id"] for run in data["runs"]} == {
        first["run_id"],
        second["run_id"],
    }
    png = client.get(f"/api/model/confusion-matrix/{first['run_id']}.png")
    assert png.headers["content-type"] == "image/png"
    assert png.content.startswith(b"\x89PNG")
    assert client.get("/api/model/confusion-matrix/missing.png").status_code == 404
    for page in ("/", "/collect", "/interpret", "/performance"):
        assert "Model Performance" in client.get(page).text
    client.post("/api/model/reset")
    data = client.get("/api/model/metrics").json()
    assert data["model_loaded"] is False
    assert data["active_run_id"] is None
    assert len(data["runs"]) == 2


def test_cli_model_replacement_is_visible_on_refresh(tmp_path):
    recorder = DatasetRecorder(tmp_path / "data.csv")
    for row in training_rows():
        recorder.save_sample({"channels": json.loads(row["channels"])}, row["gesture"])
    path = tmp_path / "model.pkl"
    running_service = MLService(path, True)
    metrics = train_and_save(str(recorder.dataset_path), str(path), "random_forest")
    assert isinstance(metrics["report"], dict)
    result = running_service.performance(recorder)
    assert result["active_run_id"] == metrics["run_id"]
    assert (
        running_service.predict({"channels": {"s1": 200, "s2": 200, "s3": 200}})
        == "YES"
    )


def test_previous_model_without_saved_metrics_is_evaluated_honestly(tmp_path):
    path = tmp_path / "old.pkl"
    model = DecisionTreeClassifier().fit([[1] * 5, [100] * 5], ["A", "B"])
    joblib.dump(model, path)
    original = path.read_bytes()
    recorder = DatasetRecorder(tmp_path / "data.csv")
    recorder.save_sample({"channels": [1] * 5}, "A")
    recorder.save_sample({"channels": [100] * 5}, "B")
    service = MLService(path, True)
    performance = service.performance(recorder)
    metrics = performance["runs"][0]
    assert metrics["evaluation_kind"] == "current_dataset"
    assert metrics["accuracy"] == 1.0
    assert metrics["train_samples"] is None
    assert metrics["warning"]
    assert path.read_bytes() == original
    recorder.save_sample({"channels": [100] * 5}, "A")
    refreshed = service.performance(recorder)
    active = next(
        run for run in refreshed["runs"] if run["run_id"] == refreshed["active_run_id"]
    )
    assert active["accuracy"] == pytest.approx(2 / 3)


def test_invalid_training_preserves_previous_model(tmp_path):
    service = MLService(tmp_path / "model.pkl", True)
    first = service.retrain(rows=training_rows())
    with pytest.raises(ValueError, match="two gesture classes"):
        service.retrain(rows=training_rows()[:2])
    assert service.model.training_metrics_["run_id"] == first["run_id"]
    with pytest.raises(ValueError, match="test_size"):
        service.retrain(rows=training_rows(), test_size=1.5)
