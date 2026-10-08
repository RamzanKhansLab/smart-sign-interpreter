"""Optional browser verification: python tests/browser_smoke.py.

Requires playwright (pip install playwright). Uses headless Chrome and a temporary
dataset/model with an in-memory Google Sheets boundary; never changes live data.
"""

from __future__ import annotations

import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import uvicorn
    from playwright.sync_api import expect, sync_playwright

    with tempfile.TemporaryDirectory(prefix="sign-browser-") as directory:
        os.environ.update(
            GOOGLE_CREDENTIALS_PATH="",
            GOOGLE_SPREADSHEET_ID="",
            DATASET_PATH=str(Path(directory) / "dataset.csv"),
            MODEL_PATH=str(Path(directory) / "model.pkl"),
            ALLOW_MISSING_MODEL="true",
        )
        from test_dataset_sheets import MemoryWorksheet

        from app.main import create_app
        from app.services.google_sheets_service import GoogleSheetsService

        app = create_app()
        sheet = MemoryWorksheet()
        sheet.values = []  # Match the existing live worksheet's headerless layout.
        sheets = object.__new__(GoogleSheetsService)
        sheets.worksheet = sheet
        sheets.spreadsheet = sheet
        sheets.spreadsheet_id = "browser-test"
        app.state.dataset_recorder.google_sheets = sheets
        app.state.dataset_recorder.use_google_sheets = True
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.monotonic() + 20
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.started
        base = f"http://127.0.0.1:{port}"
        screenshots = ROOT / ".pytest_cache" / "browser"
        screenshots.mkdir(parents=True, exist_ok=True)
        errors = []
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                page = browser.new_page(viewport={"width": 1365, "height": 1000})
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("dialog", lambda dialog: dialog.accept())
                page.goto(base + "/collect")
                expect(page.locator("#dataset-stats")).to_contain_text('"total": 0')
                response = page.request.post(
                    base + "/api/sensor-data",
                    data={"channels": {"s1": 10, "s2": 20, "s3": 30}, "timestamp": 123},
                )
                assert response.ok
                expect(page.locator("#s1")).to_have_text("10")
                page.locator("#gesture-label").fill("HELLO")
                page.locator("#start").click()
                expect(page.locator("#buffer-count")).to_have_text("1")
                page.locator("#stop").click()
                page.locator("#save").click()
                expect(page.locator("#dataset-stats")).to_contain_text('"HELLO": 1')
                assert [row[0] for row in sheet.values if row] == ["HELLO"]
                page.locator("#edit-label").select_option("HELLO")
                page.locator("#rename-to").fill("RENAMED")
                page.locator("#label-rename").click()
                expect(page.locator("#dataset-rows")).to_contain_text("RENAMED")
                assert [row[0] for row in sheet.values if row] == ["RENAMED"]
                page.locator("#label-delete").click()
                expect(page.locator("#dataset-stats")).to_contain_text('"total": 0')
                assert not any(any(row) for row in sheet.values)
                # A user edits the sheet outside the app, then refreshes statistics.
                sheet.values.append(["EXTERNAL", "456", '{"s1":1,"s2":2,"s3":3}'])
                page.locator("#refresh-stats").click()
                expect(page.locator("#dataset-stats")).to_contain_text('"EXTERNAL": 1')
                sheet.fail_read = True
                page.locator("#refresh-stats").click()
                expect(page.locator("#dataset-stats")).to_contain_text("Refresh failed")
                sheet.fail_read = False
                page.locator("#refresh-stats").click()
                expect(page.locator("#dataset-stats")).to_contain_text('"EXTERNAL": 1')
                page.locator("#dataset-clear").click()
                expect(page.locator("#dataset-stats")).to_contain_text('"total": 0')
                for label, base_value in (("HELLO", 0), ("YES", 100)):
                    response = page.request.post(
                        base + "/api/dataset/save-batch",
                        data={
                            "label": label,
                            "samples": [
                                {
                                    "channels": {
                                        "s1": base_value + i,
                                        "s2": base_value + i,
                                        "s3": base_value + i,
                                    }
                                }
                                for i in range(20)
                            ],
                        },
                    )
                    assert response.ok
                page.locator("#model-retrain").click()
                expect(page.locator("#model-loaded")).to_have_text("YES", timeout=30000)
                page.get_by_role("link", name="Model Performance").click()
                expect(page.locator("#metric-accuracy")).to_have_text(
                    "100.00%", timeout=30000
                )
                expect(page.locator("#confusion-matrix")).to_be_visible(timeout=30000)
                expect(page.locator("#classification-rows tr")).to_have_count(2)
                first_run = page.locator("#training-run").input_value()
                with page.expect_download() as download:
                    page.locator("#download-matrix").click()
                assert Path(download.value.path()).read_bytes().startswith(b"\x89PNG")
                # Training elsewhere becomes visible on refresh without losing history.
                response = page.request.post(
                    base + "/api/model/retrain", data={"model_type": "random_forest"}
                )
                assert response.ok
                newest = response.json()["metrics"]["run_id"]
                page.locator("#refresh-metrics").click()
                expect(page.locator("#training-run")).to_have_value(
                    newest, timeout=30000
                )
                expect(page.locator("#training-run option")).to_have_count(2)
                page.locator("#training-run").select_option(first_run)
                expect(page.locator("#evaluation-details")).to_contain_text(
                    "historical result"
                )
                page.reload()
                expect(page.locator("#training-run")).to_have_value(
                    newest, timeout=30000
                )
                expect(page.locator("#confusion-matrix")).to_be_visible(timeout=30000)
                page.screenshot(
                    path=str(screenshots / "performance-desktop.png"), full_page=True
                )
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth"
                )
                page.screenshot(
                    path=str(screenshots / "performance-mobile.png"), full_page=True
                )
                page.request.post(base + "/api/model/reset")
                page.locator("#refresh-metrics").click()
                expect(page.locator("#metrics-status")).to_contain_text(
                    "No active model"
                )
                expect(page.locator("#training-run option")).to_have_count(2)
                browser.close()
            assert not errors, errors
            print(
                "Browser checks passed: capture/save, Sheets rename/delete/refresh/"
                "error recovery, training, history, reload, PNG download, "
                "mobile layout, and reset."
            )
            print(f"Screenshots: {screenshots}")
        finally:
            server.should_exit = True
            thread.join(timeout=10)


if __name__ == "__main__":
    main()
