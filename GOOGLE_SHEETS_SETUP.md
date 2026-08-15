# Google Sheets Integration Guide

## Overview

This guide explains how to set up and use Google Sheets for persistent training data storage in the Smart Sign Interpreter project.

## Problem Statement

When deploying on Render (or other cloud platforms with ephemeral file systems):
- Training data stored in `data/datasets/gesture_dataset.csv` gets **deleted** when the service restarts
- The service goes to sleep after inactivity, causing data loss
- This prevents effective model retraining with accumulated data

## Solution

By integrating Google Sheets:
- ✅ Training data is saved to Google Sheets (cloud-hosted, always accessible)
- ✅ Local CSV provides automatic backup
- ✅ Model retrains using data from Google Sheets
- ✅ Data persists across service restarts, sleep cycles, and rebuilds

## Prerequisites

- Google account
- Basic familiarity with Google Cloud Console
- Access to your project's environment variables

## Setup Instructions

### 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top
3. Click "NEW PROJECT"
4. Enter a name (e.g., "smart-sign-interpreter")
5. Click "CREATE"
6. Wait for the project to be created, then select it

### 2. Create a Service Account

A service account allows the application to authenticate with Google Sheets without user interaction.

1. In the Google Cloud Console, go to **Service Accounts**
   - Search "Service Accounts" in the top search bar
   - Click the result

2. Click **"CREATE SERVICE ACCOUNT"**

3. Fill in the details:
   - **Service account name**: `smart-sign-interpreter`
   - **Service account ID**: Auto-generated
   - **Description**: "For gesture dataset storage"
   - Click **"CREATE AND CONTINUE"**

4. Grant permissions (optional but recommended):
   - Click **"CONTINUE"** on the "Grant this service account access to project" step
   - Click **"DONE"** (we'll manage permissions via spreadsheet sharing)

5. Create a JSON key:
   - Find your service account in the list
   - Click on it
   - Go to the **"KEYS"** tab
   - Click **"ADD KEY"** → **"Create new key"**
   - Choose **"JSON"**
   - Click **"CREATE"**
   - A JSON file will be downloaded - **save this securely!**

### 3. Enable Required APIs

1. In your Cloud project, go to **APIs & Services** → **Enabled APIs & Services**
2. Click **"+ ENABLE APIS AND SERVICES"**
3. Search for **"Google Sheets API"**
   - Click the result
   - Click **"ENABLE"**
4. Repeat for **"Google Drive API"**

### 4. Create a Google Sheet

1. Go to [Google Sheets](https://sheets.google.com/)
2. Click **"+ New Spreadsheet"**
3. Name it (e.g., "gesture_dataset")
4. In the URL bar, copy the spreadsheet ID:
   ```
   https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit...
   ```
   - Copy just the ID (long alphanumeric string)

5. Share the spreadsheet with your service account:
   - Click **"Share"** button
   - In the service account JSON file, find the `"client_email"` field (looks like `service-account@project.iam.gserviceaccount.com`)
   - Paste this email in the share dialog
   - Give it **"Editor"** access
   - Click **"Share"** or **"Send"**

### 5. Configure Environment Variables

#### For Local Development

1. In your project root, copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add:
   ```env
   GOOGLE_CREDENTIALS_PATH=/path/to/google-credentials.json
   GOOGLE_SPREADSHEET_ID=your_spreadsheet_id_here
   ```

   Replace with your actual values:
   - `/path/to/google-credentials.json`: Absolute path to the downloaded JSON file
   - `your_spreadsheet_id_here`: The ID from step 4

3. Test the connection:
   ```bash
   python -m app
   ```

   You should see:
   ```
   ✓ Google Sheets integration enabled for dataset storage
   ```

#### For Render Deployment

1. **Option A: Using Render's File Storage**
   - Upload the JSON credentials file to Render's mounted file system
   - Set `GOOGLE_CREDENTIALS_PATH` to the file's location

2. **Option B: Using Environment Variables**
   - In Render dashboard → Your service → "Environment"
   - Add these variables:
     ```
     GOOGLE_CREDENTIALS_PATH=/etc/secrets/google-credentials.json
     GOOGLE_SPREADSHEET_ID=your_spreadsheet_id
     ```

3. Upload the credentials file:
   - Create `.render/google-credentials.json` (or your preferred location)
   - Place your downloaded JSON file there
   - In Render → "Disk" → Mount the directory
   - Or upload via Render's file management

### 6. Verify the Setup

1. Run the application:
   ```bash
   python -m app
   ```

2. Visit the data collection tool:
   ```
   http://localhost:8000/collect
   ```

3. Collect some gesture data and save it
4. Check your Google Sheet - new rows should appear!
5. Check stats endpoint:
   ```
   curl http://localhost:8000/api/dataset/stats
   ```

   Response should include:
   ```json
   {
     "storage": "google_sheets",
     "path": "Google Sheets (your_spreadsheet_id)",
     ...
   }
   ```

## Usage

### Data Collection and Training

1. **Collect Data:**
   - Open `http://localhost:8000/collect`
   - Collect gesture samples
   - Data is automatically saved to both Google Sheets and local CSV

2. **Retrain Model:**
   - Click **"RETRAIN"** button in the collection tool
   - Model is trained using data from Google Sheets
   - New model is saved

### Manual Data Management

Use the provided sync script:

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

## API Endpoints

### Dataset Statistics
```
GET /api/dataset/stats
```

Returns:
```json
{
  "total": 150,
  "by_label": {"A": 50, "B": 50, "C": 50},
  "storage": "google_sheets",
  "path": "Google Sheets (spreadsheet_id)"
}
```

### Retrain Model
```
POST /api/model/retrain
```

Body:
```json
{
  "model_type": "knn"
}
```

## Troubleshooting

### "Google Sheets integration failed"

**Possible causes:**

1. **Credentials file not found**
   - Verify the path in `GOOGLE_CREDENTIALS_PATH`
   - Path must be absolute or relative to current working directory

2. **Service account doesn't have access**
   - Go to the spreadsheet
   - Click "Share"
   - Make sure the service account email has "Editor" access
   - Check the email matches `client_email` in your JSON file

3. **Google Sheets API not enabled**
   - Go to Google Cloud Console → APIs & Services
   - Search "Google Sheets API" → Enable it
   - Search "Google Drive API" → Enable it

4. **Invalid Spreadsheet ID**
   - Copy the ID from the URL bar
   - Should be a long alphanumeric string
   - Make sure there are no spaces or extra characters

### Data not appearing in Google Sheets

1. Check that the data collection tool shows saves are happening
2. Verify spreadsheet is shared with the service account
3. Try manually uploading with the sync script:
   ```bash
   python scripts/sync_google_sheets.py upload --csv ... --credentials ... --sheet-id ...
   ```

### Model not retraining

1. Click **"RETRAIN"** button in the collection tool
2. Check the endpoint: `POST /api/model/retrain`
3. Check application logs for errors
4. Verify Google Sheets has data: `GET /api/dataset/stats`

### "No data found in Google Sheets" error

1. Make sure you've collected and saved at least one gesture
2. Verify the spreadsheet ID is correct
3. Check that data is visible in the Google Sheet (not just in header row)

## Performance Notes

- First data load from Google Sheets may take a few seconds
- Subsequent loads are cached by gspread library
- For optimal performance, keep gesture dataset under 10,000 rows
- If performance degrades, consider archiving old data

## Security Best Practices

1. **Protect the credentials JSON file:**
   - Never commit it to git
   - Add to `.gitignore` if not already there
   - Use environment variables for Render/production

2. **Limit sheet permissions:**
   - Only share with the service account
   - Don't share with personal Google account

3. **Use project-specific service accounts:**
   - Create separate accounts for different environments
   - Makes it easier to revoke access

4. **Rotate credentials periodically:**
   - Delete old JSON keys
   - Generate new ones monthly

## Migration Guide

If you're migrating from local-only storage:

1. Set up Google Sheets (steps 1-5 above)
2. Deploy the updated application
3. Test data collection and verify data appears in Google Sheets
4. Manually upload existing local data (if needed):
   ```bash
   python scripts/sync_google_sheets.py upload \
     --csv data/datasets/gesture_dataset.csv \
     --credentials /path/to/credentials.json \
     --sheet-id YOUR_ID
   ```

## Support

For issues:
1. Check the logs in your application
2. Review the troubleshooting section above
3. Check Google Cloud Console for API errors
4. Open an issue in the repository

## Additional Resources

- [Google Sheets API Documentation](https://developers.google.com/sheets/api)
- [gspread Library Documentation](https://docs.gspread.org/)
- [Service Account Setup Guide](https://cloud.google.com/iam/docs/service-accounts)
