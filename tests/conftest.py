from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Unit and API tests use local temporary datasets. Do not let a developer's
# .env credentials open or modify the live Google Sheet during test collection.
os.environ["GOOGLE_CREDENTIALS_PATH"] = ""
os.environ["GOOGLE_SPREADSHEET_ID"] = ""

from app.main import create_app  # noqa: E402


@pytest.fixture()
def app(tmp_path, monkeypatch):
    dataset_path = tmp_path / "gesture_dataset.csv"
    model_path = tmp_path / "gesture_model.pkl"
    monkeypatch.setenv("DATASET_PATH", str(dataset_path))
    monkeypatch.setenv("MODEL_PATH", str(model_path))
    monkeypatch.setenv("ALLOW_MISSING_MODEL", "true")
    return create_app()


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client
