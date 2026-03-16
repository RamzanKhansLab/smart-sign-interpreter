from __future__ import annotations

from dataclasses import dataclass

SENSOR_FIELDS = ["thumb", "index", "middle", "ring", "little"]
MIN_VALUE = 0
MAX_VALUE = 1023


@dataclass
class ValidationError(Exception):
    message: str
    errors: list[str] | None = None
    status_code: int = 400

    def __str__(self) -> str:
        return self.message


def validate_sensor_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("Payload must be a JSON object")

    errors: list[str] = []
    data: dict = {}

    for field in SENSOR_FIELDS:
        if field not in payload:
            errors.append(f"missing:{field}")
            continue
        value = payload[field]
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"invalid_type:{field}")
            continue
        if value < MIN_VALUE or value > MAX_VALUE:
            errors.append(f"out_of_range:{field}")
            continue
        data[field] = value

    if errors:
        raise ValidationError("Invalid sensor data", errors=errors)

    return data
