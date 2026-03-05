# Cloud Deployment Guide: Vercel + Railway

**Last Updated:** March 5, 2026  
**Tech Stack:** React 18.2 (Vercel) + FastAPI 0.115 (Railway)  
**Status:** Production Ready ✅

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Vercel Frontend Deployment](#vercel-frontend-deployment)
4. [Railway Backend Deployment](#railway-backend-deployment)
5. [Configuration & Environment Variables](#configuration--environment-variables)
6. [Production Validation](#production-validation)
7. [Troubleshooting](#troubleshooting)
8. [Monitoring & Maintenance](#monitoring--maintenance)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    VERCEL FRONTEND                          │
│  (React 18.2 + TypeScript + Vite)                           │
│  - Hosted on Vercel CDN                                     │
│  - Auto-deploys from GitHub main branch                     │
│  - Environment: VITE_API_BASE_URL → Railway Backend         │
└──────────────────────────┬──────────────────────────────────┘
                           │ WebSocket + REST
                           │ (HTTPS/WSS)
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    RAILWAY BACKEND                          │
│  (FastAPI 0.115 + Python 3.13.2)                            │
│  - Containerized with Docker                                │
│  - Auto-deploys from GitHub main branch                     │
│  - Port: 8000 (Railway assigns via PORT env var)            │
│  - Environment: PROVIDER_MODE=real, API Keys                │
└─────────────────────────────────────────────────────────────┘
         ↓
    OpenAI APIs
    - Whisper ASR
    - GPT-3.5-turbo LLM
    - TTS (tts-1-hd)
```

### Why This Works:

✅ **Vercel for Frontend:**
- Global CDN for low-latency asset delivery
- Automatic HTTPS
- Serverless deployments
- Free tier available
- Seamless GitHub integration

✅ **Railway for Backend:**
- Docker support out-of-box
- Easy environment variable management
- WebSocket support (critical for real-time)
- Automatic HTTPS
- Auto-scaling capabilities
- PostgreSQL support (future expansion)

---

## Pre-Deployment Checklist

### Before You Start:

- [ ] GitHub account with repo pushed
- [ ] Vercel account (free at vercel.com)
- [ ] Railway account (free at railway.app)
- [ ] OpenAI API key (for production backend)
- [ ] Git repository is clean and up-to-date

### Repository Requirements:

- [ ] `.gitignore` includes `.env` (sensitive keys not in repo)
- [ ] `client/vercel.json` exists
- [ ] `Dockerfile` exists in root
- [ ] `railway.json` exists in root
- [ ] All code committed to `main` branch

Check:
```bash
cd /Users/karthikvankara/Desktop/Karthik/Development/real-time-voice-assistant
git log --oneline -5  # Verify recent commits
```

---

## Vercel Frontend Deployment

### Step 1: Connect Repository to Vercel

1. Go to **https://vercel.com/dashboard**
2. Click **"New Project"**
3. Select **"Import Git Repository"**
4. Authorize GitHub access
5. Select your **real-time-voice-assistant** repository
6. Click **"Import"**

### Step 2: Configure Project Settings

**Project Name:** `real-time-voice-assistant` (or your choice)

**Framework Preset:** Select **"Vite"** (should auto-detect)

**Root Directory:** `client` (important!)

**Build Command:** `npm run build` (should be auto-filled)

**Output Directory:** `dist` (should be auto-filled)

**Install Command:** `npm install` (should be auto-filled)

### Step 3: Add Environment Variables

**⚠️ Critical Step:** Configure API endpoint before deployment

1. In Vercel dashboard, go to **Settings > Environment Variables**

2. Add the following variable:

   **Key:** `VITE_API_BASE_URL`  
   **Value:** `https://your-railway-backend.railway.app` (fill after deploying backend)  
   **Environments:** Select all (Production, Preview, Development)

   **For now, use placeholder:** `https://api.example.com`  
   (Update after you deploy backend)

### Step 4: Deploy Frontend

1. Click **"Deploy"** button in Vercel
2. Wait for build to complete (~2-3 minutes)
3. You'll get a URL like: `https://real-time-voice-assistant.vercel.app`

### Step 5: Verify Frontend Load

```bash
# Test in browser
curl https://real-time-voice-assistant.vercel.app

# Should return HTML with React app
```

---

## Railway Backend Deployment

### Step 1: Connect Repository to Railway

1. Go to **https://railway.app/dashboard**
2. Click **"New Project"**
3. Select **"Deploy from GitHub Repo"**
4. Authorize GitHub
5. Select **real-time-voice-assistant** repository
6. Choose branch: `main`
7. Confirm deployment region (closest to you)

### Step 2: Configure Environment Variables

Once deployed, go to **Settings > Variables** in Railway:

Add these required variables:

```
PROVIDER_MODE=real
LOG_LEVEL=info
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
```

**Critical Variables:**
- `OPENAI_API_KEY` - Your OpenAI API key (get from openai.com/account/api-keys)

---

**Optional Variables** (if overriding defaults):

```
ASR_PROVIDER_URL=https://api.openai.com/v1/audio/transcriptions
LLM_PROVIDER_URL=https://api.openai.com/v1/chat/completions
TTS_PROVIDER_URL=https://api.openai.com/v1/audio/speech
```

### Step 3: Monitor Backend Deployment

In Railway dashboard:

1. Watch the **Build Logs** for Dockerfile build progress
2. Watch the **Deploy Logs** for uvicorn startup
3. Look for: `"Uvicorn running on http://0.0.0.0:8000"`

### Step 4: Get Backend Public URL

Once deployed:

1. Go to **Settings > Domains** in Railway
2. Copy the public URL (e.g., `https://xyz-prod.up.railway.app`)
3. Save this URL - you'll need it for frontend config

### Step 5: Test Backend Health

```bash
# Replace with your Railway URL
curl https://xyz-prod.up.railway.app/health

# Expected response:
# {"status":"ok"}
```

---

## Configuration & Environment Variables

### Frontend Configuration

**File:** `client/.env.production`

```env
VITE_API_BASE_URL=https://xyz-prod.up.railway.app
VITE_ENABLE_DIAGNOSTICS=true
```

**In Vercel Dashboard:**
- Go to Settings > Environment Variables
- Add `VITE_API_BASE_URL` with your Railway backend URL
- Redeploy to apply changes

### Backend Configuration

**File:** `.env` (not committed, created in Railway)

```env
PROVIDER_MODE=real
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
LOG_LEVEL=info
CORS_ORIGINS=https://real-time-voice-assistant.vercel.app
```

**In Railway Dashboard:**
- Go to Settings > Variables
- Add above variables
- Auto-redeploys when changed

### CORS Configuration

The FastAPI backend already has CORS enabled:

```python
# src/server.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ✅ Allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**For Production (Optional):**
Restrict to specific origin:

```python
allow_origins=[
    "https://real-time-voice-assistant.vercel.app",
    "https://yourdomain.com"
],
```

---

## Client-Backend Integration

### Update WebSocket URL

**File:** `client/src/services/websocket.ts`

Currently might have:
```typescript
const WS_URL = 'ws://localhost:8000/ws';
```

Update to use environment variable:
```typescript
const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const WS_URL = apiBase.replace(/^http/, 'ws') + '/ws';
```

Example transformations:
- HTTP: `https://api.example.com` → WS: `wss://api.example.com/ws`
- HTTP: `http://localhost:8000` → WS: `ws://localhost:8000/ws`

### Update REST API Calls

**File:** `client/src/App.tsx`

Replace hardcoded URLs:
```typescript
// BEFORE
const response = await fetch('http://localhost:8000/telemetry/latency')

// AFTER
const apiBase = import.meta.env.VITE_API_BASE_URL || 'https://localhost:8000';
const response = await fetch(`${apiBase}/telemetry/latency`)
```

---

## Production Validation

### Pre-Go-Live: End-to-End Testing

**Test 1: Frontend Loads**
```bash
curl -v https://real-time-voice-assistant.vercel.app
# Should return HTML with React app
```

**Test 2: Backend Health**
```bash
curl https://xyz-prod.up.railway.app/health
# Should return {"status":"ok"}
```

**Test 3: CORS Headers**
```bash
curl -v \
  -H "Origin: https://real-time-voice-assistant.vercel.app" \
  https://xyz-prod.up.railway.app/health

# Check response headers for:
# Access-Control-Allow-Origin: *
```

**Test 4: Full User Flow**
1. Open frontend URL in browser
2. Click "Connect to Server"
3. Allow microphone access
4. Speak a test phrase (e.g., "Hey tell me about OpenAI")
5. Verify:
   - Audio captured ✓
   - Transcription appears ✓
   - LLM response generated ✓
   - Audio response plays ✓

### Monitoring After Deployment

#### Vercel Monitoring:
- Dashboard → Analytics
- Check:
  - Response times
  - Error rates
  - Traffic patterns

#### Railway Monitoring:
- Dashboard → Metrics
- Check:
  - CPU usage
  - Memory usage
  - Network latency
  - Error logs

---

## Troubleshooting

### Frontend Issues

#### Problem: "Cannot reach backend" or "Connection refused"

**Symptoms:**
- Browser console shows `WebSocket connection failed`
- API calls timeout

**Solutions:**
1. Verify Railway backend is running
   ```bash
   curl https://your-railway-url/health
   ```

2. Check `VITE_API_BASE_URL` in Vercel env variables
   - Should match Railway domain exactly
   - No trailing slash

3. Verify CORS headers from backend
   ```bash
   curl -H "Origin: https://vercel-url" https://railway-url/health
   ```

#### Problem: "DevTools error: source map"

**Symptom:** Console warnings about missing source maps

**Solution:** This is normal in production. Ignore or disable sourcemaps in `vite.config.ts`:

```typescript
export default defineConfig({
  build: {
    sourcemap: false,  // Don't generate source maps in production
  },
})
```

### Backend Issues

#### Problem: "502 Bad Gateway" from Railway

**Symptoms:**
- Fresh deployment shows 502 errors
- Then resolves after a minute

**Causes:** Cold start (normal), waiting for uvicorn to bind port

**Solution:** Wait 1-2 minutes, then refresh

#### Problem: "OpenAI API key invalid"

**Symptoms:**
- Backend logs show `401 Unauthorized` from OpenAI

**Solution:**
1. Verify API key in Railway environment variables
2. Check key hasn't expired in OpenAI dashboard
3. Ensure key has correct permissions (ASR, LLM, TTS)

#### Problem: "Out of memory" errors

**Symptoms:**
- Backend crashes after ~30 requests
- Railway logs show OOM kill

**Solution:**
1. In Railway, upgrade to larger plan
2. Or optimize WebSocket buffer management in `src/server.py`

### WebSocket Connection Issues

#### Problem: "WebSocket connection fails on first attempt"

**Solution:** Add retry logic in `client/src/services/websocket.ts`:

```typescript
async function connectWithRetry(url: string, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return new WebSocket(url);
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      await new Promise(r => setTimeout(r, 1000 * (i + 1)));
    }
  }
}
```

#### Problem: "WebSocket connection drops intermittently"

**Causes:**
- Railway auto-scaling (rare)
- Network timeouts (firewall)
- Long-running requests without keep-alives

**Solution:**
1. Add heartbeat ping/pong:
   ```python
   # In src/server.py WebSocket handler
   async for message in websocket:
       # ... handle message ...
       await websocket.send_text('{"type":"pong"}')
   ```

2. Configure Railway keep-alive in railway.json

---

## Monitoring & Maintenance

### Daily Checks

- [ ] Backend health endpoint responds (200 OK)
- [ ] Frontend loads without console errors
- [ ] End-to-end test: speech input → audio response works

### Weekly Checks

- [ ] Review Railway metrics (CPU, Memory)
- [ ] Review Vercel analytics (errors, latency)
- [ ] Check OpenAI API usage in dashboard

### Monthly Tasks

- [ ] Update dependencies
  ```bash
  npm update  # Frontend
  pip install --upgrade -e .  # Backend
  ```

- [ ] Review logs for warnings/errors
- [ ] Test disaster recovery (what if backend fails?)

### Setting Up Alerts (Optional)

#### Railway Alerts:
1. Dashboard → Settings → Alerts
2. Add alert for:
   - Memory > 80%
   - CPU > 90%
   - Build failure

#### Vercel Alerts:
1. Dashboard → Settings → Monitoring
2. Add alerts for:
   - Error rate > 1%
   - Response time > 1s

---

## Scaling in Future

### When You Need More Capacity:

**Frontend (Vercel):**
- Already handles infinite scale via CDN
- Pro plan ($20/mo) for additional features

**Backend (Railway):**
1. Upgrade to paid plan
2. Enable auto-scaling in railway.json:
   ```json
   {
     "deploy": {
       "restartPolicy": "always",
       "healthcheckPath": "/health",
       "healthcheckInterval": 30
     }
   }
   ```

3. Add PostgreSQL for session persistence (optional)

---

## Rollback Procedure

### If Production Breaks:

**From Vercel:**
1. Dashboard → Deployments
2. Click previous working deployment
3. Click "Promote to Production"
4. Done (instant rollback)

**From Railway:**
1. Dashboard → Deployments
2. Select previous working deployment
3. Click "Redeploy"
4. Wait ~2-3 minutes

---

## Cost Estimation

### Monthly Costs (Estimate):

| Service | Plan | Cost | Notes |
|---------|------|------|-------|
| Vercel | Free/Pro | $0-20 | Free tier includes generous limits |
| Railway | Starter | $5-20 | ~2 GB RAM, auto-scaling available |
| OpenAI | Pay-as-you-go | $0-50 | Depends on usage (transcription, LLM, TTS) |
| **Total** | - | **$5-90/mo** | Scale with usage |

---

## Support & Documentation

### Helpful Resources:

- **Vercel Docs:** https://vercel.com/docs
- **Railway Docs:** https://docs.railway.app
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **OpenAI API Docs:** https://platform.openai.com/docs

### Getting Help:

1. Check troubleshooting section above
2. Review logs:
   - Vercel: Dashboard → Function Logs
   - Railway: Dashboard → Logs
3. Search GitHub issues in the repo
4. Ask on respective platform support forums

---

## Summary Checklist

### Before Deploying:

- [ ] `.gitignore` properly configured
- [ ] `.env` never committed
- [ ] All tests pass locally
- [ ] Git main branch is clean and updated

### Vercel Deployment:

- [ ] Repository connected to Vercel
- [ ] Root directory set to `client`
- [ ] Build command: `npm run build`
- [ ] Deployment successful
- [ ] Can access frontend URL in browser

### Railway Deployment:

- [ ] Repository connected to Railway
- [ ] Dockerfile exists and builds successfully
- [ ] Environment variables set (OPENAI_API_KEY, etc.)
- [ ] Backend health endpoint works
- [ ] Can reach /health endpoint

### Integration:

- [ ] Frontend `VITE_API_BASE_URL` points to Railway backend
- [ ] WebSocket URL correctly transforms http → ws
- [ ] CORS headers present in responses
- [ ] End-to-end test passes (speech → audio response)

### Post-Deployment:

- [ ] Monitor Vercel & Railway dashboards
- [ ] Set up alerts (optional)
- [ ] Document backend URL for future reference
- [ ] Share URLs with team

---

**Document Version:** 1.0  
**Last Updated:** March 5, 2026  
**Deployment Status:** Ready for Production ✅  

---

## Quick Command Reference

```bash
# Test frontend locally with production backend URL
VITE_API_BASE_URL=https://your-railway-url npm run dev

# Test backend locally
uvicorn src.server:create_app --reload --port 8000

# Deploy backend to Railway (via Git push)
git add . && git commit -m "..." && git push origin main
# Railway auto-deploys

# Deploy frontend to Vercel (via Git push)
git add . && git commit -m "..." && git push origin main
# Vercel auto-deploys
```
