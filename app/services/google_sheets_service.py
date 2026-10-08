"""Google Sheets service for persistent data storage."""

from __future__ import annotations

import json
import os


class DatasetStorageError(RuntimeError):
    """The configured dataset storage could not complete an operation."""


try:
    import gspread
    from google.oauth2.service_account import Credentials

    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    GOOGLE_SHEETS_AVAILABLE = False


class GoogleSheetsService:
    """Service for reading and writing data to Google Sheets."""

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    HEADER = ["gesture", "timestamp", "channels", "imu"]

    def __init__(self, credentials_source: str, spreadsheet_id: str):
        """
        Initialize Google Sheets service.

        Args:
            credentials_source: Either a path to a service-account JSON file or
                the complete service-account JSON document. The latter is useful
                for a secret environment variable on platforms such as Render.
            spreadsheet_id: Google Sheets spreadsheet ID
        """
        if not GOOGLE_SHEETS_AVAILABLE:
            raise ImportError(
                "Google Sheets libraries not installed. "
                "Install with: pip install gspread google-auth google-auth-oauthlib"
            )

        self.spreadsheet_id = spreadsheet_id
        self.credentials_source = credentials_source
        self.client = None
        self.spreadsheet = None
        self.worksheet = None
        self._initialize_client()

    def _load_credentials(self):
        """Load credentials from a JSON document or a JSON file path."""
        source = (self.credentials_source or "").strip()
        if not source:
            raise ValueError("Google credentials were not provided")

        if source.startswith("{"):
            try:
                credentials_info = json.loads(source)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Google credentials must be valid JSON when provided inline"
                ) from exc

            if not isinstance(credentials_info, dict):
                raise ValueError("Inline Google credentials must be a JSON object")

            return Credentials.from_service_account_info(
                credentials_info, scopes=self.SCOPES
            )

        if not os.path.isfile(source):
            raise FileNotFoundError(
                "Google credentials file not found. Set GOOGLE_CREDENTIALS_PATH "
                "to an existing file path or to the complete service-account JSON."
            )

        return Credentials.from_service_account_file(source, scopes=self.SCOPES)

    def _initialize_client(self) -> None:
        """Initialize Google Sheets client."""
        credentials = self._load_credentials()
        self.client = gspread.authorize(credentials)
        self._get_or_create_worksheet()

    def _get_or_create_worksheet(self) -> None:
        """Get existing worksheet or create new one."""
        try:
            spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            self.spreadsheet = spreadsheet
            # Try to get existing worksheet
            try:
                self.worksheet = spreadsheet.worksheet("gesture_data")
            except gspread.exceptions.WorksheetNotFound:
                # Create new worksheet if it doesn't exist
                self.worksheet = spreadsheet.add_worksheet(
                    title="gesture_data", rows=1000, cols=4
                )
            self._write_header()
        except Exception as e:
            raise DatasetStorageError(
                "Cannot access Google Sheets. Check credentials, sharing permissions, "
                "and the connection, then retry."
            ) from e

    def _write_header(self) -> None:
        """Write header row if sheet is empty."""
        if len(self.worksheet.get_all_values()) == 0:
            self.worksheet.append_row(self.HEADER, value_input_option="RAW")

    def append_row(self, row_data: dict) -> bool:
        """
        Append a single row to the worksheet.

        Args:
            row_data: Dictionary with keys matching HEADER

        Returns:
            True if successful; raises DatasetStorageError on failure
        """
        try:
            values = [
                row_data.get("gesture", ""),
                row_data.get("timestamp", ""),
                row_data.get("channels", ""),
                row_data.get("imu", ""),
            ]
            self.worksheet.append_row(values, value_input_option="RAW")
            return True
        except Exception as e:
            raise DatasetStorageError(
                "Could not save the sample to Google Sheets."
            ) from e

    def append_rows(self, rows_data: list[dict]) -> int:
        """
        Append multiple rows to the worksheet.

        Args:
            rows_data: List of dictionaries with keys matching HEADER

        Returns:
            Number of rows successfully appended
        """
        try:
            values = [
                [
                    row.get("gesture", ""),
                    row.get("timestamp", ""),
                    row.get("channels", ""),
                    row.get("imu", ""),
                ]
                for row in rows_data
            ]
            if values:
                self.worksheet.append_rows(values, value_input_option="RAW")
            return len(rows_data)
        except Exception as e:
            raise DatasetStorageError("Could not save samples to Google Sheets.") from e

    def get_all_rows(self) -> list[dict]:
        """
        Get all rows from the worksheet.

        Returns:
            List of dictionaries representing rows
        """
        try:
            return [row for _, row in self._indexed_rows()]
        except Exception as e:
            if isinstance(e, DatasetStorageError):
                raise
            raise DatasetStorageError(
                "Could not read Google Sheets. Check the connection and sheet access, "
                "then refresh again."
            ) from e

    def _indexed_rows(self) -> list[tuple[int, dict]]:
        values = self.worksheet.get_all_values()
        indexed = [
            (index, cells) for index, cells in enumerate(values, 1) if any(cells)
        ]
        if not indexed:
            return []
        first_cells = indexed[0][1]
        header = [str(cell).lstrip("\ufeff").strip() for cell in first_cells[:4]]
        if header == self.HEADER:
            data = indexed[1:]
        else:
            # Some existing sheets were populated without a header. Do not lose
            # their first sample or shift the physical row numbers used by edits.
            try:
                channels = json.loads(first_cells[2])
            except (IndexError, ValueError, TypeError):
                channels = None
            if not isinstance(channels, (dict, list)):
                raise DatasetStorageError(
                    "Unrecognized gesture_data sheet layout. Expected columns: "
                    "gesture, timestamp, channels, imu (optional)."
                )
            data = indexed
        # Sheets omits trailing empty cells, including the optional IMU column.
        return [
            (index, dict(zip(self.HEADER, (cells + [""] * 4)[:4])))
            for index, cells in data
        ]

    def rewrite(self, transform) -> tuple[int, list[dict]]:
        """Edit only matching rows in one atomic Sheets batch; preserve other cells."""
        try:
            requests = []
            kept = []
            changed = 0
            # Bottom-up deletion keeps row indices valid within the batch.
            for index, row in reversed(self._indexed_rows()):
                result = transform(row)
                if result is None:
                    if index == 1 and not kept:
                        # Google forbids deleting the final grid row. Clearing
                        # this last headerless sample leaves an empty valid sheet.
                        requests.append(
                            {
                                "updateCells": {
                                    "range": {
                                        "sheetId": self.worksheet.id,
                                        "startRowIndex": 0,
                                        "endRowIndex": 1,
                                    },
                                    "rows": [],
                                    "fields": "userEnteredValue",
                                }
                            }
                        )
                        changed += 1
                        continue
                    requests.append(
                        {
                            "deleteDimension": {
                                "range": {
                                    "sheetId": self.worksheet.id,
                                    "dimension": "ROWS",
                                    "startIndex": index - 1,
                                    "endIndex": index,
                                }
                            }
                        }
                    )
                    changed += 1
                else:
                    kept.append(result)
                    if result != row:
                        requests.append(
                            {
                                "updateCells": {
                                    "range": {
                                        "sheetId": self.worksheet.id,
                                        "startRowIndex": index - 1,
                                        "endRowIndex": index,
                                        "startColumnIndex": 0,
                                        "endColumnIndex": 1,
                                    },
                                    "rows": [
                                        {
                                            "values": [
                                                {
                                                    "userEnteredValue": {
                                                        "stringValue": result[
                                                            "gesture"
                                                        ],
                                                    }
                                                }
                                            ]
                                        }
                                    ],
                                    "fields": "userEnteredValue",
                                }
                            }
                        )
                        changed += 1
            if requests:
                self.spreadsheet.batch_update({"requests": requests})
            return changed, list(reversed(kept))
        except Exception as e:
            if isinstance(e, DatasetStorageError):
                raise
            raise DatasetStorageError(
                "Could not edit Google Sheets. Check Editor access and retry."
            ) from e

    def get_rows_by_gesture(self, gesture: str) -> list[dict]:
        """
        Get all rows for a specific gesture.

        Args:
            gesture: Gesture label to filter by

        Returns:
            List of dictionaries representing rows for the gesture
        """
        return [row for row in self.get_all_rows() if row.get("gesture") == gesture]

    def clear_worksheet(self) -> bool:
        """
        Clear all data from the worksheet (keeps header).

        Returns:
            True if successful; raises DatasetStorageError on failure
        """
        self.rewrite(lambda row: None)
        return True

    def get_row_count(self) -> int:
        """
        Get total number of data rows (excluding header).

        Returns:
            Number of data rows
        """
        return len(self.get_all_rows())

    @staticmethod
    def is_available() -> bool:
        """Check if Google Sheets libraries are available."""
        return GOOGLE_SHEETS_AVAILABLE
