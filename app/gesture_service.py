from __future__ import annotations

import numpy as np

from .validators import SENSOR_FIELDS


def to_feature_array(sensor_data: dict) -> np.ndarray:
    values = [sensor_data[field] for field in SENSOR_FIELDS]
    return np.array(values, dtype=float).reshape(1, -1)


def predict_gesture(model, sensor_data: dict) -> str:
    features = to_feature_array(sensor_data)
    prediction = model.predict(features)
    if len(prediction) == 0:
        raise RuntimeError("Empty prediction result")
    return str(prediction[0])
