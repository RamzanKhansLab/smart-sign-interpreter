from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from dataset_tools.dataset_builder import append_row


def parse_serial_line(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    try:
        if line.startswith("{"):
            return json.loads(line)
        parts = [p.strip() for p in line.split(",")]
        if len(parts) not in (5, 6):
            return None
        values = list(map(int, parts))
        data = {
            "flex1": values[0],
            "flex2": values[1],
            "flex3": values[2],
            "flex4": values[3],
            "flex5": values[4],
        }
        if len(values) == 6:
            data["timestamp"] = values[5]
        else:
            data["timestamp"] = int(time.time() * 1000)
        return data
    except Exception:
        return None


def run_serial(args):
    try:
        import serial
    except ImportError as exc:
        raise SystemExit("pyserial is required for serial mode") from exc

    dataset_path = Path(args.dataset)
    recorded = 0

    with serial.Serial(args.port, args.baud, timeout=1) as ser:
        print("Recording from serial. Press Ctrl+C to stop.")
        while True:
            line = ser.readline().decode("utf-8", errors="ignore")
            payload = parse_serial_line(line)
            if payload is None:
                continue
            payload["gesture"] = args.gesture
            append_row(dataset_path, payload)
            recorded += 1
            print(f"Recorded {recorded}: {payload}")
            if args.count and recorded >= args.count:
                break


def make_handler(dataset_path: Path, gesture: str):
    class RecordHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/record":
                self.send_response(404)
                self.end_headers()
                return

            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body)
                if not isinstance(payload, dict):
                    raise ValueError("Invalid payload")
            except Exception:
                self.send_response(400)
                self.end_headers()
                return

            payload["gesture"] = gesture
            if "timestamp" not in payload:
                payload["timestamp"] = int(time.time() * 1000)
            append_row(dataset_path, payload)

            response = json.dumps({"status": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    return RecordHandler


def run_http(args):
    dataset_path = Path(args.dataset)
    handler = make_handler(dataset_path, args.gesture)
    server = ThreadingHTTPServer((args.listen_host, args.listen_port), handler)
    print(
        f"HTTP recording server running on http://{args.listen_host}:{args.listen_port}/record"
    )
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Record gesture dataset samples.")
    parser.add_argument("--gesture", required=True, help="Gesture label")
    parser.add_argument(
        "--dataset",
        default=str(ROOT / "data" / "datasets" / "gesture_dataset.csv"),
        help="Dataset CSV path",
    )
    parser.add_argument(
        "--source",
        choices=["serial", "http"],
        default="serial",
        help="Data source",
    )
    parser.add_argument("--port", default="COM3", help="Serial port")
    parser.add_argument("--baud", type=int, default=9600, help="Serial baud rate")
    parser.add_argument("--count", type=int, default=0, help="Stop after N samples")
    parser.add_argument("--listen-host", default="0.0.0.0", help="HTTP host")
    parser.add_argument("--listen-port", type=int, default=6000, help="HTTP port")

    args = parser.parse_args()
    if args.source == "serial":
        run_serial(args)
    else:
        run_http(args)


if __name__ == "__main__":
    main()
