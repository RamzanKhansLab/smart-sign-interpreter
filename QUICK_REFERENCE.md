# Quick Reference Guide

## Google Sheets Integration - Quick Commands

### Initial Setup

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Edit .env with your credentials
nano .env
# Add: GOOGLE_CREDENTIALS_PATH and GOOGLE_SPREADSHEET_ID

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run application
python -m app

# 5. Visit collection tool
# Open: http://localhost:8000/collect
```

### Check Configuration

```bash
# Verify Google Sheets is enabled
curl http://localhost:8000/api/dataset/stats

# Output should show:
# "storage": "google_sheets" (if configured)
# "storage": "local_csv" (if not configured)
```

### Data Operations

```bash
# Upload local CSV to Google Sheets
python scripts/sync_google_sheets.py upload \
  --csv data/datasets/gesture_dataset.csv \
  --credentials path/to/google-credentials.json \
  --sheet-id YOUR_SPREADSHEET_ID

# Download from Google Sheets to local CSV
python scripts/sync_google_sheets.py download \
  --credentials path/to/google-credentials.json \
  --sheet-id YOUR_SPREADSHEET_ID \
  --csv data/datasets/gesture_dataset.csv

# Show statistics
python scripts/sync_google_sheets.py stats \
  --credentials path/to/google-credentials.json \
  --sheet-id YOUR_SPREADSHEET_ID
```

### Model Operations

```bash
# Retrain model (uses Google Sheets if configured)
curl -X POST http://localhost:8000/api/model/retrain \
  -H "Content-Type: application/json" \
  -d '{"model_type": "knn"}'

# Check model status
curl http://localhost:8000/api/model/status

# Reset model
curl -X POST http://localhost:8000/api/model/reset
```

### Data Collection

```bash
# Get dataset statistics
curl http://localhost:8000/api/dataset/stats

# Get sample rows
curl "http://localhost:8000/api/dataset/rows?limit=10&offset=0"

# Get rows for specific gesture
curl "http://localhost:8000/api/dataset/rows?label=hello&limit=50"
```

### API Endpoints Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | System health check |
| `/api/latest` | GET | Get latest sensor data |
| `/api/sensor-data` | POST | Send sensor data |
| `/api/demo/publish` | POST | Send demo data |
| `/api/dataset/stats` | GET | Get dataset statistics |
| `/api/dataset/rows` | GET | Get dataset rows |
| `/api/dataset/save-latest` | POST | Save latest sensor as sample |
| `/api/dataset/save-batch` | POST | Save batch of samples |
| `/api/dataset/rename-label` | POST | Rename gesture label |
| `/api/dataset/delete-label` | POST | Delete gesture label |
| `/api/model/status` | GET | Check model status |
| `/api/model/retrain` | POST | Retrain model |
| `/api/model/reset` | POST | Reset model |

### Web UI

| URL | Purpose |
|-----|---------|
| `http://localhost:8000/` | Home page |
| `http://localhost:8000/collect` | Data collection tool |
| `http://localhost:8000/interpret` | Gesture interpretation tool |

### Environment Variables

```
# Application
APP_HOST=0.0.0.0
APP_PORT=8000

# Model and Data Paths
MODEL_PATH=models/gesture_model.pkl
DATASET_PATH=data/datasets/gesture_dataset.csv

# Google Sheets (Optional)
# Accepts a credentials-file path or the complete service-account JSON value.
GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
GOOGLE_SPREADSHEET_ID=spreadsheet_id_here

# Logging
LOG_LEVEL=INFO

# Features
ALLOW_MISSING_MODEL=true
ENABLE_DEMO=true
CORS_ORIGINS=
```

### Troubleshooting

```bash
# Check if Google Sheets is working
curl http://localhost:8000/api/dataset/stats | grep storage

# View application logs
python -m app 2>&1 | tee app.log

# Test Google Sheets connection
python scripts/sync_google_sheets.py stats \
  --credentials path/to/credentials.json \
  --sheet-id YOUR_ID

# Check Python environment
python --version
pip list | grep gspread
```

### Docker Deployment

```bash
# Build image
docker build -t smart-sign-interpreter .

# Run container
docker run -p 8000:8000 \
  -e GOOGLE_CREDENTIALS_PATH=/secrets/credentials.json \
  -e GOOGLE_SPREADSHEET_ID=your_id \
  -v /path/to/credentials.json:/secrets/credentials.json \
  smart-sign-interpreter

# Run with docker-compose
docker compose up --build
```

### Render Deployment

```bash
# Set environment variables in Render dashboard:
# GOOGLE_CREDENTIALS_PATH=<complete service-account JSON secret>
# GOOGLE_SPREADSHEET_ID=your_id

# Deploy
git push origin main
# Render auto-deploys

# Check logs
# Open Render dashboard → Logs tab

# Force redeploy
# Render dashboard → Manual Deploy
```

### Common Issues

```bash
# "Google Sheets integration failed"
# → Check GOOGLE_CREDENTIALS_PATH is a valid JSON document or an existing file path
# → Check GOOGLE_SPREADSHEET_ID is correct
# → Check APIs are enabled

# "No data found in Google Sheets"
# → Make sure you've collected and saved data
# → Check spreadsheet is shared with service account email

# "Model not retraining"
# → Click RETRAIN button in collection tool
# → Or: curl -X POST http://localhost:8000/api/model/retrain

# "Data not in Google Sheets"
# → Check stats endpoint: /api/dataset/stats
# → Verify spreadsheet ID in .env
# → Try manual upload: python scripts/sync_google_sheets.py upload
```

### Performance Tips

```bash
# For large datasets (>1000 rows)
# 1. Consider archiving old data in separate sheet
# 2. Download to local CSV for faster initial training
# 3. Use download command to create local backup

python scripts/sync_google_sheets.py download \
  --credentials path/to/credentials.json \
  --sheet-id YOUR_ID \
  --csv archive_data.csv
```

### Security Checklist

- [ ] Google credentials not in git (add to .gitignore)
- [ ] Use .env file for local development
- [ ] Use Render secrets for production
- [ ] Google Sheet shared only with service account
- [ ] Service account has "Editor" access only
- [ ] APIs enabled in Google Cloud Console
- [ ] Regularly rotate service account keys
- [ ] Monitor for unauthorized access

### Useful Links

- [Google Sheets Setup Guide](GOOGLE_SHEETS_SETUP.md)
- [Render Deployment Guide](RENDER_DEPLOYMENT.md)
- [API Documentation](README.md)
- [Changes Summary](CHANGES_SUMMARY.md)
- [Google Cloud Console](https://console.cloud.google.com/)
- [Google Sheets](https://sheets.google.com/)
- [Render Dashboard](https://dashboard.render.com/)

### Support

For detailed help:
- Setup issues → See [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md)
- Deployment issues → See [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md)
- Code changes → See [CHANGES_SUMMARY.md](CHANGES_SUMMARY.md)
- General usage → See [README.md](README.md)
