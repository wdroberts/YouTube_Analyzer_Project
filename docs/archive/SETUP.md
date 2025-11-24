# 🚀 Setup Guide - YouTube Analyzer Project

Complete step-by-step guide to get the YouTube Analyzer up and running.

---

## 📋 Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation Steps](#installation-steps)
3. [Configuration](#configuration)
4. [First Run](#first-run)
5. [Troubleshooting](#troubleshooting)
6. [Advanced Setup](#advanced-setup)

---

## 🖥️ System Requirements

### Minimum Requirements
- **OS**: Windows 10+, macOS 10.14+, or Linux
- **Python**: 3.9 or higher
- **RAM**: 4GB minimum (8GB recommended)
- **Disk Space**: 500MB for application + space for processed files
- **Internet**: Required for API calls and video downloads

### Required Software
- Python 3.9+ ([Download](https://www.python.org/downloads/))
- FFmpeg ([Download](https://ffmpeg.org/download.html))
- Git (optional, for cloning repository)

### API Requirements
- OpenAI API key with Whisper and GPT access
- Active OpenAI account with available credits

---

## 📦 Installation Steps

### Step 1: Get the Code

**Option A: Clone with Git** (recommended)
```bash
git clone https://github.com/wdroberts/YouTube_Analyzer_Project.git
cd YouTube_Analyzer_Project
```

**Option B: Download ZIP**
1. Go to https://github.com/wdroberts/YouTube_Analyzer_Project
2. Click "Code" → "Download ZIP"
3. Extract the ZIP file
4. Open terminal/command prompt in the extracted folder

### Step 2: Install FFmpeg

FFmpeg is required for audio processing.

**Windows:**
```powershell
# Using Chocolatey (recommended)
choco install ffmpeg

# Or download manually from https://ffmpeg.org/download.html
# Add to PATH after installation
```

**macOS:**
```bash
# Using Homebrew
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Verify installation:**
```bash
ffmpeg -version
```

### Step 3: Create Virtual Environment

Virtual environments keep dependencies isolated.

```bash
# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate

# Mac/Linux:
source .venv/bin/activate

# You should see (.venv) in your terminal prompt
```

### Step 4: Install Python Dependencies

```bash
# Make sure virtual environment is activated
pip install --upgrade pip
pip install -r requirements.txt
```

This installs:
- streamlit (web framework)
- yt-dlp (video downloader)
- openai (API client)
- PyPDF2 (PDF processing)
- python-docx (Word documents)
- python-dotenv (environment variables)
- pytest (testing framework)

### Step 5: Configure Environment Variables

```bash
# Copy the template
# Windows:
copy env.template .env

# Mac/Linux:
cp env.template .env
```

Edit `.env` with your favorite text editor:
```bash
# Windows:
notepad .env

# Mac:
open -a TextEdit .env

# Linux:
nano .env
```

**Required:** Add your OpenAI API key
```ini
OPENAI_API_KEY=sk-your-actual-api-key-here
```

**Optional:** Adjust other settings
```ini
AUDIO_QUALITY=96
OPENAI_MODEL=gpt-4o-mini
```

---

## 🔑 Configuration

### Getting an OpenAI API Key

1. Go to https://platform.openai.com/signup
2. Create an account or sign in
3. Navigate to https://platform.openai.com/api-keys
4. Click "Create new secret key"
5. Copy the key (starts with `sk-`)
6. Paste it in your `.env` file

### Understanding Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | Your OpenAI API key |
| `AUDIO_QUALITY` | 96 | Audio bitrate (32-320 kbps) |
| `OPENAI_MODEL` | gpt-4o-mini | Model for summaries |
| `MAX_AUDIO_FILE_SIZE_MB` | 24 | Max file size for Whisper |
| `RATE_LIMIT_SECONDS` | 5 | Cooldown between requests |

### Choosing Audio Quality

```ini
AUDIO_QUALITY=64   # Low - smaller files, faster (10-15 min videos)
AUDIO_QUALITY=96   # Medium - recommended for speech (20-30 min videos)
AUDIO_QUALITY=128  # High - better quality (15-20 min videos)
AUDIO_QUALITY=192  # Very High - best quality (10-15 min videos)
```

**Note:** Higher quality = larger files. Whisper API has a 25MB limit.

### Choosing AI Model

```ini
OPENAI_MODEL=gpt-4o-mini      # Fastest, cheapest, recommended
OPENAI_MODEL=gpt-3.5-turbo    # Fast, affordable
OPENAI_MODEL=gpt-4            # Best quality, slower, more expensive
```

---

## ▶️ First Run

### Start the Application

**Method 1: Using the launcher (Windows)**
```bash
start_app.bat
```

**Method 2: Command line (All platforms)**
```bash
# Make sure virtual environment is activated
streamlit run app.py.py
```

### What to Expect

1. **Terminal output:**
   ```
   You can now view your Streamlit app in your browser.
   Local URL: http://localhost:8501
   Network URL: http://192.168.1.x:8501
   ```

2. **Browser opens automatically** to http://localhost:8501

3. **Application loads** - You'll see the YouTube Analyzer interface

### Test with a Simple Video

1. Select "YouTube Video" mode
2. Paste this test URL: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
3. Click "Process Video"
4. Watch the progress bar update through 6 steps
5. Download the transcript when complete

---

## 🔧 Troubleshooting

### "ModuleNotFoundError: No module named 'streamlit'"

**Solution:** Activate virtual environment and install dependencies
```bash
# Activate venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

### "ValueError: OPENAI_API_KEY environment variable is not set"

**Solution:** Check your `.env` file
```bash
# Make sure .env file exists
ls .env  # Mac/Linux
dir .env  # Windows

# Check it contains your API key
cat .env  # Mac/Linux
type .env  # Windows

# Should see:
# OPENAI_API_KEY=sk-...
```

### "Audio file is too large (XX MB)"

**Solution:** Reduce audio quality in `.env`
```ini
AUDIO_QUALITY=64  # Instead of 96 or higher
```

Or process shorter videos (under 30 minutes).

### "FFmpeg not found" or "Audio file was not created"

**Solution:** Install FFmpeg and add to PATH
```bash
# Verify FFmpeg is installed
ffmpeg -version

# If not installed, see Step 2 above
```

**Windows:** Make sure FFmpeg is in your PATH
1. Find ffmpeg.exe location
2. Add to System Environment Variables → PATH
3. Restart terminal

### Port 8501 Already in Use

**Solution:** Stop other Streamlit apps or use different port
```bash
streamlit run app.py.py --server.port 8502
```

### "Rate limit exceeded" or "Quota exceeded"

**Solution:** Check your OpenAI account
1. Visit https://platform.openai.com/account/usage
2. Check your usage limits
3. Add payment method if needed
4. Wait for rate limit to reset

### Tests Fail to Run

**Solution:** Install test dependencies
```bash
pip install pytest pytest-cov pytest-mock
```

---

## ⚙️ Advanced Setup

### Running on Different Port

```bash
streamlit run app.py.py --server.port 8080
```

### Running on Network (Access from other devices)

```bash
streamlit run app.py.py --server.address 0.0.0.0
```

Then access from other devices: `http://YOUR_IP:8501`

### Development Mode (Auto-reload)

Streamlit auto-reloads by default when you edit files.

```bash
# Watch for changes
streamlit run app.py.py
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=html

# Specific test file
pytest tests/test_utilities.py -v
```

### Production Deployment

For production deployment, consider:

1. **Use environment-specific .env files**
   ```bash
   .env.production
   .env.development
   ```

2. **Set up proper logging**
   ```ini
   LOG_LEVEL=WARNING  # Less verbose in production
   ```

3. **Use reverse proxy** (nginx, Apache)
   
4. **Enable HTTPS**

5. **Monitor API usage and costs**

### Docker Setup (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py.py", "--server.address", "0.0.0.0"]
```

Build and run:
```bash
docker build -t youtube-analyzer .
docker run -p 8501:8501 --env-file .env youtube-analyzer
```

---

## 📚 Next Steps

Once setup is complete:

1. **Read the README** - [README.md](README.md)
2. **Try processing a document** - Upload a PDF
3. **Check project history** - See your processed content
4. **Explore advanced features** - Batch processing, exports
5. **Run the tests** - `pytest tests/ -v`
6. **Customize settings** - Adjust `.env` file

---

## 🆘 Still Having Issues?

### Check Documentation
- [README.md](README.md) - Main documentation
- [tests/README.md](tests/README.md) - Testing guide
- [env.template](env.template) - Configuration reference

### Get Help
- [Open an issue](https://github.com/wdroberts/YouTube_Analyzer_Project/issues)
- Check [existing issues](https://github.com/wdroberts/YouTube_Analyzer_Project/issues?q=is%3Aissue)
- Review [GitHub Discussions](https://github.com/wdroberts/YouTube_Analyzer_Project/discussions)

### Common Resources
- [Python Installation Guide](https://realpython.com/installing-python/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)

---

## ✅ Setup Checklist

Use this checklist to track your setup progress:

- [ ] Python 3.9+ installed and verified
- [ ] FFmpeg installed and in PATH
- [ ] Repository cloned or downloaded
- [ ] Virtual environment created
- [ ] Virtual environment activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created from template
- [ ] OpenAI API key added to `.env`
- [ ] Application starts successfully
- [ ] Test video processed successfully
- [ ] Tests run successfully (optional)

---

<p align="center">
  <strong>Ready to analyze!</strong> 🎉
  <br>
  <a href="README.md">← Back to README</a>
</p>

