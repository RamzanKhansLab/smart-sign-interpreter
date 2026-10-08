"""Persisted, reproducible classification metrics and server-side Matplotlib plots."""

from __future__ import annotations

import threading
from io import BytesIO

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)

_PLOT_LOCK = threading.Lock()


def classification_metrics(y_true, y_pred, labels: list[str]) -> dict:
    report = classification_report(
        y_true, y_pred, labels=labels, output_dict=True, zero_division=0
    )
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(report["macro avg"]["precision"]),
        "recall": float(report["macro avg"]["recall"]),
        "f1": float(report["macro avg"]["f1-score"]),
        "weighted_precision": float(report["weighted avg"]["precision"]),
        "weighted_recall": float(report["weighted avg"]["recall"]),
        "weighted_f1": float(report["weighted avg"]["f1-score"]),
        # Class names may themselves be 'accuracy' or 'macro avg'; sklearn's
        # report dictionary reserves those keys for summary values.
        "per_class": [
            {
                "label": label,
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1-score": float(f1[index]),
                "support": int(support[index]),
            }
            for index, label in enumerate(labels)
        ],
        "classification_report": report,
        "report": classification_report(y_true, y_pred, labels=labels, zero_division=0),
        "classes": labels,
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "evaluation_samples": len(y_true),
    }


def confusion_matrix_png(metrics: dict) -> bytes:
    """Use Agg without pyplot/global figure state, including on headless servers."""
    labels = metrics["classes"]
    matrix = np.asarray(metrics["confusion_matrix"], dtype=int)
    with _PLOT_LOCK:
        side = min(24, max(6, len(labels) * 0.7))
        figure = Figure(figsize=(side + 1, side), layout="constrained")
        FigureCanvasAgg(figure)
        ax = figure.subplots()
        plot = ax.imshow(matrix, interpolation="nearest", cmap="Blues")
        figure.colorbar(plot, ax=ax, label="Sample count")
        ax.set(
            xticks=np.arange(len(labels)),
            yticks=np.arange(len(labels)),
            xticklabels=labels,
            yticklabels=labels,
            xlabel="Predicted label",
            ylabel="True label",
            title=f"{metrics['model_type']} — {metrics['evaluation_label']}",
        )
        ax.tick_params(axis="x", labelrotation=45)
        for tick in ax.get_xticklabels():
            tick.set_horizontalalignment("right")
        threshold = matrix.max() / 2 if matrix.size else 0
        for row in range(len(labels)):
            for col in range(len(labels)):
                ax.text(
                    col,
                    row,
                    str(matrix[row, col]),
                    ha="center",
                    va="center",
                    color="white" if matrix[row, col] > threshold else "black",
                    fontsize=max(5, min(12, 100 / max(1, len(labels)))),
                )
        output = BytesIO()
        figure.savefig(output, format="png", dpi=140)
        return output.getvalue()
