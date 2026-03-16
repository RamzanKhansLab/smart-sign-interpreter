from __future__ import annotations

import joblib

from ml.train_model import train_and_save


def test_train_model_creates_file(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    dataset_path.write_text(
        "thumb,index,middle,ring,little,gesture\n"
        "840,210,205,220,230,HELLO\n"
        "835,215,200,225,235,HELLO\n"
        "200,800,820,810,790,YES\n"
        "210,790,830,805,780,YES\n"
    )

    model_path = tmp_path / "gesture_model.pkl"
    metrics = train_and_save(
        dataset_path=str(dataset_path),
        model_path=str(model_path),
        model_type="knn",
    )

    assert model_path.exists()
    model = joblib.load(model_path)
    assert hasattr(model, "predict")
    assert metrics["accuracy"] >= 0.0
