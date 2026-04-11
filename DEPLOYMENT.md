# 🚀 Deployment Guide for Render

## Quick Deploy

This app is optimized for deployment on [Render](https://render.com/).

### Prerequisites
- Git repository with your code
- Remove.bg API key
- Cloudinary account credentials

### Step-by-Step Deployment

#### 1. Push to GitHub
```bash
git add .
git commit -m "Prepare for deployment"
git push origin main
```

#### 2. Create Web Service on Render
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **New +** → **Web Service**
3. Connect your GitHub repository
4. Configure the service:
   - **Name**: `passport-photo-pro` (or your choice)
   - **Region**: Choose closest to your users
   - **Branch**: `main`
   - **Root Directory**: Leave blank
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

#### 3. Set Environment Variables
In Render dashboard, go to **Environment** tab and add:

```
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
REMOVE_BG_API_KEY=your_remove_bg_key
```

**OR** use the Settings UI after deployment:
1. Visit `https://your-app.onrender.com/settings`
2. Upload your `.env` file or enter credentials manually
3. Click **Save Settings**

#### 4. Deploy
Click **Create Web Service** and wait for deployment to complete.

---

## 📦 What's Included for Deployment

### Files Created:
- ✅ `requirements.txt` - Clean, minimal dependencies (7 packages instead of 147)
- ✅ `runtime.txt` - Specifies Python 3.11.9
- ✅ `Procfile` - Tells Render how to start the app
- ✅ `settings.json` - Persistent settings storage (auto-created)

### Optimizations:
- Removed 140+ unnecessary packages (TensorFlow, OpenCV, mediapipe, etc.)
- Fixed Python version compatibility issues
- Reduced build time from ~10 minutes to ~2 minutes
- Smaller deployment footprint

---

## 🔧 Troubleshooting

### Build Fails
**Problem**: `ERROR: No matching distribution found for mediapipe==0.10.14`
**Solution**: Already fixed! The new `requirements.txt` doesn't include mediapipe.

### Import Errors
**Problem**: `ModuleNotFoundError: No module named 'xyz'`
**Solution**: The app only needs these packages:
- Flask
- Pillow
- requests
- python-dotenv
- cloudinary
- gunicorn

If you get an error, verify `requirements.txt` has all dependencies.

### Settings Not Persisting
**Problem**: Have to re-enter API keys after restart
**Solution**: 
- Check that `settings.json` exists in your project
- Verify it's NOT in `.gitignore` for production (it should be ignored in dev)
- Use Render Environment Variables instead (recommended for production)

### App Starts but Images Don't Process
**Problem**: API errors during image processing
**Solution**:
1. Check Render logs for error messages
2. Verify API keys are correct in Environment Variables
3. Test at `/settings` page using the **Test Configuration** button

---

## 🎯 Post-Deployment Checklist

- [ ] App loads at `https://your-app.onrender.com`
- [ ] Settings page accessible at `/settings`
- [ ] API keys configured (via env vars or settings UI)
- [ ] Test image upload and PDF generation
- [ ] Verify 4R paper size shows 3 photos per row
- [ ] Test feedback form sends emails
- [ ] Check all paper sizes work correctly

---

## 📝 Environment Variables (Alternative to Settings UI)

You can set these in Render's Environment tab instead of using the settings UI:

```env
CLOUDINARY_CLOUD_NAME=doti6peqv
CLOUDINARY_API_KEY=753695856529428
CLOUDINARY_API_SECRET=dgOueofEhU8xnLwySek2GeTxkx0
REMOVE_BG_API_KEY=bZ5HFTALnGZQxRsPw4TbN1Nr
```

**Recommended**: Use Render's Environment Variables for production (more secure).

---

## 🔄 Updating the App

After making changes:
```bash
git add .
git commit -m "Update description"
git push origin main
```

Render will automatically redeploy.

---

## 💡 Tips

1. **Free Tier**: Render free instances sleep after 15 minutes of inactivity
2. **First Load**: May take 30-60 seconds after waking up
3. **Logs**: Check Render dashboard → Logs for debugging
4. **Custom Domain**: Add custom domain in Render settings
5. **HTTPS**: Automatically enabled by Render

---

## 🆘 Support

If you encounter issues:
1. Check Render logs first
2. Verify all environment variables are set
3. Test API keys at `/settings` page
4. Review this guide's troubleshooting section
