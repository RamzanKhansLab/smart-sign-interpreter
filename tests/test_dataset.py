from __future__ import annotations

from ml.dataset_loader import load_dataset
from dataset_tools.dataset_builder import append_row


def test_append_row_and_load_dataset(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    append_row(
        dataset_path,
        {
            "thumb": 840,
            "index": 210,
            "middle": 205,
            "ring": 220,
            "little": 230,
            "gesture": "HELLO",
        },
    )

    X, y, _ = load_dataset(dataset_path)
    assert X.shape[0] == 1
    assert y[0] == "HELLO"
