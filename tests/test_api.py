from __future__ import annotations


def test_gesture_endpoint_ok(client):
    payload = {
        "thumb": 840,
        "index": 210,
        "middle": 205,
        "ring": 220,
        "little": 230,
    }
    response = client.post("/gesture", json=payload)
    assert response.status_code == 200
    assert "gesture" in response.get_json()


def test_gesture_endpoint_invalid(client):
    response = client.post("/gesture", json={"thumb": 1})
    assert response.status_code == 400
    assert response.get_json()["error"] == "validation_error"
