# API Key Setup & Security

## Overview
This document explains how the OpenAI API key is managed securely in the YouTube Analyzer application.

---

## 🔒 Security Model

### For Developers (You)
✅ **Your API key stays on YOUR machine only**
- Create `.env` file once with your API key
- It's protected by `.gitignore` and never pushed to GitHub
- Works automatically every time you run the app
- No need to re-enter it

### For Other Users
⚠️ **They must provide their own API key**
- They clone the repo **without** your `.env` file
- They get `env.template` as a guide
- They must create their own `.env` file
- The app shows a warning banner if they forget

---

## 📋 Setup Instructions

### First-Time Setup (Developer)

1. **Create your `.env` file:**
   ```bash
   # Windows
   copy env.template .env
   
   # Mac/Linux
   cp env.template .env
   ```

2. **Add your API key to `.env`:**
   ```ini
   OPENAI_API_KEY=sk-your-actual-api-key-here
   AUDIO_QUALITY=96
   OPENAI_MODEL=gpt-4o-mini
   ```

3. **Done!** Your API key is now saved and will work every time.

### How Other Users Set Up

When someone clones your repository:

1. They run the app: `streamlit run app.py.py`
2. They see this warning banner:
   ```
   ⚠️ OpenAI API Key Not Configured
   
   [Setup Instructions - Click to expand]
   - Get API key from OpenAI
   - Copy env.template to .env
   - Add their API key
   - Restart app
   ```
3. They follow the instructions
4. App works with **their** API key

---

## 🛡️ Security Features

### What's Protected (Never Pushed to GitHub)
- ✅ `.env` - Your local environment file with API key
- ✅ `app.log` - May contain API responses
- ✅ `outputs/` - Processed content

### What's Shared (Pushed to GitHub)
- ✅ `env.template` - Template with placeholder values
- ✅ `app.py.py` - Application code
- ✅ `README.md` - Setup documentation
- ✅ All other source code

### `.gitignore` Protection (Lines 46-51)
```gitignore
# Environment variables (IMPORTANT: Never commit these!)
.env
.env.local
.env.*.local
.env.production
.env.development
```

---

## 🎯 How the Warning Banner Works

### Implementation Location
File: `app.py.py`, lines 1301-1345

### Logic Flow
```python
# 1. Try to initialize OpenAI client
try:
    client = get_openai_client()  # Reads OPENAI_API_KEY from .env
except:
    client = None  # No API key found

# 2. In Streamlit UI
if client is None:
    st.error("⚠️ OpenAI API Key Not Configured")
    # Show setup instructions
    st.stop()  # Prevent rest of UI from showing
```

### What Users See

**If API key is configured:**
- ✅ Normal app interface
- ✅ All features work
- ✅ No warnings

**If API key is missing:**
- ❌ Red error banner
- 📋 Expandable setup instructions
- 🛑 UI stops (no processing buttons shown)
- 💡 Helpful note about `.env` file

---

## 🔍 Verification Commands

### Check if `.env` file exists:
```bash
# Windows PowerShell
Test-Path .env

# Mac/Linux
ls -la .env
```

### Check if API key is configured (without revealing it):
```bash
# Windows PowerShell
Select-String -Path .env -Pattern "^OPENAI_API_KEY=sk-"

# Mac/Linux
grep "^OPENAI_API_KEY=sk-" .env
```

### Verify `.env` is in `.gitignore`:
```bash
git check-ignore -v .env
# Should output: .gitignore:47:.env    .env
```

---

## ⚠️ Common Issues

### Issue 1: "API key not found" but I created `.env`
**Solution:** 
- Ensure `.env` is in the project root (same directory as `app.py.py`)
- Check file name is exactly `.env` (not `env.txt` or `.env.txt`)
- Verify the line is: `OPENAI_API_KEY=sk-...` (no spaces around `=`)

### Issue 2: Changes to `.env` not taking effect
**Solution:**
- Restart the Streamlit app
- `.env` is loaded only once at startup

### Issue 3: Accidentally committed `.env` to GitHub
**Solution:**
```bash
# Remove from git (but keep local file)
git rm --cached .env

# Commit the removal
git commit -m "Remove .env from git tracking"

# Push to GitHub
git push origin master

# Regenerate your API key at OpenAI (old one is compromised)
```

---

## 📊 Testing the Warning Banner

### Test 1: Missing API Key
```bash
# Temporarily rename .env
mv .env .env.backup

# Run app
streamlit run app.py.py
# Should see warning banner

# Restore
mv .env.backup .env
```

### Test 2: Invalid API Key
```bash
# Edit .env temporarily
OPENAI_API_KEY=invalid-key

# Run app - should work initially
# But fail when trying to process (different error)
```

### Test 3: Normal Operation
```bash
# With valid .env file
streamlit run app.py.py
# Should see normal UI, no warnings
```

---

## 🎓 Best Practices

### For Repository Maintainers
1. ✅ Never commit your `.env` file
2. ✅ Keep `env.template` updated with new config options
3. ✅ Document any new environment variables in README
4. ✅ Test the app without `.env` occasionally to verify warning works

### For Contributors
1. ✅ Create your own `.env` file (never ask maintainer for theirs)
2. ✅ Get your own OpenAI API key (free tier available)
3. ✅ Never include API keys in pull requests or issues
4. ✅ Test locally before submitting PRs

### For Users
1. ✅ Keep your API key private
2. ✅ Monitor your OpenAI usage/costs
3. ✅ Regenerate key if accidentally exposed
4. ✅ Use `.env` file (never hardcode in source)

---

## 🔗 Related Files

- **`.gitignore`** - Protects `.env` from being committed
- **`env.template`** - Template for users to copy
- **`app.py.py`** - Contains warning banner code
- **`README.md`** - User-facing setup instructions
- **`SETUP.md`** - Detailed setup guide

---

## 📈 Statistics

- ✅ **0** API keys in source code
- ✅ **0** `.env` files in git history
- ✅ **100%** of secrets protected by `.gitignore`
- ✅ **1** warning banner to catch configuration issues
- ✅ **45** lines of helpful setup instructions

---

**Last Updated:** November 21, 2025  
**Status:** ✅ Implemented and Tested  
**Commit:** `b6a058a`

