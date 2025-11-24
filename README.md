# 🎬 YouTube Analyzer Project

> AI-powered YouTube video and document analyzer with transcription, summarization, and intelligent insights extraction using OpenAI Whisper and GPT-4.

[![Tests](https://github.com/wdroberts/YouTube_Analyzer_Project/actions/workflows/tests.yml/badge.svg)](https://github.com/wdroberts/YouTube_Analyzer_Project/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## ✨ Features

### 🎥 YouTube Video Analysis
- **Hybrid Transcription** - Choose between Local GPU (2x faster, FREE) or OpenAI API (best quality)
- **Local GPU Support** - Leverage your NVIDIA GPU for fast, free transcription
- **No Size Limits** - Automatic audio chunking for videos of any length (handles 25MB+ files)
- **Timestamped Transcripts** - Precise timestamps for every segment
- **SRT Subtitle Generation** - Export subtitles in industry-standard format
- **Smart Summaries** - AI-generated 4-6 paragraph summaries
- **Key Insights Extraction** - Main ideas, quotes, statistics, and actionable takeaways
- **Real-time Progress** - Visual progress bar with step-by-step updates

### 📄 Document Analysis  
- **Multi-format Support** - PDF, DOCX, and TXT files
- **Text Extraction** - Accurate text extraction from documents
- **Intelligent Summarization** - Concise summaries of long documents
- **Key Factor Analysis** - Extract important points and insights
- **Content Titling** - Automatic descriptive title generation

### 🗄️ Database & Organization
- **SQLite Database** - Fast, reliable project storage with full-text search
- **Full-Text Search** - Search within transcripts and summaries using FTS5
- **Tag System** - Organize projects with custom tags
- **Notes** - Add personal notes to any project
- **Statistics Dashboard** - View analytics on your processed content
- **Export Tools** - Export database as JSON or CSV
- **D: Drive Storage** - All data stored on configurable location (default: D: drive)

### 🎯 Advanced Features
- **Database Explorer** - Comprehensive UI for browsing and managing projects
- **Advanced Search** - Filter by type, tags, date, and content
- **Project History** - Organized history with quick search
- **Batch Management** - Easy access to previous projects
- **Download Options** - Export transcripts, summaries, and metadata
- **Content-based Titles** - AI-generated titles from transcript content
- **Error Handling** - Robust retry logic and graceful failure handling
- **Progress Tracking** - 11-step progress for videos, 9-step for documents
- **Automatic Migration** - Seamlessly migrate existing projects to new database

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))
- FFmpeg (for audio processing)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/wdroberts/YouTube_Analyzer_Project.git
   cd YouTube_Analyzer_Project
   ```

2. **Create virtual environment** (recommended)
   ```bash
   python -m venv .venv
   
   # Windows
   .venv\Scripts\activate
   
   # Mac/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   # Windows
   copy env.template .env
   
   # Mac/Linux
   cp env.template .env
   ```
   
   Edit `.env` and add your OpenAI API key:
   ```
   OPENAI_API_KEY=sk-your-actual-api-key-here
   ```

5. **Run the application**
   ```bash
   streamlit run app.py.py
   ```
   
   Or use the provided launcher:
   ```bash
   # Windows
   start_app.bat
   ```

6. **Open your browser**
   
   The app will automatically open at `http://localhost:8501`

---

## 📖 Usage

### Analyzing a YouTube Video

1. Select **"YouTube Video"** mode
2. Paste a YouTube URL (standard, shorts, or youtu.be format)
3. Click **"Process Video"**
4. Watch the progress bar update through 6 processing steps
5. Download transcripts, summaries, and subtitles

### Analyzing a Document

1. Select **"Document File"** mode
2. Upload a PDF, DOCX, or TXT file
3. Click **"Process Document"**
4. Watch the progress through 4 processing steps
5. Download extracted text, summaries, and insights

### Managing Projects

#### Quick Access (Sidebar)
- View recent projects in the **Project History** sidebar
- Use quick search to filter projects by title
- Click any project to see details (date, word count, tags)
- Delete individual projects or clear all history

#### Database Explorer
- Navigate to **Database Explorer** page for advanced management
- **Table Viewer**: Browse all projects with sorting and pagination
- **Advanced Search**: Search by metadata (type, tags, date) or full-text content
- **Tags & Notes**: Add custom tags and notes to organize projects
- **Statistics Dashboard**: View analytics (total projects, words, top tags, timeline)
- **Export**: Export database as JSON or CSV, create backups

---

## 🎨 Screenshots

### Main Interface
*Coming soon - Video analysis interface with progress tracking*

### Project History
*Coming soon - Sidebar showing processed projects*

### Results View
*Coming soon - Transcript, summary, and download options*

---

## 🔧 Configuration

All configuration is done via the `.env` file. See `env.template` for all available options.

### Essential Settings

```bash
# Required
OPENAI_API_KEY=sk-your-key-here

# Recommended
AUDIO_QUALITY=96              # 32-320 kbps (96 recommended)
OPENAI_MODEL=gpt-4o-mini      # Model for summaries
DATA_ROOT=D:\Documents\Software_Projects\YouTube_Analyzer_Project\Data  # Storage location
```

### Advanced Settings

```bash
MAX_AUDIO_FILE_SIZE_MB=24     # Whisper API limit
RATE_LIMIT_SECONDS=5          # Cooldown between requests
LOG_LEVEL=INFO                # Logging verbosity
```

### Data Storage

By default, all output files and the database are stored at:
```
D:\Documents\Software_Projects\YouTube_Analyzer_Project\Data\
├── youtube_analyzer.db       # SQLite database
└── outputs\                  # Project output files
    ├── <video_id>\
    │   ├── audio.mp3
    │   ├── transcript.txt
    │   ├── transcript_with_timestamps.txt
    │   ├── transcript.srt
    │   ├── summary.txt
    │   ├── key_factors.txt
    │   └── metadata.json
    └── ...
```

You can customize the storage location by setting `DATA_ROOT` in your `.env` file.

### First-Time Migration

When you first run the updated application with existing projects:
1. The app will detect old projects in the `./outputs` folder
2. Automatic migration will start, showing progress
3. Projects are copied to the new D: drive location
4. All projects are imported into the SQLite database
5. Old files are backed up to `./backups` folder for safety

The migration is non-destructive and creates backups automatically.

See [env.template](env.template) for complete configuration reference.

---

## 📊 Technical Details

### Architecture

```
┌─────────────────┐
│  Streamlit UI   │ ← User interface layer
└────────┬────────┘
         │
┌────────▼────────┐
│ Business Logic  │ ← Processing functions (testable)
└────────┬────────┘
         │
┌────────▼────────┐
│   APIs & I/O    │ ← OpenAI, yt-dlp, file operations
└─────────────────┘
```

### Key Technologies

- **Frontend**: Streamlit (Python web framework)
- **Database**: SQLite with FTS5 (Full-Text Search)
- **Transcription**: OpenAI Whisper API + faster-whisper (local GPU)
- **Summarization**: GPT-4o-mini (or GPT-4)
- **Video Download**: yt-dlp
- **Document Parsing**: PyPDF2, python-docx
- **Data Visualization**: Pandas for analytics
- **Testing**: pytest with 65 automated tests
- **CI/CD**: GitHub Actions

### Processing Pipeline

#### YouTube Videos (7 Steps)
1. 🎬 Validate URL and create session
2. ⬇️ Download audio (MP3 format)
3. 🎤 Transcribe with Whisper (API or Local GPU)
4. 💾 Save transcripts (TXT, SRT, timestamped)
5. 📝 Generate AI summary
6. 🎯 Extract key factors and create title
7. 🗄️ Save to database with full-text indexing

#### Documents (5 Steps)
1. 📄 Extract text from file
2. 📝 Generate AI summary  
3. 🎯 Extract key factors
4. 📋 Create descriptive title
5. 🗄️ Save to database with full-text indexing

### Database Schema

The application uses SQLite with the following structure:

```sql
projects (id, type, title, content_title, source, created_at, 
          word_count, segment_count, project_dir, notes)
          
tags (id, name)

project_tags (project_id, tag_id)  -- Many-to-many relationship

project_content_fts (FTS5 virtual table for full-text search)
  - project_id, transcript_text, summary_text, key_factors_text
```

**Features:**
- Full-text search across all content using SQLite FTS5
- Tag-based organization with many-to-many relationships
- Indexed queries for fast filtering and sorting
- Automatic backup and export functionality

---

## 🧪 Testing

The project includes comprehensive automated testing with **65 test cases** and **87.7% pass rate**.

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=. --cov-report=html

# Open coverage report
start htmlcov/index.html  # Windows
open htmlcov/index.html   # Mac
```

### Test Coverage

- **Utility Functions**: 86.5% (32 tests)
- **Configuration**: 82.4% (17 tests)
- **File Operations**: 100% (11 tests)

See [tests/README.md](tests/README.md) for detailed testing documentation.

---

## 📁 Project Structure

```
YouTube_Analyzer_Project/
├── app.py.py                      # Main application
├── requirements.txt               # Python dependencies
├── env.template                   # Configuration template
├── start_app.bat                  # Windows launcher
├── pytest.ini                     # Test configuration
│
├── tests/                         # Test suite
│   ├── test_utilities.py         # Utility function tests
│   ├── test_config.py            # Configuration tests
│   └── test_file_operations.py   # File I/O tests
│
├── outputs/                       # Processed content (gitignored)
│   └── [session-id]/             # Individual processing sessions
│       ├── audio.mp3             # Downloaded audio
│       ├── transcript.txt        # Plain transcript
│       ├── transcript.srt        # Subtitle file
│       ├── summary.txt           # AI summary
│       ├── key_factors.txt       # Extracted insights
│       └── metadata.json         # Session metadata
│
├── .github/workflows/            # CI/CD pipelines
│   └── tests.yml                 # Automated testing
│
└── docs/                         # Documentation
    ├── DIAGNOSIS.md              # Processing issue analysis
    ├── IMPROVEMENTS_SUMMARY.md   # Best practices implementation
    ├── PROGRESS_BAR_FIX.md       # Progress system details
    └── TESTING_IMPLEMENTATION.md  # Testing infrastructure
```

---

## 🔒 Security & Privacy

### Data Handling
- ✅ All processing happens locally on your machine
- ✅ Files are only sent to OpenAI APIs (Whisper, GPT)
- ✅ No data is stored on external servers
- ✅ Downloaded audio files stored in local `outputs/` directory
- ✅ `.env` file protected by `.gitignore`

### API Keys
- ⚠️ **Never commit your `.env` file**
- ⚠️ Keep your `OPENAI_API_KEY` secret
- ⚠️ Review OpenAI's [data usage policy](https://openai.com/policies/api-data-usage-policies)

### Best Practices
- Use environment variables for all secrets
- Regenerate API keys if accidentally exposed
- Monitor your OpenAI usage and billing
- Keep dependencies up to date

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Ways to Contribute
- 🐛 Report bugs
- 💡 Suggest new features
- 📝 Improve documentation
- 🧪 Add more tests
- 🎨 Enhance UI/UX
- 🌍 Add translations

### Development Setup

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Install dev dependencies (`pip install -r requirements.txt`)
4. Make your changes
5. Run tests (`pytest tests/ -v`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) (coming soon) for detailed guidelines.

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

### Technologies & Libraries
- [OpenAI](https://openai.com/) - Whisper and GPT APIs
- [Streamlit](https://streamlit.io/) - Web application framework
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube video downloader
- [PyPDF2](https://github.com/py-pdf/pypdf2) - PDF processing
- [python-docx](https://python-docx.readthedocs.io/) - DOCX processing

### Inspiration
Built to make video content and documents more accessible and analyzable through AI-powered insights.

---

## 📞 Support

### Documentation
- [Setup Guide](env.template) - Configuration reference
- [Hybrid Transcription](HYBRID_TRANSCRIPTION.md) - Local GPU vs OpenAI API guide
- [Audio Chunking](AUDIO_CHUNKING.md) - How large files are handled
- [Testing Guide](tests/README.md) - How to run tests
- [Technical Docs](docs/) - Implementation details

### Issues
Found a bug or have a suggestion? [Open an issue](https://github.com/wdroberts/YouTube_Analyzer_Project/issues)

### Contact
- **GitHub**: [@wdroberts](https://github.com/wdroberts)
- **Project**: [YouTube_Analyzer_Project](https://github.com/wdroberts/YouTube_Analyzer_Project)

---

## 🗺️ Roadmap

### Planned Features
- [ ] Batch processing of multiple videos
- [ ] Support for other video platforms (Vimeo, etc.)
- [ ] Multi-language transcription support
- [ ] Export to more formats (DOCX, PDF)
- [ ] Integration with note-taking apps
- [ ] Customizable AI prompts
- [ ] Cost estimation before processing
- [ ] Video length and duration detection

### In Progress
- [x] ✅ Comprehensive testing infrastructure
- [x] ✅ Environment variable configuration
- [x] ✅ GitHub Actions CI/CD

### Completed
- [x] ✅ YouTube video transcription
- [x] ✅ Automatic audio chunking for large files
- [x] ✅ Document analysis
- [x] ✅ Real-time progress tracking
- [x] ✅ Project history management
- [x] ✅ Retry logic and error handling
- [x] ✅ Type hints and documentation

---

## 📈 Stats

![GitHub stars](https://img.shields.io/github/stars/wdroberts/YouTube_Analyzer_Project?style=social)
![GitHub forks](https://img.shields.io/github/forks/wdroberts/YouTube_Analyzer_Project?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/wdroberts/YouTube_Analyzer_Project?style=social)

---

<p align="center">
  Made with ❤️ using Python, Streamlit, and OpenAI
  <br>
  <a href="#-youtube-analyzer-project">↑ Back to Top</a>
</p>

