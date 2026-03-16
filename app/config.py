from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .utils import parse_bool


@dataclass
class AppConfig:
    BASE_DIR: Path
    FLASK_HOST: str
    FLASK_PORT: int
    MODEL_PATH: str
    DATASET_PATH: str
    ENABLE_TTS: bool
    LOG_LEVEL: str
    LOG_FILE: str
    MODEL_TYPE: str
    RANDOM_STATE: int
    TEST_SIZE: float
    ALLOW_MISSING_MODEL: bool


def get_config() -> AppConfig:
    base_dir = Path(__file__).resolve().parents[1]
    log_dir = base_dir / "logs"
    model_path = os.getenv("MODEL_PATH", str(base_dir / "models" / "gesture_model.pkl"))
    dataset_path = os.getenv("DATASET_PATH", str(base_dir / "data" / "dataset.csv"))

    return AppConfig(
        BASE_DIR=base_dir,
        FLASK_HOST=os.getenv("FLASK_HOST", "0.0.0.0"),
        FLASK_PORT=int(os.getenv("FLASK_PORT", "5000")),
        MODEL_PATH=model_path,
        DATASET_PATH=dataset_path,
        ENABLE_TTS=parse_bool(os.getenv("ENABLE_TTS", "false")),
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        LOG_FILE=os.getenv("LOG_FILE", str(log_dir / "app.log")),
        MODEL_TYPE=os.getenv("MODEL_TYPE", "knn"),
        RANDOM_STATE=int(os.getenv("RANDOM_STATE", "42")),
        TEST_SIZE=float(os.getenv("TEST_SIZE", "0.2")),
        ALLOW_MISSING_MODEL=parse_bool(os.getenv("ALLOW_MISSING_MODEL", "false")),
    )
