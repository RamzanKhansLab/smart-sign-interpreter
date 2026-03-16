from __future__ import annotations

from pathlib import Path

import pandas as pd

FEATURE_COLUMNS = ["thumb", "index", "middle", "ring", "little"]
EXPECTED_COLUMNS = FEATURE_COLUMNS + ["gesture"]


def load_dataset(dataset_path: str | Path):
    path = Path(dataset_path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found at {path}")

    df = pd.read_csv(path)
    missing = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing columns: {sorted(missing)}")

    df = df.dropna()
    X = df[FEATURE_COLUMNS].astype(float).values
    y = df["gesture"].astype(str).values
    return X, y, df
