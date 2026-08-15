# Smart Sign Language Glove Backend

## Project Overview

This backend ingests **generic raw sensor data** from a sign-language glove over HTTP (WiFi), streams live predictions to a minimal Jinja2 UI, and stores labeled datasets for easy retraining.

**New Feature:** Data is now automatically persisted to **Google Sheets**, ensuring data survival across server restarts and Render sleep mode!

## Documentation

- **[Google Sheets Setup Guide](GOOGLE_SHEETS_SETUP.md)** - Detailed setup instructions for persistent data storage
- **[Render Deployment Guide](RENDER_DEPLOYMENT.md)** - Step-by-step deployment on Render with Google Sheets

## System Architecture

Components:

- FastAPI backend with REST + WebSocket
- Unified processing pipeline
- Dataset recorder (CSV + Google Sheets)
- Optional ML prediction service
- Minimal Jinja2 tools (Interpretation + Data Collection)

Data flow diagram:

```
Sensors -> ATmega328P -> (WiFi HTTP / USB Serial)
       -> FastAPI Backend -> Processing Pipeline
       -> Dataset (CSV/Google Sheets) / ML Model -> Web Dashboard
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

## Google Sheets Integration for Persistent Data Storage

By default, training data is stored locally in `data/datasets/gesture_dataset.csv`, which **gets deleted when the Render deployment goes to sleep** or is restarted.

To ensure your training data persists, configure Google Sheets integration:

### Setup Instructions

1. **Create a Google Cloud Project:**
   - Go to https://console.cloud.google.com/
   - Create a new project (name it anything, e.g., "smart-sign-interpreter")

2. **Create a Service Account:**
   - In your project, go to **Service Accounts** (search in the top search bar)
   - Click **Create Service Account**
   - Fill in the details and click **Create and Continue**
   - Click **Create Key** → **JSON** → **Create**
   - A JSON file will be downloaded - **keep this safe!**
   - This is your `GOOGLE_CREDENTIALS_PATH` file

3. **Enable Google Sheets API:**
   - In your Cloud project, go to **APIs & Services** → **Enabled APIs & Services**
   - Click **+ Enable APIs and Services**
   - Search for **"Google Sheets API"** → Click it → Click **Enable**
   - Repeat for **"Google Drive API"**

4. **Create a Google Sheet:**
   - Go to https://sheets.google.com/
   - Create a new blank spreadsheet (name it "gesture_dataset" or anything)
   - Copy the spreadsheet ID from the URL: `https://docs.google.com/spreadsheets/d/**SPREADSHEET_ID**/edit...`
   - Click **Share** and add your service account email (found in the JSON credentials file)
   - Give it **Editor** access

5. **Configure Environment Variables:**
   - Copy `.env.example` to `.env` (if not already done)
   - Add your credentials to `.env`:
   ```env
   GOOGLE_CREDENTIALS_PATH=/path/to/google-credentials.json
   GOOGLE_SPREADSHEET_ID=1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p
   ```

6. **For Render Deployment:**
   - Upload the JSON credentials file to Render's file storage or environment variables
   - Set the environment variables in Render's dashboard:
     - `GOOGLE_CREDENTIALS_PATH`: Path in the container
     - `GOOGLE_SPREADSHEET_ID`: Your spreadsheet ID
   - Alternatively, use Render's **Secrets** feature to store the JSON file securely

### How It Works

- Training data is automatically saved to **both** Google Sheets and the local CSV
- When the model retrains, it pulls data from Google Sheets (with local CSV as fallback)
- Data persists even after server restarts or Render sleep mode
- The local CSV serves as an automatic backup

### WiFi Mode Usage

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

## Deploying on Render with Google Sheets

### Problem

By default, Render deployments have ephemeral file systems - data is **deleted** when:
- The service goes to sleep (after 15 minutes of inactivity on free tier)
- The service is restarted
- The dyno is rebuilt

### Solution: Google Sheets Integration

With Google Sheets configured, your training data persists permanently:

1. **Data is saved to Google Sheets** - Survives deployment restarts
2. **Local CSV backup** - Preserved across service restarts
3. **Model retrains from Google Sheets** - Always uses the latest remote data

### Step-by-Step Render Deployment

1. **Connect your GitHub repository to Render:**
   - Go to https://render.com/
   - Click "New +" → "Web Service"
   - Connect your GitHub account
   - Select this repository
   - Choose free or paid tier

2. **Set environment variables in Render dashboard:**
   - Go to your service → "Environment"
   - Add these variables:
     ```
     APP_HOST=0.0.0.0
     APP_PORT=8000
     MODEL_PATH=models/gesture_model.pkl
     DATASET_PATH=data/datasets/gesture_dataset.csv
     LOG_LEVEL=INFO
     ALLOW_MISSING_MODEL=true
     ENABLE_DEMO=true
     GOOGLE_CREDENTIALS_PATH=/etc/secrets/google-credentials.json
     GOOGLE_SPREADSHEET_ID=your_spreadsheet_id_here
     ```

3. **Store Google credentials securely:**
   - Option A: Upload to Render's mounted file system
     - Create a file in your project (not in git): `.render/google-credentials.json`
     - In Render dashboard → "Disk" → Mount at `/var/data`
     - Adjust `GOOGLE_CREDENTIALS_PATH=/var/data/google-credentials.json`
   - Option B: Use environment variables (for simple JSON)
     - Set the JSON file content as a secret environment variable

4. **Deploy:**
   - Push changes to GitHub
   - Render will auto-deploy

### Data Sync Script

For local development or manual syncing:

```bash
# Upload local CSV to Google Sheets
python scripts/sync_google_sheets.py upload \
  --csv data/datasets/gesture_dataset.csv \
  --credentials /path/to/google-credentials.json \
  --sheet-id YOUR_SPREADSHEET_ID

# Download from Google Sheets to local CSV
python scripts/sync_google_sheets.py download \
  --credentials /path/to/google-credentials.json \
  --sheet-id YOUR_SPREADSHEET_ID \
  --csv data/datasets/gesture_dataset.csv

# Show statistics
python scripts/sync_google_sheets.py stats \
  --credentials /path/to/google-credentials.json \
  --sheet-id YOUR_SPREADSHEET_ID
```

### Troubleshooting

**"Google Sheets integration failed" message:**
- Check that credentials JSON path is correct
- Verify the service account email has "Editor" access to the spreadsheet
- Ensure Google Sheets API and Drive API are enabled

**Model not updating after new data:**
- Click "RETRAIN" button in the data collection tool
- Or manually call: `POST /api/model/retrain`

**Data not appearing in Google Sheets:**
- Check that the spreadsheet exists and is shared with the service account
- Verify `GOOGLE_SPREADSHEET_ID` is correct (from the URL)

## Testing Instructions

```bash
pytest
```
