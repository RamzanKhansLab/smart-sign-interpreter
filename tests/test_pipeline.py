from __future__ import annotations

from app.services.processing import SensorPipeline


def test_pipeline_adds_timestamp():
    class DummyWS:
        async def broadcast(self, message):
            pass

    class DummyML:
        loaded = False

        def predict(self, data):
            return None

    pipeline = SensorPipeline(DummyWS(), DummyML())
    message = pipeline.process_sensor_data(
        {"channels": {"s1": 1, "s2": 2, "s3": 3}},
        source="http",
    )
    assert message["data"]["timestamp"] is not None
