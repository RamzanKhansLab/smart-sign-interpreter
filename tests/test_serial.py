from __future__ import annotations

import time

from app.services.serial_reader import SerialReader, parse_serial_line


def test_parse_serial_line_csv():
    payload = parse_serial_line("10,20,30,40,50")
    assert payload["channels"]["s1"] == 10.0
    assert payload["timestamp"] is not None


def test_serial_reader(monkeypatch):
    messages = []

    class DummyPipeline:
        def process_sensor_data(self, payload, source):
            messages.append((payload, source))

    class DummySerial:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        def readline(self):
            self.calls += 1
            if self.calls == 1:
                return b"1,2,3,4,5\n"
            time.sleep(0.01)
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    import app.services.serial_reader as sr

    monkeypatch.setattr(sr.serial, "Serial", DummySerial)

    reader = SerialReader("COM_TEST", 9600, DummyPipeline())
    started = reader.start()
    assert started is True
    time.sleep(0.05)
    reader.stop()

    assert messages
    assert messages[0][1] == "serial"
