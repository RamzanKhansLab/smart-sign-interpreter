from __future__ import annotations

import argparse
import json
import random
import time

import requests

DEFAULT_PACKET = {
    "flex1": 840,
    "flex2": 210,
    "flex3": 205,
    "flex4": 220,
    "flex5": 230,
    "timestamp": 0,
}


def generate_random_packet() -> dict:
    packet = {key: random.randint(0, 1023) for key in DEFAULT_PACKET.keys()}
    packet["timestamp"] = int(time.time() * 1000)
    return packet


def main():
    parser = argparse.ArgumentParser(description="Simulate glove sensor sender.")
    parser.add_argument(
        "--url",
        default="http://localhost:8000/api/sensor-data",
        help="Backend URL",
    )
    parser.add_argument("--count", type=int, default=10, help="Number of packets")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between")
    parser.add_argument("--random", action="store_true", help="Send random packets")
    parser.add_argument(
        "--packet-file",
        help="JSON file containing a packet to send",
    )

    args = parser.parse_args()

    packet = DEFAULT_PACKET
    if args.packet_file:
        with open(args.packet_file, "r", encoding="utf-8") as handle:
            packet = json.load(handle)

    for i in range(args.count):
        payload = generate_random_packet() if args.random else packet
        if "timestamp" not in payload:
            payload["timestamp"] = int(time.time() * 1000)
        response = requests.post(args.url, json=payload, timeout=5)
        print(f"{i + 1}: {response.status_code} {response.text}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
