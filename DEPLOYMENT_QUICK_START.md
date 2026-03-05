# Quick Start: Deploy to Vercel + Railway

**This guide gets your app live in ~15 minutes!**

---

## Prerequisites Checklist

- [ ] GitHub account (with repository pushed)
- [ ] Vercel account (free at vercel.com)
- [ ] Railway account (free at railway.app)  
- [ ] OpenAI API key (from openai.com/account/api-keys)

---

## Step 1: Deploy Backend to Railway (5 minutes)

### 1.1 Create Railway Project

1. Go to **https://railway.app/dashboard**
2. Click **"New Project"**
3. Select **"Deploy from GitHub Repo"**
4. Authorize GitHub connection
5. Select **real-time-voice-assistant** repo
6. Choose branch: **main**
7. Click **"Deploy"** and wait 2-3 minutes

### 1.2 Set Environment Variables

Once deployed:

1. In Railway, go to **Settings > Variables**
2. Click **"New Variable"** and add:

```
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxx
```

(Get your key from: https://platform.openai.com/account/api-keys)

3. Add another variable:

```
PROVIDER_MODE=real
```

4. Click **Deploy** to apply changes

### 1.3 Get Your Backend URL

1. Go to Railway project main page
2. In **Settings > Domains**, you'll see:
   ```
   https://your-project-prod.up.railway.app
   ```
3. **Copy this URL** - you'll need it in next step!

### 1.4 Verify Backend is Working

```bash
# Replace with your Railway URL
curl https://your-project-prod.up.railway.app/health

# Should return:
# {"status":"ok"}
```

✅ Backend is live!

---

## Step 2: Deploy Frontend to Vercel (5 minutes)

### 2.1 Create Vercel Project

1. Go to **https://vercel.com/dashboard**
2. Click **"New Project"**
3. Select **"Import Git Repository"**
4. Authorize GitHub
5. Select **real-time-voice-assistant** repo
6. Click **"Import"**

### 2.2 Configure Project Settings

**Project Name:** `real-time-voice-assistant` (your choice)

**Framework Preset:** Should auto-detect as **"Vite"**

**⚠️ IMPORTANT: Set Root Directory to `client`**

**Build Command:** `npm run build`

**Output Directory:** `dist`

**Install Command:** `npm install`

### 2.3 Add Environment Variables

**This connects frontend to Railway backend!**

1. In Vercel dashboard Settings, select **Environment Variables**
2. Click **"Add"**
3. Fill in:
   - **Name:** `VITE_API_BASE_URL`
   - **Value:** Paste your Railway URL from Step 1.3
     ```
     https://your-project-prod.up.railway.app
     ```
   - **Environments:** Select all (Production, Preview, Development)
4. Click **"Add Environment Variable"**

### 2.4 Deploy

1. Click **"Deploy"** button
2. Wait ~2-3 minutes for build
3. You'll get a URL like:
   ```
   https://real-time-voice-assistant.vercel.app
   ```

✅ Frontend is live!

---

## Step 3: End-to-End Testing (5 minutes)

### 3.1 Open the App

Open in browser:
```
https://real-time-voice-assistant.vercel.app
```

### 3.2 Test Connection

1. You should see the UI load
2. Click **"Connect to Server"** button
3. Allow microphone access when prompted
4. Connection status should show **"Connected ✓"**

### 3.3 Test Speech-to-Text

1. Click start recording
2. Speak clearly: **"Hey tell me about OpenAI"**
3. Release microphone
4. You should see:
   - Transcribed text in UI
   - LLM response generated
   - Audio response plays automatically

✅ End-to-end is working!

---

## Troubleshooting

### Problem: Frontend shows "Cannot connect to server"

**Solution:**
1. Verify Railway backend is running
   ```bash
   curl https://your-railway-url/health
   ```
2. In Vercel, check environment variable `VITE_API_BASE_URL` exactly matches your Railway URL
3. Wait 1-2 minutes after Vercel build (caching)
4. Hard refresh browser (Cmd+Shift+R on Mac)

### Problem: "Compiling error in Vercel build"

**Solution:**
1. Verify you set root directory to `client` in Vercel settings
2. Rebuild locally:
   ```bash
   cd client && npm install && npm run build
   ```
3. If error persists, check client/src/vite-env.d.ts exists

### Problem: Audio doesn't play

**Solution:**
1. Check browser console (F12) for errors
2. Verify OpenAI API key in Railway (Settings > Variables)
3. Check you're using a recent Chrome/Firefox/Safari
4. Refresh page

---

## Next Steps

### Monitoring

**Watch your backend:**
- Railway dashboard → Metrics
- Check CPU, Memory usage

**Watch your frontend:**  
- Vercel dashboard → Analytics
- Check error rates, response times

### Configuration

**Need to update later?**

Environment variables: Go to same Settings > Environment Variables page

Updates: Just push to GitHub `main` branch, both Vercel and Railway auto-deploy

### Scaling

As you get users:
- Vercel: Already handles infinite scale via CDN
- Railway: Upgrade plan if needed (Settings > Plan)

---

## File Reference

📁 Key files created for deployment:

**Backend:**
- `Dockerfile` - Container definition
- `railway.json` - Railway configuration
- `.dockerignore` - Build optimization
- `.env.production` - Template for env vars

**Frontend:**
- `client/vercel.json` - Vercel configuration
- `client/src/vite-env.d.ts` - TypeScript types
- `client/.env.example` - Environment template

**Documentation:**
- `DEPLOYMENT_GUIDE.md` - Full detailed guide
- `setup-deployment.sh` - Verification script
- `TROUBLESHOOTING_GUIDE.md` - Issue reference

---

## Success! 🎉

Your real-time voice assistant is now live on:
- **Frontend:** https://real-time-voice-assistant.vercel.app
- **Backend:** https://your-project-prod.up.railway.app/health

Share the frontend URL with users. They can start using it immediately!

---

## Support

- **Vercel Help:** https://vercel.com/support
- **Railway Help:** https://railway.app/support
- **Full Guide:** See `DEPLOYMENT_GUIDE.md`
- **Issues:** See `TROUBLESHOOTING_GUIDE.md`

---

**Deployment Date:** March 5, 2026  
**Status:** Ready for Production ✅
