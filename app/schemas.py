from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

try:
    from pydantic import ConfigDict, field_validator
except ImportError:  # pragma: no cover - fallback for older Pydantic
    ConfigDict = None
    field_validator = None


class ImuData(BaseModel):
    if ConfigDict:
        model_config = ConfigDict(extra="forbid")

    ax: Optional[float] = None
    ay: Optional[float] = None
    az: Optional[float] = None
    gx: Optional[float] = None
    gy: Optional[float] = None
    gz: Optional[float] = None

    if field_validator:

        @field_validator("ax", "ay", "az", "gx", "gy", "gz")
        def reject_bool(cls, value):
            if isinstance(value, bool):
                raise ValueError("boolean values are not allowed")
            return value


ChannelsInput = Union[Dict[str, float], List[float]]


class RawSensorData(BaseModel):
    """Generic sensor payload.

    `channels` is the only required field and should contain at least 3 sensor
    readings (hall sensors, flex sensors, etc). Optional sensors can be included
    either as extra channel keys or via the optional `imu` object.

    Accepted `channels` formats:
    - Dict: {"s1": 123, "s2": 456, "s3": 789, "s4": 12, "s5": 34}
    - List: [123, 456, 789, 12, 34] (mapped to s1..sN)

    The ML pipeline learns feature keys from the dataset. If an optional sensor
    has no values in the dataset, it will be ignored automatically.
    """

    if ConfigDict:
        model_config = ConfigDict(extra="forbid")

    channels: ChannelsInput = Field(..., description="At least 3 sensor readings")
    imu: Optional[ImuData] = None
    timestamp: Optional[int] = Field(default=None, ge=0)

    if field_validator:

        @field_validator("channels")
        def validate_channels(cls, value: Any):
            if isinstance(value, bool):
                raise ValueError("boolean values are not allowed")

            if isinstance(value, list):
                if len(value) < 3:
                    raise ValueError("channels must contain at least 3 values")
                if any(isinstance(v, bool) for v in value):
                    raise ValueError("boolean values are not allowed")
                return value

            if isinstance(value, dict):
                if len(value) < 3:
                    raise ValueError("channels must contain at least 3 entries")
                for key, v in value.items():
                    if not isinstance(key, str) or not key:
                        raise ValueError("channels keys must be non-empty strings")
                    if isinstance(v, bool):
                        raise ValueError("boolean values are not allowed")
                return value

            raise ValueError("channels must be a dict or list")

        @field_validator("timestamp")
        def reject_bool_timestamp(cls, value):
            if isinstance(value, bool):
                raise ValueError("boolean values are not allowed")
            return value


class SensorDataResponse(BaseModel):
    data: RawSensorData
    prediction: Optional[str]
    model_loaded: bool
    source: str


class LabelRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=64)


class SaveBatchRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=64)
    samples: List[RawSensorData] = Field(..., min_length=1, max_length=10000)


class RetrainRequest(BaseModel):
    model_type: str = Field(default="knn")
