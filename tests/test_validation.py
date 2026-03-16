from __future__ import annotations

from app.validators import ValidationError, validate_sensor_payload


def test_validate_sensor_payload_ok():
    payload = {
        "thumb": 840,
        "index": 210,
        "middle": 205,
        "ring": 220,
        "little": 230,
    }
    result = validate_sensor_payload(payload)
    assert result["thumb"] == 840


def test_validate_sensor_payload_missing():
    payload = {"thumb": 100}
    try:
        validate_sensor_payload(payload)
    except ValidationError as exc:
        assert "missing:index" in exc.errors
    else:
        raise AssertionError("Expected ValidationError")


def test_validate_sensor_payload_out_of_range():
    payload = {
        "thumb": 2000,
        "index": 210,
        "middle": 205,
        "ring": 220,
        "little": 230,
    }
    try:
        validate_sensor_payload(payload)
    except ValidationError as exc:
        assert "out_of_range:thumb" in exc.errors
    else:
        raise AssertionError("Expected ValidationError")
