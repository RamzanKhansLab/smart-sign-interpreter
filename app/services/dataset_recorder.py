from __future__ import annotations

import csv
import json
import threading
from collections import Counter
from pathlib import Path

HEADER = ["gesture", "timestamp", "channels", "imu"]


class DatasetRecorder:
    def __init__(self, dataset_path: str | Path) -> None:
        self.dataset_path = Path(dataset_path)
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.dataset_path.exists():
            with self.dataset_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=HEADER)
                writer.writeheader()

    def _normalize_label(self, label: str) -> str:
        label = (label or "").strip()
        if not label:
            raise ValueError("label cannot be empty")
        return label

    def _normalize_row(self, data: dict, label: str) -> dict:
        label = self._normalize_label(label)

        channels = data.get("channels")
        imu = data.get("imu")
        if isinstance(channels, list):
            channels = {f"s{i + 1}": float(v) for i, v in enumerate(channels)}
        if channels is None:
            channels = {}

        row = {
            "gesture": label,
            "timestamp": data.get("timestamp"),
            "channels": json.dumps(channels, separators=(",", ":"), ensure_ascii=False),
            "imu": json.dumps(imu or {}, separators=(",", ":"), ensure_ascii=False),
        }
        return row

    def save_sample(self, data: dict, label: str) -> None:
        self._ensure_file()
        row = self._normalize_row(data, label)
        with self._lock:
            with self.dataset_path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=HEADER)
                writer.writerow(row)

    def save_samples(self, samples: list[dict], label: str) -> int:
        self._ensure_file()
        rows = [self._normalize_row(sample, label) for sample in samples]
        with self._lock:
            with self.dataset_path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=HEADER)
                for row in rows:
                    writer.writerow(row)
        return len(rows)

    def stats(self) -> dict:
        self._ensure_file()
        with self._lock:
            with self.dataset_path.open("r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                gestures = [
                    (row.get("gesture", "") or "")
                    for row in reader
                    if row and row.get("gesture") is not None
                ]
        counts = Counter(gestures)
        return {
            "total": sum(counts.values()),
            "by_label": dict(counts),
            "path": str(self.dataset_path),
        }
