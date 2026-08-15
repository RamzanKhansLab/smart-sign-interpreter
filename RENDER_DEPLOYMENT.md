# Deploying Smart Sign Interpreter on Render

This guide walks you through deploying the Smart Sign Interpreter on Render with persistent Google Sheets storage.

## Quick Start

### Prerequisites
- GitHub account with access to the repository
- Render account (free or paid)
- Google account
- This completed: [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md)

### Step 1: Prepare Google Credentials

Before deployment, ensure you have:
1. Google Sheets API and Drive API enabled in Google Cloud Console
2. Service account JSON credentials file downloaded
3. Google Sheet created and shared with the service account
4. Spreadsheet ID copied from the URL

See [GOOGLE_SHEETS_SETUP.md](GOOGLE_SHEETS_SETUP.md) for detailed instructions.

### Step 2: Push Code to GitHub

1. Commit all changes:
   ```bash
   git add .
   git commit -m "Add Google Sheets integration for persistent data storage"
   ```

2. Push to your repository:
   ```bash
   git push origin main
   ```

### Step 3: Create Render Service

1. Go to [render.com](https://render.com/)
2. Sign up or log in
3. Click **"New +"** → **"Web Service"**
4. Connect your GitHub account (first time only)
5. Select this repository
6. Fill in the settings:
   - **Name**: `smart-sign-interpreter` (or your preferred name)
   - **Environment**: `Docker`
   - **Region**: Choose closest to your location
   - **Branch**: `main`
   - **Plan**: `Free` (or upgrade if needed)

7. Click **"Create Web Service"**

Wait for Render to build and deploy (2-5 minutes).

### Step 4: Configure Environment Variables

1. In your Render service dashboard, click **"Environment"**
2. Click **"Add Environment Variable"**
3. Add the following variables:

   ```
   APP_HOST: 0.0.0.0
   APP_PORT: 8000
   MODEL_PATH: models/gesture_model.pkl
   DATASET_PATH: data/datasets/gesture_dataset.csv
   LOG_LEVEL: INFO
   ALLOW_MISSING_MODEL: true
   ENABLE_DEMO: true
   GOOGLE_CREDENTIALS_PATH: [PASTE_COMPLETE_SERVICE_ACCOUNT_JSON_AS_A_SECRET]
   GOOGLE_SPREADSHEET_ID: [YOUR_SPREADSHEET_ID]
   ```

   Replace `[YOUR_SPREADSHEET_ID]` with your actual Google Sheet ID.

### Step 5: Store Google Credentials Safely

For Render free tier, create `GOOGLE_CREDENTIALS_PATH` as a **secret** environment
variable and paste the complete contents of the downloaded service-account JSON
file as its value. This does not require uploading a credentials file to Render.

Do not paste the key into the repository, a committed `.env` file, or a public
support request. If you use a mounted disk on a paid plan, you may instead set
`GOOGLE_CREDENTIALS_PATH` to the credentials file path.

### Step 6: Deploy

1. Go back to your service dashboard
2. Click **"Manual Deploy"** → **"Deploy latest commit"**
3. Wait for deployment to complete
4. Check the logs for:
   ```
   ✓ Google Sheets integration enabled for dataset storage
   ```

### Step 7: Test the Deployment

1. Get your Render URL from the dashboard (e.g., `https://smart-sign-interpreter.onrender.com`)

2. Test the health endpoint:
   ```bash
   curl https://smart-sign-interpreter.onrender.com/api/health
   ```

3. Access the collection tool:
   ```
   https://smart-sign-interpreter.onrender.com/collect
   ```

4. Collect a sample gesture and save it
5. Check that data appears in your Google Sheet

## Monitoring and Maintenance

### View Logs

In your Render dashboard:
- Click **"Logs"** tab
- Real-time logs appear below
- Check for errors and Google Sheets connection messages

### Update Data Sync

To manually sync data:

```bash
# From your local machine
python scripts/sync_google_sheets.py download \
  --credentials /path/to/credentials.json \
  --sheet-id YOUR_SHEET_ID \
  --csv local_data.csv
```

### Retrain Model

The model automatically retrains when you click **"RETRAIN"** in the data collection tool.

To manually trigger:
```bash
curl -X POST https://smart-sign-interpreter.onrender.com/api/model/retrain \
  -H "Content-Type: application/json" \
  -d '{"model_type": "knn"}'
```

### Storage Limits

- **Free tier**: Ephemeral disk only (no persistent data on disk)
- **Paid tier**: Can add persistent disks
- **Google Sheets**: Unlimited (within Google account limits)

### Billing

**Free tier:**
- 750 hours/month of running services
- Auto-spins down after 15 minutes of inactivity
- Good for development/testing

**Paid tier:**
- Always-on service
- More reliable
- Check Render pricing

## Troubleshooting Render Deployment

### Service won't start

1. Check the logs tab
2. Common issues:
   - Missing environment variables
   - Invalid Google credentials JSON or an incorrect credentials path
   - Port already in use

3. Click **"Manual Deploy"** to retry

### "Google Sheets integration failed" on Render

1. Verify `GOOGLE_CREDENTIALS_PATH` contains the complete valid JSON or matches
   the credentials file location.
2. Verify `GOOGLE_SPREADSHEET_ID` is correct.
3. Check Google Sheets API is enabled.

### Data not appearing in Google Sheets

1. Check application logs for errors
2. Verify the spreadsheet is shared with the service account
3. Try accessing the collection tool and checking `/api/dataset/stats`

### Service goes to sleep

On Render's free tier, services auto-spin down after 15 minutes of inactivity.
- This is normal
- Your Google Sheets data is safe
- Data restores when you make a request
- Upgrade to paid tier for always-on service

## Advanced Configuration

### Custom Domain

1. In your service settings, go to **"Custom Domain"**
2. Enter your domain (e.g., `gesture.example.com`)
3. Update your domain's DNS records as instructed

### Scaling

If you need better performance:
1. Upgrade to a paid plan
2. Consider using Render's PostgreSQL for session storage
3. Cache model predictions if needed

### CI/CD

Render automatically deploys on push to main branch. To disable:
1. Go to service settings
2. Turn off **"Auto-deploy"**

## Rendering Service vs Local Development

| Aspect | Local | Render |
|--------|-------|--------|
| Data persistence | Disk based | Google Sheets |
| Uptime | Only while running | 24/7 (paid) or auto-sleep (free) |
| Performance | Fast local access | Network latency to Google |
| Cost | Free | Free/Paid |
| Model updates | Manual via CLI | Via web interface |

## Next Steps

1. Set up real glove hardware to send data
2. Collect training data over time
3. Monitor model accuracy
4. Share deployment URL with team
5. Consider upgrading to paid plan for production use

## Support

- [Render Documentation](https://render.com/docs)
- [Google Sheets Setup Guide](GOOGLE_SHEETS_SETUP.md)
- [Repository Issues](https://github.com/RamzanKhansLab/smart-sign-interpreter/issues)

## Maintenance Checklist

- [ ] Google Sheets API enabled
- [ ] Service account credentials downloaded
- [ ] Google Sheet created and shared
- [ ] Environment variables configured
- [ ] Credentials stored as a Render secret (or uploaded to mounted storage)
- [ ] Service deployed successfully
- [ ] Test data collection working
- [ ] Google Sheets receiving data
- [ ] Model retraining works
- [ ] Share deployment URL with team
