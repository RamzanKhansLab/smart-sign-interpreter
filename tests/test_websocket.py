from __future__ import annotations

from fastapi.testclient import TestClient


def test_websocket_stream(client: TestClient):
    payload = {
        "channels": {"s1": 111, "s2": 222, "s3": 333, "s4": 444, "s5": 555},
        "timestamp": 999,
    }

    with client.websocket_connect("/ws/sensor-stream") as websocket:
        client.post("/api/sensor-data", json=payload)
        message = websocket.receive_json()
        assert message["data"]["channels"]["s1"] == 111
