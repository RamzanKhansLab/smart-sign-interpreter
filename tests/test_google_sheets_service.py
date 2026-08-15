from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.services import google_sheets_service


def _mock_sheets_client(monkeypatch):
    worksheet = MagicMock()
    spreadsheet = MagicMock()
    spreadsheet.worksheet.return_value = worksheet
    client = MagicMock()
    client.open_by_key.return_value = spreadsheet
    monkeypatch.setattr(google_sheets_service.gspread, "authorize", lambda _: client)
    return client


def test_google_sheets_service_accepts_credentials_file_path(tmp_path, monkeypatch):
    credentials_path = tmp_path / "google-credentials.json"
    credentials_path.write_text("{}", encoding="utf-8")
    credentials = MagicMock()
    load_from_file = MagicMock(return_value=credentials)
    load_from_info = MagicMock()
    monkeypatch.setattr(
        google_sheets_service.Credentials,
        "from_service_account_file",
        load_from_file,
    )
    monkeypatch.setattr(
        google_sheets_service.Credentials,
        "from_service_account_info",
        load_from_info,
    )
    _mock_sheets_client(monkeypatch)

    google_sheets_service.GoogleSheetsService(str(credentials_path), "spreadsheet-id")

    load_from_file.assert_called_once_with(
        str(credentials_path), scopes=google_sheets_service.GoogleSheetsService.SCOPES
    )
    load_from_info.assert_not_called()


def test_google_sheets_service_accepts_inline_credentials_json(monkeypatch):
    credentials_info = {
        "type": "service_account",
        "project_id": "example-project",
        "private_key": "-----BEGIN PRIVATE KEY-----\\nplaceholder\\n-----END PRIVATE KEY-----\\n",
        "client_email": "service@example-project.iam.gserviceaccount.com",
    }
    credentials = MagicMock()
    load_from_file = MagicMock()
    load_from_info = MagicMock(return_value=credentials)
    monkeypatch.setattr(
        google_sheets_service.Credentials,
        "from_service_account_file",
        load_from_file,
    )
    monkeypatch.setattr(
        google_sheets_service.Credentials,
        "from_service_account_info",
        load_from_info,
    )
    _mock_sheets_client(monkeypatch)

    google_sheets_service.GoogleSheetsService(
        json.dumps(credentials_info), "spreadsheet-id"
    )

    load_from_info.assert_called_once_with(
        credentials_info, scopes=google_sheets_service.GoogleSheetsService.SCOPES
    )
    load_from_file.assert_not_called()


def test_google_sheets_service_rejects_invalid_inline_credentials_json():
    with pytest.raises(ValueError, match="valid JSON"):
        google_sheets_service.GoogleSheetsService("{not-valid-json", "spreadsheet-id")
