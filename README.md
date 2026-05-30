# Russian Bot - Telegram Anonymous Chat Auto-Promoter

Auto-promotion bot for `@znakomstva_anon_bot` (Anonymous Chat bot).

## Promo Sequence (Per Match)
When matched with a partner, the bot sends:
1. **"heyyy"** → wait 3 seconds
2. **"F"** → wait 3 seconds
3. **Sticker** (promo) → wait 3 seconds
4. **Send `/stop`** → find next partner

## Deploy to Railway (No Terminal/Bash Needed)

### Step 1: Create GitHub Repo
1. Go to [github.com](https://github.com) and create a **new repository**
2. Name it anything (e.g., `russian-bot`)
3. Click **"Add file" → "Upload files"**
4. Upload ALL files from this folder:
   - `main.py`
   - `requirements.txt`
   - `Procfile`
   - `gitignore` (we will rename this after upload)
5. Click **"Commit changes"**
6. Now find `gitignore` in your repo, click it → **Edit (pencil icon)** → rename to `.gitignore` → **Commit**

### Step 2: Deploy on Railway
1. Go to [railway.app](https://railway.app) and login with GitHub
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your repository
4. Railway will auto-detect Python from `requirements.txt` and `Procfile`

### Step 3: Add Environment Variables
In Railway Dashboard:
1. Click on your **service**
2. Go to **"Variables"** tab
3. Click **"New Variable"** and add these 3:

| Variable Name | Value |
|--------------|-------|
| `STRING_SESSION` | Your Telethon string session (see below) |
| `API_ID` | Your API ID from my.telegram.org |
| `API_HASH` | Your API hash from my.telegram.org |

4. Railway will auto-redeploy after adding variables

### Step 4: Setup Messages (BEFORE running)
Before the bot starts, send these to your own Telegram **Saved Messages**:
1. A text message: **`heyyy`**
2. A text message: **`F`**
3. Your promo **sticker**

The bot will forward these in sequence to every matched partner.

## How to Get STRING_SESSION (No Code Needed)

Use this online tool: **[@SessionGeneratorBot](https://t.me/SessionGeneratorBot)** on Telegram

Or run this Python code locally:
```python
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = YOUR_API_ID
api_hash = 'YOUR_API_HASH'

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print(client.session.save())
```

## Files

| File | Purpose |
|------|---------|
| `main.py` | Main bot script |
| `requirements.txt` | Python dependencies |
| `Procfile` | Tells Railway to run `python main.py` |
| `gitignore` | Rename to `.gitignore` after GitHub upload |

## ⚠️ Disclaimer
Use responsibly. Excessive spamming may result in Telegram account restrictions.
