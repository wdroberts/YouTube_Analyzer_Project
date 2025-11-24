# 📊 YouTube Analyzer - User Guide

## What This Application Does

**YouTube Analyzer** is a powerful content analysis tool that automatically transcribes, summarizes, and extracts insights from both YouTube videos and documents (PDFs, Word, TXT files). It uses cutting-edge AI technology to help you quickly understand and organize large amounts of content.

### Key Capabilities:
- 🎬 **YouTube Video Analysis**: Automatically download audio, transcribe with timestamps, and analyze content
- 📄 **Document Processing**: Extract and analyze text from PDF, DOCX, and TXT files
- 🤖 **AI-Powered Insights**: Generate summaries and extract key factors using GPT-4
- 🗄️ **Smart Database**: Store and search all your analyzed content
- 🔍 **Full-Text Search**: Find any word or phrase across all your projects instantly
- 📊 **Statistics Dashboard**: Track your analysis history and productivity

---

## How to Use the User Interface

### 🚀 Getting Started

#### First-Time Setup (One-Time Only)
1. **API Key Configuration**: On first launch, you'll be prompted to set up your OpenAI API key
2. **Migration**: If you have existing projects, they'll be automatically migrated to the new database
3. **Ready to Go**: Once setup is complete, you're ready to analyze content!

---

### 📍 Main Navigation

The application has **two main pages** accessible from the left sidebar:

#### 1️⃣ **Process Page** (Default)
Where you analyze new content - videos and documents

#### 2️⃣ **Database Explorer Page**
Where you browse, search, and manage your analyzed projects

---

## 🎬 Process Page - Analyzing New Content

### Tab 1: 📹 YouTube Video

**Purpose**: Transcribe and analyze YouTube videos

**How to Use**:
1. **Paste YouTube URL**: Enter any YouTube video URL (youtube.com, youtu.be, or shorts)
2. **Choose Transcription Method**:
   - **OpenAI Whisper API** (Recommended): Fast, cloud-based, accurate
   - **Local GPU**: Use your own GPU (requires setup, faster for large batches)
3. **Click "Process Video"**: The app will:
   - Download audio (automatically deleted after processing to save space)
   - Transcribe with timestamps
   - Generate summary
   - Extract key factors
   - Save everything to database

**Processing Time**: 2-5 minutes for typical 10-30 minute videos

**What You Get**:
- 📝 Full transcript (plain text)
- ⏱️ Time-stamped transcript (with clickable timestamps)
- 📺 SRT subtitle file (for video players)
- 📋 AI-generated summary (4-6 paragraphs)
- 🎯 Key factors (main ideas, insights, quotes, actionable items)

### Tab 2: 📄 Document Analysis

**Purpose**: Extract and analyze text from uploaded documents

**How to Use**:
1. **Upload File**: Drag and drop or click to upload
   - **Supported formats**: PDF, DOCX (Word), TXT
   - **Size limits**: 
     - PDFs: Max 500 pages
     - All files: Max 50,000 characters per page
2. **Click "Process Document"**: The app will:
   - Extract all text
   - Generate summary
   - Extract key factors
   - Save to database

**What You Get**:
- 📝 Extracted text
- 📋 AI-generated summary
- 🎯 Key factors

---

## 🗄️ Database Explorer Page

Access this page by clicking **"Database Explorer"** in the left sidebar navigation.

### Tab 1: 📊 Table Viewer

**Purpose**: Browse all your projects in a sortable table

**Features**:
- **Sortable Columns**: Click any column header to sort
- **Pagination**: Navigate through projects (10, 25, 50, or 100 per page)
- **Project Details**: Click to expand and see:
  - Full project information
  - Preview of transcript/summary
  - Download buttons for all files
  - Tags management
  - Notes (add personal annotations)

**How to Use**:
1. Select how many projects per page
2. Click any row to expand details
3. Use "Download" buttons to get text files
4. Add tags to organize projects
5. Add notes for personal reference

### Tab 2: 🔍 Advanced Search

**Purpose**: Find specific content across all projects

**Search Types**:

1. **Metadata Search** (Default)
   - Search by title, date range, type (video/document)
   - Filter by tags
   - Fast and efficient

2. **Full-Text Content Search** (Toggle on for deep search)
   - Search inside transcript and summary content
   - Find any word or phrase
   - Supports advanced syntax:
     - **Quotes** for exact phrases: `"machine learning"`
     - **OR** operator: `python OR javascript`
     - **Exclusion**: `-tensorflow` (exclude term)

3. **Combined Search**
   - Search both metadata AND content simultaneously
   - Most comprehensive option

**How to Use**:
1. Enter search terms in the search box
2. Select search mode (Metadata / Full-Text / Combined)
3. Apply filters (type, tags, dates)
4. Click "Search"
5. View results with highlighted matches
6. Click any result to see full details

### Tab 3: 📈 Statistics

**Purpose**: Visualize your analysis activity and productivity

**Metrics Displayed**:
- Total projects analyzed (videos vs documents)
- Total words processed
- Average words per project
- Most used tags (bar chart)
- Projects created over time (line chart)
- Database storage size

**Use Cases**:
- Track your research progress
- See which topics you analyze most (via tags)
- Monitor storage usage

### Tab 4: 🛠️ Schema & Tools

**Purpose**: Advanced database management and data export

**Features**:

1. **Schema Explorer**
   - View database structure
   - See table names, columns, data types
   - Understand relationships

2. **Data Export**
   - **Export to CSV**: Download project table as spreadsheet
   - **Export to JSON**: Download complete database backup
   - **Backup Database**: Create timestamped database backup

3. **Database Maintenance**
   - View database file location
   - Check database size
   - Verify integrity

**When to Use**:
- Backing up before major changes
- Exporting data for analysis in Excel/Python
- Understanding database structure
- Creating regular backups

---

## 📁 Left Sidebar - Project History

### Quick Access Panel

**Purpose**: Quickly access recent projects

**Features**:
- 🔍 **Quick Search**: Filter projects by name
- **Recent Projects**: Last 20 projects, newest first
- **Expandable Cards**: Click to view details
- **Thumbnail Preview**: Videos show YouTube thumbnails
- **Quick Actions**: 
  - View summaries inline
  - Download key factors
  - See project metadata

**How to Use**:
1. Type in search box to filter
2. Click any project card to expand
3. View details without leaving current page
4. Click file names to download

---

## 💡 Pro Tips

### Processing Videos
- ✅ **Best for**: Educational content, interviews, podcasts, lectures
- ⚡ **Large files**: Automatically split and processed (up to 125MB)
- 🔊 **Audio quality**: Works with any YouTube audio quality
- 📱 **Formats**: Supports standard YouTube, Shorts, and youtu.be links

### Processing Documents
- ✅ **Best for**: Research papers, reports, articles, books
- 📄 **PDFs**: Extracts text even from image-based PDFs (if text layer exists)
- 📝 **Word docs**: Preserves paragraph structure
- 🔤 **Encoding**: Auto-detects text encoding for TXT files

### Organizing Projects
- 🏷️ **Tags**: Add multiple tags per project (e.g., "Research", "Work", "AI")
- 📝 **Notes**: Add personal context or reminders
- 🔍 **Search**: Use tags and notes to quickly find related projects

### Storage Efficiency
- 🗑️ **Audio files**: Automatically deleted after transcription (saves ~80MB per video)
- 💾 **Database**: Stores all searchable text content
- 📄 **Text files**: Small files kept for easy access and download
- 💿 **Location**: All data stored on D: drive (configurable in .env)

---

## 🎯 Common Workflows

### Research Workflow
1. Analyze multiple videos/papers on a topic
2. Tag them all with the research topic
3. Use full-text search to find specific concepts
4. Export summaries to CSV for comparison
5. Add notes with your insights

### Learning Workflow
1. Process educational videos/lectures
2. Use time-stamped transcripts to review specific sections
3. Export key factors for study notes
4. Track progress with statistics dashboard

### Content Curation Workflow
1. Process interesting content throughout the week
2. Use quick search in sidebar to find projects
3. Review summaries to recall content
4. Share extracted insights with team (export files)

---

## ⚙️ Settings & Configuration

### File Locations (from .env)
- `DATA_ROOT`: Main data directory (default: D:/Documents/.../Data)
- `OPENAI_API_KEY`: Your OpenAI API key (required)

### Processing Limits
- **PDF Pages**: Max 500 pages
- **Audio Files**: Auto-split if >24MB
- **Page Characters**: Max 50,000 per page

---

## 🆘 Troubleshooting

### "API Key Not Configured"
- Check that `.env` file exists in project root
- Verify `OPENAI_API_KEY=sk-...` is set correctly
- Restart the application

### Video Processing Fails
- Verify YouTube URL is correct
- Check internet connection
- Try a different video to test
- Check logs in `app.log`

### Document Upload Fails
- Verify file format (PDF, DOCX, TXT only)
- Check file isn't corrupted
- Try a smaller document first
- Check file size limits

### Search Returns No Results
- Try broader search terms
- Toggle full-text search on
- Check spelling
- Verify projects are in database

---

## 📞 Need More Help?

- **README.md**: Detailed technical documentation
- **SETUP.md**: Setup and installation guide
- **app.log**: Check application logs for errors
- **Database backup**: Regular backups prevent data loss

---

**Version**: 2.0 with Database Integration  
**Last Updated**: November 2025

---

*Your API key stays secure on your machine and is never shared or committed to version control.*

