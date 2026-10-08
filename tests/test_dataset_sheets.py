from __future__ import annotations

import copy
import csv
import json

import pytest

from app.services.dataset_recorder import DatasetRecorder
from app.services.google_sheets_service import DatasetStorageError, GoogleSheetsService


class MemoryWorksheet:
    """Offline Sheets boundary implementing the requests sent to Google."""

    id = 42

    def __init__(self):
        self.values = [GoogleSheetsService.HEADER[:]]
        self.fail_read = False
        self.fail_write = False
        self.batches = []

    def get_all_values(self):
        if self.fail_read:
            raise ConnectionError("offline")
        return copy.deepcopy(self.values)

    def append_rows(self, values, value_input_option):
        assert value_input_option == "RAW"
        if self.fail_write:
            raise PermissionError("read-only")
        self.values.extend(copy.deepcopy(values))

    def batch_update(self, body):
        if self.fail_write:
            raise PermissionError("read-only")
        self.batches.append(body)
        for request in body["requests"]:
            if "deleteDimension" in request:
                area = request["deleteDimension"]["range"]
                assert area["sheetId"] == self.id
                assert area["startIndex"] >= 0
                del self.values[area["startIndex"] : area["endIndex"]]
            else:
                update = request["updateCells"]
                assert update["fields"] == "userEnteredValue"
                if not update["rows"]:
                    self.values[update["range"]["startRowIndex"]] = []
                    continue
                assert update["range"]["startColumnIndex"] == 0
                assert update["range"]["endColumnIndex"] == 1
                value = update["rows"][0]["values"][0]["userEnteredValue"][
                    "stringValue"
                ]
                self.values[update["range"]["startRowIndex"]][0] = value


@pytest.fixture
def sheets_recorder(tmp_path):
    sheet = MemoryWorksheet()
    sheets = object.__new__(GoogleSheetsService)
    sheets.worksheet = sheet
    sheets.spreadsheet = sheet
    sheets.spreadsheet_id = "test-sheet"
    recorder = DatasetRecorder(tmp_path / "local.csv")
    recorder.google_sheets = sheets
    recorder.use_google_sheets = True
    return recorder, sheet


def add_rows(sheet):
    sheet.values.extend(
        [
            ["A", "1", '{"s1":1,"s2":2,"s3":3}'],  # No optional IMU cell
            [],  # Physical blank row: preserve its index when deleting later rows
            ["B", "2", '{"s1":10,"s2":20,"s3":30}', "{}"],
            ["A", "3", '{"s1":2,"s2":3,"s3":4}', "{}", "keep extra column"],
            ["", "4", '{"s1":1}', ""],
            ["  ", "5", '{"s1":2}', ""],
        ]
    )


def test_sheets_edits_refresh_and_local_backup(sheets_recorder):
    recorder, sheet = sheets_recorder
    add_rows(sheet)
    assert recorder.stats()["by_label"] == {"A": 2, "B": 1, "": 1, "  ": 1}
    assert recorder.list_rows(label="A", offset=1)["rows"][0]["timestamp"] == "3"
    assert recorder.rename_label("A", "=HELLO") == 2
    assert sheet.values[1][0] == "=HELLO"
    assert sheet.values[4][-1] == "keep extra column"
    assert recorder.delete_label("=HELLO") == 2
    assert len(sheet.batches) == 2
    assert recorder.delete_empty_labels() == 2
    assert recorder.stats()["by_label"] == {"B": 1}
    with recorder.dataset_path.open(newline="", encoding="utf-8") as handle:
        assert [row["gesture"] for row in csv.DictReader(handle)] == ["B"]
    # A change made directly in Sheets must appear on the next refresh.
    sheet.values.append(["EXTERNAL", "6", '{"s1":9}', ""])
    assert recorder.stats()["by_label"] == {"B": 1, "EXTERNAL": 1}
    recorder.clear()
    assert recorder.stats()["total"] == 0
    assert sheet.values[0] == GoogleSheetsService.HEADER


def test_sheets_save_failures_do_not_report_local_success(sheets_recorder):
    recorder, sheet = sheets_recorder
    sample = {"channels": {"s1": 1, "s2": 2, "s3": 3}, "timestamp": 1}
    recorder.save_sample(sample, "A")
    assert recorder.stats()["total"] == 1
    original = recorder.dataset_path.read_bytes()
    sheet.fail_write = True
    with pytest.raises(DatasetStorageError):
        recorder.save_samples([sample], "B")
    with pytest.raises(DatasetStorageError):
        recorder.rename_label("A", "B")
    with pytest.raises(DatasetStorageError):
        recorder.delete_label("A")
    assert recorder.dataset_path.read_bytes() == original
    sheet.fail_read = True
    with pytest.raises(DatasetStorageError):
        recorder.stats()
    assert recorder.dataset_path.read_bytes() == original


def test_headerless_sheet_keeps_first_sample_and_correct_edit_indices(sheets_recorder):
    recorder, sheet = sheets_recorder
    sheet.values = [
        ["FIRST", "1", '{"s1":1,"s2":2,"s3":3}', "{}"],
        ["SECOND", "2", '{"s1":4,"s2":5,"s3":6}', "{}"],
    ]
    assert recorder.stats()["total"] == 2
    assert recorder.rename_label("FIRST", "RENAMED") == 1
    assert sheet.values[0][0] == "RENAMED"
    assert recorder.delete_label("RENAMED") == 1
    assert sheet.values[0][0] == "SECOND"
    recorder.clear()
    assert recorder.stats()["total"] == 0
    recorder.save_sample({"channels": {"s1": 1, "s2": 2, "s3": 3}}, "NEW")
    assert recorder.stats()["by_label"] == {"NEW": 1}


def test_configured_sheets_retries_instead_of_editing_wrong_source(
    tmp_path, monkeypatch
):
    def offline(*args):
        raise ConnectionError("offline")

    monkeypatch.setattr("app.services.dataset_recorder.GoogleSheetsService", offline)
    recorder = DatasetRecorder(tmp_path / "backup.csv", "credentials", "sheet")
    with pytest.raises(DatasetStorageError):
        recorder.clear()


def test_sheets_http_edit_and_refresh_flow(client, app, sheets_recorder):
    recorder, sheet = sheets_recorder
    app.state.dataset_recorder = recorder
    add_rows(sheet)
    response = client.get("/api/dataset/stats")
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["total"] == 5
    renamed = client.post(
        "/api/dataset/rename-label", json={"from_label": "A", "to_label": "HELLO"}
    )
    assert renamed.json()["updated"] == 2
    assert renamed.json()["stats"]["by_label"]["HELLO"] == 2
    assert client.get("/api/dataset/rows?label=HELLO").json()["total"] == 2
    assert (
        client.post("/api/dataset/delete-label", json={"label": ""}).json()["deleted"]
        == 1
    )
    assert (
        client.post("/api/dataset/delete-label", json={"label": "HELLO"}).json()[
            "deleted"
        ]
        == 2
    )
    sheet.fail_read = True
    for url in ("/api/dataset/stats", "/api/dataset/rows"):
        assert client.get(url).status_code == 503
    assert (
        client.post("/api/model/retrain", json={"model_type": "knn"}).status_code == 503
    )
    sheet.fail_read = False
    assert client.post("/api/dataset/clear").json()["stats"]["total"] == 0


def test_training_uses_fresh_sheet_not_stale_csv(client, app, sheets_recorder):
    recorder, sheet = sheets_recorder
    app.state.dataset_recorder = recorder
    for label, base in (("REMOTE_A", 0), ("REMOTE_B", 100)):
        for i in range(10):
            sheet.values.append(
                [
                    label,
                    str(i),
                    json.dumps({"s1": base + i, "s2": base + 2, "s3": base + 3}),
                ]
            )
    response = client.post("/api/model/retrain", json={"model_type": "decision_tree"})
    assert response.status_code == 200, response.text
    metrics = response.json()["metrics"]
    assert metrics["dataset_source"] == "google_sheets"
    assert metrics["classes"] == ["REMOTE_A", "REMOTE_B"]
