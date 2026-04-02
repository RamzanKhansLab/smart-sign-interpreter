from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .utils import load_env_file, parse_bool


@dataclass
class AppConfig:
    BASE_DIR: Path
    APP_HOST: str
    APP_PORT: int
    MODEL_PATH: str
    DATASET_PATH: str
    LOG_LEVEL: str
    ALLOW_MISSING_MODEL: bool
    CORS_ORIGINS: list[str]
    ENABLE_DEMO: bool


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [p.strip() for p in value.split(',')]
    return [p for p in parts if p]


def get_config() -> AppConfig:
    load_env_file()
    base_dir = Path(__file__).resolve().parents[1]

    return AppConfig(
        BASE_DIR=base_dir,
        APP_HOST=os.getenv('APP_HOST', '0.0.0.0'),
        APP_PORT=int(os.getenv('APP_PORT', '8000')),
        MODEL_PATH=os.getenv('MODEL_PATH', str(base_dir / 'models' / 'gesture_model.pkl')),
        DATASET_PATH=os.getenv(
            'DATASET_PATH',
            str(base_dir / 'data' / 'datasets' / 'gesture_dataset.csv'),
        ),
        LOG_LEVEL=os.getenv('LOG_LEVEL', 'INFO'),
        ALLOW_MISSING_MODEL=parse_bool(os.getenv('ALLOW_MISSING_MODEL', 'true')),
        CORS_ORIGINS=_parse_csv(os.getenv('CORS_ORIGINS', '')),
        ENABLE_DEMO=parse_bool(os.getenv('ENABLE_DEMO', 'true')),
    )