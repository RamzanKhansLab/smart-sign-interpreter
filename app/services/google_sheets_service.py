"""Google Sheets service for persistent data storage."""

from __future__ import annotations

import json
import os

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
            raise RuntimeError(f"Failed to access Google Sheet: {str(e)}")

    def _write_header(self) -> None:
        """Write header row if sheet is empty."""
        try:
            if len(self.worksheet.get_all_values()) == 0:
                self.worksheet.append_row(self.HEADER)
        except Exception:
            pass

    def append_row(self, row_data: dict) -> bool:
        """
        Append a single row to the worksheet.

        Args:
            row_data: Dictionary with keys matching HEADER

        Returns:
            True if successful, False otherwise
        """
        try:
            values = [
                row_data.get("gesture", ""),
                row_data.get("timestamp", ""),
                row_data.get("channels", ""),
                row_data.get("imu", ""),
            ]
            self.worksheet.append_row(values)
            return True
        except Exception as e:
            print(f"Error appending row to Google Sheets: {str(e)}")
            return False

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
            self.worksheet.append_rows(values)
            return len(rows_data)
        except Exception as e:
            print(f"Error appending rows to Google Sheets: {str(e)}")
            return 0

    def get_all_rows(self) -> list[dict]:
        """
        Get all rows from the worksheet.

        Returns:
            List of dictionaries representing rows
        """
        try:
            all_values = self.worksheet.get_all_values()
            if not all_values:
                return []

            # Skip header row
            rows = []
            for row_values in all_values[1:]:
                if len(row_values) >= 4:
                    rows.append(
                        {
                            "gesture": row_values[0],
                            "timestamp": row_values[1],
                            "channels": row_values[2],
                            "imu": row_values[3],
                        }
                    )
            return rows
        except Exception as e:
            print(f"Error reading from Google Sheets: {str(e)}")
            return []

    def get_rows_by_gesture(self, gesture: str) -> list[dict]:
        """
        Get all rows for a specific gesture.

        Args:
            gesture: Gesture label to filter by

        Returns:
            List of dictionaries representing rows for the gesture
        """
        try:
            all_rows = self.get_all_rows()
            return [row for row in all_rows if row.get("gesture") == gesture]
        except Exception as e:
            print(f"Error filtering rows: {str(e)}")
            return []

    def clear_worksheet(self) -> bool:
        """
        Clear all data from the worksheet (keeps header).

        Returns:
            True if successful, False otherwise
        """
        try:
            self.worksheet.clear()
            self._write_header()
            return True
        except Exception as e:
            print(f"Error clearing worksheet: {str(e)}")
            return False

    def get_row_count(self) -> int:
        """
        Get total number of data rows (excluding header).

        Returns:
            Number of data rows
        """
        try:
            all_values = self.worksheet.get_all_values()
            return max(0, len(all_values) - 1)  # Subtract header
        except Exception:
            return 0

    @staticmethod
    def is_available() -> bool:
        """Check if Google Sheets libraries are available."""
        return GOOGLE_SHEETS_AVAILABLE
