from __future__ import annotations

import csv
import json
import os
import threading
from collections import Counter
from pathlib import Path

HEADER = ["gesture", "timestamp", "channels", "imu"]


class DatasetRecorder:
    def __init__(self, dataset_path: str | Path) -> None:
        self.dataset_path = Path(dataset_path).expanduser()
        self._lock = threading.RLock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        with self._lock:
            self._ensure_file_unlocked()

    def _ensure_file_unlocked(self) -> None:
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.dataset_path.exists():
            self._write_header_file_unlocked()
            return

        if self.dataset_path.stat().st_size == 0:
            self._write_header_file_unlocked()
            return

        with self.dataset_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            first_row = next(reader, None)
            if self._header_matches(first_row):
                return

            rows = []
            if first_row:
                rows.append(first_row)
            rows.extend(row for row in reader if row)

        if not rows:
            self._write_header_file_unlocked()
            return

        if all(len(row) == len(HEADER) for row in rows):
            # Repair older/headerless datasets without discarding the captured rows.
            self._rewrite_rows_with_header_unlocked(rows)
            return

        raise ValueError(
            f"Dataset file has an invalid CSV structure and cannot be repaired: {self.dataset_path}"
        )

    def _flush_handle(self, handle) -> None:
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass

    def _write_header_file_unlocked(self) -> None:
        with self.dataset_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADER)
            self._flush_handle(handle)

    def _header_matches(self, row: list[str] | None) -> bool:
        if not row:
            return False
        normalized = [cell.lstrip("\ufeff") for cell in row]
        return normalized == HEADER

    def _rewrite_rows_with_header_unlocked(self, rows: list[list[str]]) -> None:
        tmp_path = self.dataset_path.with_suffix(self.dataset_path.suffix + ".tmp")
        with tmp_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADER)
            writer.writerows(rows)
            self._flush_handle(handle)
        tmp_path.replace(self.dataset_path)

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
                self._flush_handle(handle)

    def save_samples(self, samples: list[dict], label: str) -> int:
        self._ensure_file()
        rows = [self._normalize_row(sample, label) for sample in samples]
        with self._lock:
            with self.dataset_path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=HEADER)
                for row in rows:
                    writer.writerow(row)
                self._flush_handle(handle)
        return len(rows)

    def _parse_json_cell(self, raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            return {}
        except Exception:
            return {}

    def list_rows(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        label: str | None = None,
    ) -> dict:
        self._ensure_file()
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))

        with self._lock:
            with self.dataset_path.open("r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                rows = []
                total = 0
                for row in reader:
                    if not row:
                        continue
                    gesture = row.get("gesture")
                    if label is not None and gesture != label:
                        continue

                    if total >= offset and len(rows) < limit:
                        rows.append(
                            {
                                "gesture": gesture,
                                "timestamp": row.get("timestamp"),
                                "channels": self._parse_json_cell(row.get("channels")),
                                "imu": self._parse_json_cell(row.get("imu")),
                            }
                        )
                    total += 1

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "rows": rows,
        }

    def _rewrite(self, transform) -> int:
        self._ensure_file()
        tmp_path = self.dataset_path.with_suffix(self.dataset_path.suffix + ".tmp")

        changed = 0
        with self._lock:
            with self.dataset_path.open("r", newline="", encoding="utf-8") as inp:
                reader = csv.DictReader(inp)
                with tmp_path.open("w", newline="", encoding="utf-8") as out:
                    writer = csv.DictWriter(out, fieldnames=HEADER)
                    writer.writeheader()
                    for row in reader:
                        if not row:
                            continue
                        new_row = transform(row)
                        if new_row is None:
                            changed += 1
                            continue
                        if new_row is not row:
                            changed += 1
                        writer.writerow(
                            {
                                "gesture": new_row.get("gesture", ""),
                                "timestamp": new_row.get("timestamp", ""),
                                "channels": new_row.get("channels", "{}"),
                                "imu": new_row.get("imu", "{}"),
                            }
                        )
                    self._flush_handle(out)
            tmp_path.replace(self.dataset_path)

        return changed

    def rename_label(self, from_label: str, to_label: str) -> int:
        from_label = (from_label or "")
        to_label = self._normalize_label(to_label)

        def transform(row: dict):
            if row.get("gesture") != from_label:
                return row
            new_row = dict(row)
            new_row["gesture"] = to_label
            return new_row

        return self._rewrite(transform)

    def delete_label(self, label: str) -> int:
        label = (label or "")

        def transform(row: dict):
            if row.get("gesture") == label:
                return None
            return row

        return self._rewrite(transform)

    def delete_empty_labels(self) -> int:
        return self.delete_label("")

    def clear(self) -> None:
        self._ensure_file()
        with self._lock:
            with self.dataset_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=HEADER)
                writer.writeheader()
                self._flush_handle(handle)

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
