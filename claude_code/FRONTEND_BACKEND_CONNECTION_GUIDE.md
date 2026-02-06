# Frontend-Backend Connection Fix

**Date:** February 1, 2026
**Issue:** Frontend not connecting to new backend deployment

---

## Current Setup

### Backend (NEW - Just Deployed)
```
URL: https://knowledge-base-backend-hrjhw2yiva-uc.a.run.app
Status: ✅ Working
CORS: ✅ Already allows your Firebase domain
```

### Frontend
```
URL: https://knowledge-base-agent-55afc.web.app
Status: ✅ Loading
Issue: Still pointing to OLD backend URL
```

---

## What Changed?

**Before:** Your frontend was pointing to an old backend URL (possibly different Cloud Run service)

**Now:** You deployed a new backend, but frontend still has old URL configured

---

## Fix Steps

### **Step 1: Find Your Frontend Code**

You need to update the backend URL in your frontend. Where is your frontend code located?

Common locations:
- `/Users/melville/Documents/Propengine-KB-frontend/`
- Same repo in a `/frontend` folder?
- Different repository?

### **Step 2: Update Environment Variables**

In your frontend project, find the environment file:

**File:** `.env.production` or `.env.local`

**Change from:**
```bash
# Old backend URL (probably something like this)
NEXT_PUBLIC_API_URL=https://old-backend-xyz.a.run.app
# or
NEXT_PUBLIC_BACKEND_URL=https://old-backend-xyz.a.run.app
```

**Change to:**
```bash
# New backend URL
NEXT_PUBLIC_API_URL=https://knowledge-base-backend-hrjhw2yiva-uc.a.run.app
# or
NEXT_PUBLIC_BACKEND_URL=https://knowledge-base-backend-hrjhw2yiva-uc.a.run.app
```

### **Step 3: Check API Call Format**

In your frontend code, API calls should look like:

```javascript
// CORRECT ✅ (with trailing slash)
const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/agent/test/`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    message: userQuery,
    session_id: sessionId
  })
});

// WRONG ❌ (missing trailing slash)
const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/agent/test`, {
  // ... this will cause 307 redirect
});
```

### **Step 4: Rebuild and Redeploy Frontend**

```bash
# In your frontend project directory
cd /path/to/your/frontend

# Build with new environment
npm run build
# or
yarn build

# Deploy to Firebase
firebase deploy --only hosting
```

---

## Quick Test (Before Full Redeploy)

You can test the new backend directly from your browser console:

1. Open https://knowledge-base-agent-55afc.web.app
2. Open browser DevTools (F12)
3. Go to Console tab
4. Paste this:

```javascript
// Test new backend
fetch('https://knowledge-base-backend-hrjhw2yiva-uc.a.run.app/api/agent/test/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    message: 'test from browser console',
    session_id: 'console_test_123'
  })
})
.then(r => r.json())
.then(data => {
  console.log('✅ Backend working!', data);
  console.log('Response time:', data.debug_metrics?.total_time_ms + 'ms');
})
.catch(err => {
  console.error('❌ Backend error:', err);
});
```

**If this works** → Your backend is fine, just need to update frontend env vars
**If this fails with CORS error** → Need to debug CORS (unlikely since it's whitelisted)
**If this fails with network error** → Check backend URL is correct

---

## Alternative: Check Firebase Environment Config

If your frontend uses Firebase environment config:

```bash
# Check current Firebase config
firebase functions:config:get

# Or check if using Firebase Remote Config
```

---

## Common Issues

### **Issue 1: Hardcoded Backend URL**
```javascript
// ❌ BAD (hardcoded old URL)
const API_URL = 'https://old-backend.a.run.app';

// ✅ GOOD (use environment variable)
const API_URL = process.env.NEXT_PUBLIC_API_URL;
```

### **Issue 2: Multiple Environment Files**
- `.env` (default)
- `.env.local` (local dev)
- `.env.production` (production) ← **Check this one!**
- `.env.development` (dev builds)

Make sure you update the **production** file!

### **Issue 3: Cached Build**
```bash
# Clear Next.js cache
rm -rf .next
rm -rf out

# Rebuild
npm run build
```

---

## Expected Result After Fix

```
User visits: https://knowledge-base-agent-55afc.web.app
    ↓
Frontend loads
    ↓
User asks question
    ↓
Frontend sends to: https://knowledge-base-backend-hrjhw2yiva-uc.a.run.app/api/agent/test/
    ↓
Backend processes (6-7 seconds)
    ↓
Returns response with debug_metrics ✅
    ↓
Frontend displays answer
```

---

## Need Help Finding Frontend Code?

Run these commands:

```bash
# Search for frontend projects
find ~ -name "package.json" -path "*/node_modules" -prune -o -type f -name "package.json" -print | head -10

# Search for Firebase projects
find ~ -name "firebase.json" -type f | head -5

# Search for .env files that might have backend URL
find ~ -name ".env*" -type f -exec grep -l "backend\|API_URL\|api\.run\.app" {} \; 2>/dev/null | head -10
```

---

## Summary

**Problem:** Frontend still configured with old backend URL

**Solution:**
1. Find frontend code
2. Update `.env.production` with new backend URL
3. Add trailing slash to API endpoints
4. Rebuild and redeploy

**New Backend URL:**
```
https://knowledge-base-backend-hrjhw2yiva-uc.a.run.app
```

**Test it works** → Then update frontend → Redeploy → Done! ✅
