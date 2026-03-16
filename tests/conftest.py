from __future__ import annotations

import pytest

from app import create_app
from ml.train_model import train_and_save

SAMPLE_DATASET = """thumb,index,middle,ring,little,gesture
840,210,205,220,230,HELLO
835,215,200,225,235,HELLO
200,800,820,810,790,YES
210,790,830,805,780,YES
500,300,310,320,330,NO
510,290,305,315,325,NO
"""


@pytest.fixture()
def temp_model(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    dataset_path.write_text(SAMPLE_DATASET)
    model_path = tmp_path / "gesture_model.pkl"
    train_and_save(
        dataset_path=str(dataset_path),
        model_path=str(model_path),
        model_type="knn",
        test_size=0.2,
        random_state=42,
    )
    return model_path, dataset_path


@pytest.fixture()
def client(monkeypatch, temp_model):
    model_path, dataset_path = temp_model
    monkeypatch.setenv("MODEL_PATH", str(model_path))
    monkeypatch.setenv("DATASET_PATH", str(dataset_path))
    monkeypatch.setenv("ENABLE_TTS", "false")
    monkeypatch.setenv("ALLOW_MISSING_MODEL", "false")

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as test_client:
        yield test_client
