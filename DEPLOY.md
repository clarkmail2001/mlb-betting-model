# MLB Model Deployment Guide

## Local Development
```bash
cd mlb_model_v2
pip install -r requirements.txt
python3 app.py
# Open http://localhost:5000
# Click "Import CSV Data" after adding your CSV files
```

---

## Railway Deployment (Free Tier)

### Option A: Via CLI
```bash
# Install CLI
npm install -g @railway/cli

# Login
railway login

# Navigate to project
cd mlb_model_v2

# Initialize and deploy
railway init
railway up

# Open your app
railway open
```

### Option B: Via Web
1. Go to https://railway.app
2. Click "New Project" → "Deploy from GitHub repo"
3. Connect your GitHub and select the repo
4. Railway auto-detects `railway.json` and deploys
5. Click "Generate Domain" to get your URL

### Railway Notes:
- Free tier: 500 hours/month, 512MB RAM
- SQLite works but resets on redeploy
- Add CSV files via web upload after deploy

---

## Render Deployment (Free Tier)

### Steps:
1. Push code to GitHub
2. Go to https://render.com
3. Click "New" → "Web Service"
4. Connect GitHub repo
5. Render detects `render.yaml` automatically
6. Click "Create Web Service"
7. Wait 2-3 minutes for build
8. Access via `https://mlb-model.onrender.com`

### Render Notes:
- Free tier spins down after 15 min inactive
- First request after sleep takes ~30 seconds
- SQLite works but resets on redeploy

---

## Files Included

| File | Purpose |
|------|---------|
| `app.py` | Flask application |
| `requirements.txt` | Python dependencies |
| `Procfile` | Start command for hosting |
| `runtime.txt` | Python version |
| `railway.json` | Railway-specific config |
| `render.yaml` | Render-specific config |
| `templates/` | HTML templates |

---

## After Deployment

1. Open your deployed URL
2. Go to Dashboard
3. Click "Import CSV Data" 
4. Upload your CSV files (you'll need to modify app.py to handle file uploads for cloud deployment, or pre-load data)

---

## For Persistent Data (Optional)

Free SQLite resets on each deploy. For persistent data:

1. **Supabase** (free Postgres): https://supabase.com
2. **PlanetScale** (free MySQL): https://planetscale.com
3. **Railway Postgres** (free tier included)

Update `DB_PATH` in `app.py` to use the cloud database URL.
