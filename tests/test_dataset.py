from __future__ import annotations

import csv

from app.services.dataset_recorder import DatasetRecorder


def test_dataset_recorder(tmp_path):
    recorder = DatasetRecorder(tmp_path / "dataset.csv")
    sample = {
        "channels": {"s1": 1, "s2": 2, "s3": 3},
        "timestamp": 111,
    }
    recorder.save_sample(sample, "A")
    recorder.save_samples([sample, sample], "B")
    stats = recorder.stats()
    assert stats["total"] == 3
    assert stats["by_label"]["A"] == 1
    assert stats["by_label"]["B"] == 2


def test_dataset_recorder_repairs_empty_existing_file(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    dataset_path.write_text("", encoding="utf-8")

    recorder = DatasetRecorder(dataset_path)
    recorder.save_sample({"channels": {"s1": 1, "s2": 2, "s3": 3}, "timestamp": 123}, "A")

    with dataset_path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[0] == ["gesture", "timestamp", "channels", "imu"]
    assert len(rows) == 2
    assert recorder.stats()["by_label"]["A"] == 1


def test_dataset_recorder_repairs_headerless_rows(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    with dataset_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["HELLO", "111", '{"s1":1,"s2":2,"s3":3}', "{}"])

    recorder = DatasetRecorder(dataset_path)

    with dataset_path.open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[0] == ["gesture", "timestamp", "channels", "imu"]
    assert rows[1][0] == "HELLO"
    assert recorder.stats()["total"] == 1
