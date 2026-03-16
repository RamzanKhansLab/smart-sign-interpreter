from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import joblib


@lru_cache(maxsize=1)
def load_model(model_path: str):
    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(f"Model not found at {path}")
    model = joblib.load(path)
    if not hasattr(model, "predict"):
        raise ValueError("Loaded model does not support predict()")
    return model
