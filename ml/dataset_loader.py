from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.services.google_sheets_service import GoogleSheetsService

FEATURE_COLUMNS = ['thumb', 'index', 'middle', 'ring', 'little']
EXPECTED_COLUMNS = ["gesture", "timestamp"] + FEATURE_COLUMNS


def _extract_features_from_channels(channels_json: str) -> list[float]:
    """
    Extract flex sensor values from JSON channels string.

    Expected channels: thumb, index, middle, ring, little
    """
    try:
        channels = json.loads(channels_json) if isinstance(channels_json, str) else channels_json
        if isinstance(channels, dict):
            return [
                float(channels.get('thumb', 0)),
                float(channels.get('index', 0)),
                float(channels.get('middle', 0)),
                float(channels.get('ring', 0)),
                float(channels.get('little', 0)),
            ]
    except Exception:
        pass
    return [0.0] * len(FEATURE_COLUMNS)


def load_dataset_from_google_sheets(
    credentials_path: str, spreadsheet_id: str
) -> tuple[list, list, pd.DataFrame]:
    """
    Load dataset from Google Sheets.

    Returns:
        Tuple of (X, y, dataframe)
    """
    try:
        google_sheets = GoogleSheetsService(credentials_path, spreadsheet_id)
        rows = google_sheets.get_all_rows()

        if not rows:
            raise ValueError("No data found in Google Sheets")

        data = []
        for row in rows:
            gesture = row.get("gesture", "")
            timestamp = row.get("timestamp", "")
            channels = row.get("channels", "{}")

            features = _extract_features_from_channels(channels)
            data.append({
                "gesture": gesture,
                "timestamp": timestamp,
                "thumb": features[0],
                "index": features[1],
                "middle": features[2],
                "ring": features[3],
                "little": features[4],
            })

        df = pd.DataFrame(data)
        df = df.dropna()

        X = df[FEATURE_COLUMNS].astype(float).values
        y = df["gesture"].astype(str).values

        return X, y, df
    except Exception as e:
        raise RuntimeError(f"Failed to load dataset from Google Sheets: {str(e)}")


def load_dataset(dataset_path: str | Path) -> tuple:
    """Load dataset from local CSV file."""
    path = Path(dataset_path)
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found at {path}")

    df = pd.read_csv(path)

    # Handle both direct feature columns and JSON-encoded channels
    if "channels" in df.columns and "thumb" not in df.columns:
        # Extract features from channels JSON
        features_list = []
        for channels_str in df["channels"]:
            features_list.append(_extract_features_from_channels(channels_str))

        for i, col in enumerate(FEATURE_COLUMNS):
            df[col] = [row[i] for row in features_list]

    missing = set(FEATURE_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing columns: {sorted(missing)}")

    df = df.dropna()
    X = df[FEATURE_COLUMNS].astype(float).values
    y = df["gesture"].astype(str).values
    return X, y, df
