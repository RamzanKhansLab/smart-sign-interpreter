from __future__ import annotations

from sklearn.metrics import accuracy_score, classification_report


def evaluate_model(model, X_test, y_test):
    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)
    report = classification_report(
        y_test,
        predictions,
        output_dict=True,
        zero_division=0,
    )
    return accuracy, report
