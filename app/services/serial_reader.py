from __future__ import annotations

import json
import time

import serial


def parse_serial_line(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None

    try:
        if line.startswith("{"):
            payload = json.loads(line)
            if not isinstance(payload, dict):
                return None
            if "channels" in payload:
                return payload
            flex_keys = ["flex1", "flex2", "flex3", "flex4", "flex5"]
            if all(k in payload for k in flex_keys):
                payload = {
                    "channels": {
                        "s1": payload["flex1"],
                        "s2": payload["flex2"],
                        "s3": payload["flex3"],
                        "s4": payload["flex4"],
                        "s5": payload["flex5"],
                    },
                    "timestamp": payload.get("timestamp") or int(time.time() * 1000),
                }
                return payload
            return payload

        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < 3:
            return None

        values = list(map(float, parts))
        channels = {f"s{i + 1}": values[i] for i in range(min(len(values), 5))}

        imu = None
        if len(values) >= 11:
            imu = {
                "ax": values[5],
                "ay": values[6],
                "az": values[7],
                "gx": values[8],
                "gy": values[9],
                "gz": values[10],
            }

        return {"channels": channels, "imu": imu, "timestamp": int(time.time() * 1000)}
    except Exception:
        return None


class SerialReader:
    def __init__(self, port: str, baud: int, pipeline) -> None:
        self.port = port
        self.baud = baud
        self.pipeline = pipeline
        self._thread = None
        self._stop_event = None

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return False
        import threading

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        if self._stop_event:
            self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        try:
            with serial.Serial(self.port, self.baud, timeout=1) as ser:
                while self._stop_event and not self._stop_event.is_set():
                    raw = ser.readline().decode("utf-8", errors="ignore")
                    payload = parse_serial_line(raw)
                    if not payload:
                        continue
                    try:
                        self.pipeline.process_sensor_data(payload, source="serial")
                    except Exception:
                        import logging

                        logging.getLogger("ssi").warning(
                            "serial_payload_invalid",
                            extra={"extra": {"payload": payload}},
                        )
        except Exception:
            import logging

            logging.getLogger("ssi").exception("serial_reader_error")
