from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from flask import Flask, jsonify, request

# Allow import from project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.validators import ValidationError, validate_sensor_payload
from dataset_tools.dataset_builder import append_row


def parse_serial_line(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    try:
        if line.startswith("{"):
            return json.loads(line)
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 5:
            return None
        values = list(map(int, parts))
        return {
            "thumb": values[0],
            "index": values[1],
            "middle": values[2],
            "ring": values[3],
            "little": values[4],
        }
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
            try:
                sensors = validate_sensor_payload(payload)
                sensors["gesture"] = args.gesture
                append_row(dataset_path, sensors)
                recorded += 1
                print(f"Recorded {recorded}: {sensors}")
                if args.count and recorded >= args.count:
                    break
            except ValidationError as exc:
                print(f"Invalid data: {exc}")


def run_http(args):
    app = Flask(__name__)
    dataset_path = Path(args.dataset)
    recorded = {"count": 0}

    @app.route("/record", methods=["POST"])
    def record():
        try:
            payload = request.get_json(silent=True)
            if payload is None:
                raise ValidationError("Invalid or missing JSON body")
            sensors = validate_sensor_payload(payload)
            sensors["gesture"] = args.gesture
            append_row(dataset_path, sensors)
            recorded["count"] += 1
            return jsonify({"status": "ok", "count": recorded["count"]})
        except ValidationError as exc:
            return jsonify({"error": "validation_error", "details": exc.errors}), 400

    print(
        f"HTTP recording server running on http://{args.listen_host}:{args.listen_port}/record"
    )
    app.run(host=args.listen_host, port=args.listen_port)


def main():
    parser = argparse.ArgumentParser(description="Record gesture dataset samples.")
    parser.add_argument("--gesture", required=True, help="Gesture label")
    parser.add_argument(
        "--dataset",
        default=str(ROOT / "data" / "dataset.csv"),
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
