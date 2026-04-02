from __future__ import annotations

import asyncio
import logging
import threading
import time

from app.schemas import RawSensorData


class SensorPipeline:
    def __init__(self, ws_manager, ml_service) -> None:
        self.ws_manager = ws_manager
        self.ml_service = ml_service
        self.latest_data: dict | None = None
        self.latest_message: dict | None = None
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _model_dump(self, data: RawSensorData) -> dict:
        if hasattr(data, "model_dump"):
            return data.model_dump()
        return data.dict()

    def _normalize_payload(self, payload: dict) -> dict:
        channels = payload.get("channels")
        if isinstance(channels, list):
            payload["channels"] = {f"s{i + 1}": float(v) for i, v in enumerate(channels)}
        if payload.get("timestamp") is None:
            payload["timestamp"] = int(time.time() * 1000)
        return payload

    def process_sensor_data(self, data: dict | RawSensorData, source: str) -> dict:
        if isinstance(data, dict):
            data = RawSensorData(**data)

        payload = self._normalize_payload(self._model_dump(data))

        with self._lock:
            self.latest_data = payload

        prediction = self.ml_service.predict(payload) if self.ml_service else None

        message = {
            "data": payload,
            "prediction": prediction,
            "model_loaded": self.ml_service.loaded,
            "source": source,
        }

        with self._lock:
            self.latest_message = message

        logging.getLogger("ssi").info(
            "sensor_processed",
            extra={"extra": {"source": source, "prediction": prediction}},
        )
        self._broadcast(message)
        return message

    def get_latest_message(self) -> dict | None:
        with self._lock:
            return self.latest_message

    def _broadcast(self, message: dict) -> None:
        if not self._loop or not self._loop.is_running():
            return
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop and running_loop == self._loop:
            asyncio.create_task(self.ws_manager.broadcast(message))
        else:
            asyncio.run_coroutine_threadsafe(
                self.ws_manager.broadcast(message), self._loop
            )
