# Smart Sign Language Glove Backend

## Project Overview

This backend ingests **generic raw sensor data** from a sign-language glove over HTTP (WiFi), streams live predictions to a minimal Jinja2 UI, and stores labeled datasets for easy retraining.

## System Architecture

Components:

- FastAPI backend with REST + WebSocket
- Unified processing pipeline
- Dataset recorder (CSV)
- Optional ML prediction service
- Minimal Jinja2 tools (Interpretation + Data Collection)

Data flow diagram:

```
Sensors -> ATmega328P -> (WiFi HTTP / USB Serial)
       -> FastAPI Backend -> Processing Pipeline
       -> Dataset CSV / ML Model -> Web Dashboard
```

## Hardware Setup

The backend expects a generic payload:

- **`channels`**: at least 3 readings (hall sensors, flex sensors, etc.)
- **`imu`** (optional): MPU6050 accelerometer/gyro (ax/ay/az/gx/gy/gz)
- **`timestamp`** (optional): milliseconds since epoch

Example accepted JSON:

```json
{
  "channels": { "s1": 100, "s2": 200, "s3": 300, "s4": 400, "s5": 500 },
  "imu": { "ax": 0.01, "ay": 0.02, "az": 0.98, "gx": 1.2, "gy": 0.3, "gz": 0.1 },
  "timestamp": 1710000000000
}
```

## Backend Server Setup

```bash
pip install -r requirements.txt
```

Run the server (recommended):

```bash
python -m app
```

Run the server (uvicorn):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Dashboard:

```
http://localhost:8000/
```

WebSocket stream:

```
ws://localhost:8000/ws/sensor-stream
```

## If “data is not coming” on localhost

The dashboard only shows data **after** something sends packets to `POST /api/sensor-data`.

Options:

- Use the Home page button: **SEND DEMO PACKET** (enabled by `ENABLE_DEMO=true` in `.env`)
- Run the simulator:

```bash
python scripts/simulate_glove_sender.py --random --count 20
```

If your glove is on WiFi, make sure it posts to your PC’s LAN IP (not `localhost`). Example:

```
http://<YOUR_PC_IP>:8000/api/sensor-data
```

## Docker (optional)

```bash
docker compose up --build
```

## WiFi Mode Usage

Send HTTP packets to:

```
POST /api/sensor-data
```

Example:

```bash
curl -X POST http://localhost:8000/api/sensor-data \
  -H "Content-Type: application/json" \
  -d '{"channels":{"s1":100,"s2":200,"s3":300,"s4":400,"s5":500},"timestamp":1710000000000}'
```

## Dataset Collection Tool

Dataset file path:

```
data/datasets/gesture_dataset.csv
```

Data Collection tool:

- Open `http://localhost:8000/collect`
- Click **START** to buffer one sample every 2 seconds (from `/api/latest`)
- Click **STOP**, enter the label, then **SAVE** (writes to the CSV)
- Use **RESET MODEL** and **RETRAIN** to rebuild the model from the saved dataset

Interpretation tool:

- Open `http://localhost:8000/interpret`
- Shows live channels + predicted gesture (via WebSocket)

## ML Training Workflow

Use the **RETRAIN** button in the Data Collection tool (recommended).

## Testing Instructions

```bash
pytest
```
