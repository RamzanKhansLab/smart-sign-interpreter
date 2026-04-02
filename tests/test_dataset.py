from __future__ import annotations

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
