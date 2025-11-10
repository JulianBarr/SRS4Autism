# Google Cloud Translation API Setup Guide

## Quick Setup (5 minutes)

### Step 1: Enable Translation API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create a new one)
3. Navigate to **APIs & Services** > **Library**
4. Search for "Cloud Translation API"
5. Click on it and click **Enable**

### Step 2: Create a Service Account

1. Go to **IAM & Admin** > **Service Accounts**
2. Click **Create Service Account**
3. Enter a name (e.g., "translation-service")
4. Click **Create and Continue**
5. Grant role: **Cloud Translation API User**
6. Click **Continue** then **Done**

### Step 3: Create and Download JSON Key

1. Click on the service account you just created
2. Go to the **Keys** tab
3. Click **Add Key** > **Create new key**
4. Choose **JSON** format
5. Click **Create** - the JSON file will download automatically

### Step 4: Save the Key File

**Important:** Save the downloaded JSON file to:

```
/Users/maxent/src/SRS4Autism/backend/google-credentials.json
```

**⚠️ Security Note:** This file contains sensitive credentials. It's already in `.gitignore` so it won't be committed to git.

### Step 5: Verify Setup

Run the translation script:

```bash
cd /Users/maxent/src/SRS4Autism
source venv/bin/activate
python scripts/knowledge_graph/extract_mastered_words.py
```

You should see:
```
✅ Google Cloud Translation API initialized (service account)
   Project ID: your-project-id
   Using dedicated translation API - fast and efficient!
```

## What You Get

✅ **Fast translation** - No rate limits like Gemini  
✅ **Batch processing** - Translate up to 128 words at once  
✅ **Reliable** - Designed specifically for translation  
✅ **Cost effective** - Very cheap ($20 per 1M characters)  

## Troubleshooting

**Error: "Permission denied"**
- Make sure the service account has "Cloud Translation API User" role

**Error: "API not enabled"**
- Go to APIs & Services > Library and enable Cloud Translation API

**Error: "Project ID not found"**
- Make sure the JSON credentials file contains a `project_id` field

**Error: "Billing not enabled"**
- Cloud Translation API requires billing to be enabled on your Google Cloud project
- Free tier: First 500K characters/month are free
