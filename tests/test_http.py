from __future__ import annotations


def test_http_sensor_endpoint(client):
    payload = {
        "channels": {"s1": 100, "s2": 200, "s3": 300, "s4": 400, "s5": 500},
        "timestamp": 123456,
    }
    response = client.post("/api/sensor-data", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["channels"]["s1"] == 100
    assert data["source"] == "http"


def test_dataset_save_flow(client):
    payload = {
        "channels": {"s1": 101, "s2": 202, "s3": 303},
        "timestamp": 123457,
    }
    client.post("/api/sensor-data", json=payload)
    save = client.post("/api/dataset/save-latest", json={"label": "HELLO"})
    assert save.status_code == 200
    stats = client.get("/api/dataset/stats").json()
    assert stats["total"] >= 1
