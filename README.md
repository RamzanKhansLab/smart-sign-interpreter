# SMART SIGN LANGUAGE INTERPRETER

Production-grade Flask backend for a smart sign language interpreter that receives gesture glove sensor data, predicts gestures using lightweight ML models, and optionally speaks the result.

## Overview

This backend:

- Accepts HTTP POST sensor payloads
- Validates sensor values (0–1023 integers)
- Predicts gestures using a trained scikit-learn model
- Optionally performs text-to-speech using `pyttsx3`
- Includes dataset tooling, model training, and retraining automation
- Provides CI, tests, and structured logging

## Architecture (High Level)

- `app/` Flask API server and services
- `ml/` Training and retraining pipeline
- `dataset_tools/` Recording and labeling tools
- `scripts/` Simulation utilities
- `tests/` Pytest suite

## Hardware Communication Flow

1. Glove sends sensor data via HTTP or serial.
2. Backend validates payload.
3. Values are transformed into model input.
4. Model predicts gesture label.
5. Response returned as JSON.
6. Optional TTS output (speaker).

## Example Request

```json
{
  "thumb": 840,
  "index": 210,
  "middle": 205,
  "ring": 220,
  "little": 230
}
```

## Example Response

```json
{
  "gesture": "HELLO"
}
```

## Setup

```bash
pip install -r requirements.txt
```

Create/update `.env` with:

```bash
FLASK_PORT=5000
MODEL_PATH=models/gesture_model.pkl
ENABLE_TTS=false
```

## Train Model

```bash
python ml/train_model.py
```

Model is saved to `models/gesture_model.pkl`.

## Run Backend

```bash
python app/server.py
```

## Run Tests

```bash
pytest
```

## Simulate Glove Input

```bash
python scripts/simulate_glove_sender.py --url http://localhost:5000/gesture --count 10
```

## Dataset Recording

### Serial Mode

```bash
python dataset_tools/record_gesture.py --gesture HELLO --source serial --port COM3 --baud 9600
```

### HTTP Mode

```bash
python dataset_tools/record_gesture.py --gesture HELLO --source http --listen-port 6000
```

Send POST requests to `http://localhost:6000/record` with the sensor payload.

## Model Retraining

```bash
python ml/retrain_model.py
```

## CI/CD

- `ci.yml` runs lint + tests
- `retrain.yml` retrains model on dataset changes and commits updated model
