from __future__ import annotations

import csv
import json
import os
import threading
from collections import Counter
from pathlib import Path

from app.services.google_sheets_service import DatasetStorageError, GoogleSheetsService

HEADER = ["gesture", "timestamp", "channels", "imu"]


class DatasetRecorder:
    """Dataset recorder supporting both local CSV and Google Sheets storage."""

    def __init__(
        self,
        dataset_path: str | Path,
        google_credentials_path: str | None = None,
        google_spreadsheet_id: str | None = None,
    ) -> None:
        """
        Initialize dataset recorder.

        Args:
            dataset_path: Path to local CSV file for backup
            google_credentials_path: Path to Google service-account credentials
                JSON, or the complete JSON document for an environment variable
            google_spreadsheet_id: Google Sheets spreadsheet ID
        """
        self.dataset_path = Path(dataset_path).expanduser()
        self._lock = threading.RLock()
        self.use_google_sheets = False
        self.google_sheets = None
        self._google_credentials = google_credentials_path
        self._google_id = google_spreadsheet_id
        self._cached_rows = None

        # Initialize Google Sheets if credentials provided
        if google_credentials_path and google_spreadsheet_id:
            try:
                self.google_sheets = GoogleSheetsService(
                    google_credentials_path, google_spreadsheet_id
                )
                self.use_google_sheets = True
                print("✓ Google Sheets integration enabled for dataset storage")
            except Exception as e:
                print(
                    f"⚠ Google Sheets initialization failed: {str(e)}"
                    " - Dataset operations will retry the configured Google Sheet"
                )
                self.use_google_sheets = False

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
            "Dataset file has an invalid CSV structure and cannot be repaired: "
            f"{self.dataset_path}"
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
        self.save_samples([data], label)

    def save_samples(self, samples: list[dict], label: str) -> int:
        self._ensure_file()
        rows = [self._normalize_row(sample, label) for sample in samples]
        with self._lock:
            sheets = self._sheets()
            if sheets:
                existing = sheets.get_all_rows()
                self.google_sheets.append_rows(rows)
                self._mirror_rows(existing + rows)
                return len(rows)

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

    def _sheets(self):
        if not self.google_sheets and self._google_credentials and self._google_id:
            try:
                self.google_sheets = GoogleSheetsService(
                    self._google_credentials, self._google_id
                )
                self.use_google_sheets = True
            except Exception as exc:
                raise DatasetStorageError(
                    "Google Sheets is configured but unavailable. Check credentials, "
                    "sheet sharing, and the connection, then retry."
                ) from exc
        return self.google_sheets if self.use_google_sheets else None

    def _mirror_rows(self, rows: list[dict]) -> None:
        self._rewrite_rows_with_header_unlocked(
            [[row.get(key, "") for key in HEADER] for row in rows]
        )
        self._cached_rows = rows

    def read_rows(self, *, refresh: bool = True) -> list[dict]:
        """Use one authoritative source for editing, statistics, and training."""
        with self._lock:
            sheets = self._sheets()
            if sheets:
                if refresh or self._cached_rows is None:
                    self._mirror_rows(sheets.get_all_rows())
                return [dict(row) for row in self._cached_rows]
            self._ensure_file_unlocked()
            with self.dataset_path.open(
                "r", newline="", encoding="utf-8-sig"
            ) as handle:
                return list(csv.DictReader(handle))

    def list_rows(
        self, *, limit: int = 50, offset: int = 0, label: str | None = None
    ) -> dict:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        all_rows = [
            row
            for row in self.read_rows()
            if label is None or row.get("gesture", "") == label
        ]
        rows = [
            {
                "gesture": row.get("gesture", ""),
                "timestamp": row.get("timestamp"),
                "channels": self._parse_json_cell(row.get("channels")),
                "imu": self._parse_json_cell(row.get("imu")),
            }
            for row in all_rows[offset : offset + limit]
        ]
        return {"total": len(all_rows), "limit": limit, "offset": offset, "rows": rows}

    def _rewrite(self, transform) -> int:
        with self._lock:
            sheets = self._sheets()
            if sheets:
                changed, rows = sheets.rewrite(transform)
            else:
                rows = []
                changed = 0
                for row in self.read_rows():
                    result = transform(row)
                    if result != row:
                        changed += 1
                    if result is not None:
                        rows.append(result)
            self._mirror_rows(rows)
            return changed

    def rename_label(self, from_label: str, to_label: str) -> int:
        to_label = self._normalize_label(to_label)
        return self._rewrite(
            lambda row: (
                {**row, "gesture": to_label}
                if row.get("gesture", "") == from_label
                else row
            )
        )

    def delete_label(self, label: str) -> int:
        return self._rewrite(
            lambda row: None if row.get("gesture", "") == label else row
        )

    def delete_empty_labels(self) -> int:
        return self._rewrite(
            lambda row: None if not row.get("gesture", "").strip() else row
        )

    def clear(self) -> None:
        self._rewrite(lambda row: None)

    def stats(self, *, refresh: bool = True) -> dict:
        counts = Counter(
            row.get("gesture", "") for row in self.read_rows(refresh=refresh)
        )
        return {
            "total": sum(counts.values()),
            "by_label": dict(counts),
            "path": (
                f"Google Sheets ({self.google_sheets.spreadsheet_id})"
                if self.use_google_sheets
                else str(self.dataset_path)
            ),
            "storage": "google_sheets" if self.use_google_sheets else "local_csv",
        }
