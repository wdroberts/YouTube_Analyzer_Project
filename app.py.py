## app.py (Corrected Application)
import streamlit as st
import yt_dlp
import json
import uuid
import shutil
import logging
import time
import os
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import re
import PyPDF2
import docx
import io
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# -----------------------------
# LOGGING CONFIGURATION
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Fix Windows console encoding for emoji support
import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass  # If reconfigure fails, continue without it

# -----------------------------
# CONFIGURATION
# -----------------------------
@dataclass
class Config:
    """Application configuration with validation."""
    audio_quality: int = int(os.getenv("AUDIO_QUALITY", "96"))
    summary_max_tokens: int = 1000
    key_factors_max_tokens: int = 1500
    title_max_tokens: int = 50
    title_sample_size: int = 2000
    project_title_max_length: int = 30
    url_display_max_length: int = 45
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    rate_limit_seconds: int = 5
    max_audio_file_size_mb: int = 24
    output_dir: Path = Path("outputs")
    max_text_input_length: int = 100000  # Max characters for API calls
    api_timeout_seconds: int = 300  # 5 minutes
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.audio_quality < 32 or self.audio_quality > 320:
            raise ValueError(f"Invalid audio quality: {self.audio_quality}. Must be between 32-320 kbps")
        if self.max_audio_file_size_mb > 25:
            raise ValueError(f"Max file size cannot exceed 25MB (Whisper API limit)")
        self.output_dir.mkdir(exist_ok=True)
        logger.info(f"Configuration initialized: audio_quality={self.audio_quality}, model={self.openai_model}")

# Initialize configuration
config = Config()

# Prompt templates
PROMPTS = {
    "summarize": """
    Summarize the following transcript into a clear, well-structured,
    4-6 paragraph narrative. Focus on key ideas, themes, and progression
    of the speaker's argument.

    Transcript:
    {text}
    """,
    "extract_title": """
    Based on the following transcript excerpt, generate a clear, concise, and descriptive title 
    that captures the main topic or theme. The title should be 5-15 words long.
    
    Return ONLY the title, nothing else.
    
    Transcript excerpt:
    {text}
    """,
    "extract_key_factors": """
    Extract key factors from this transcript.

    Return the following sections:

    1. Main Ideas
    2. Notable Insights
    3. Key Statistics or Facts
    4. Important Quotes
    5. People or Organizations Mentioned
    6. Actionable Takeaways

    Transcript:
    {text}
    """
}

# Initialize OpenAI client with error handling
def get_openai_client() -> OpenAI:
    """Get or create OpenAI client with proper error handling."""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        return OpenAI(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        raise ValueError(
            "OpenAI API key not configured. Please set OPENAI_API_KEY environment variable."
        ) from e

try:
    client = get_openai_client()
    logger.info("OpenAI client initialized successfully")
except ValueError as e:
    logger.error(str(e))
    client = None


# -----------------------------
# UTILITIES
# -----------------------------
def safe_filename(s: str) -> str:
    """Convert string to safe filename by removing special characters."""
    return re.sub(r'[^a-zA-Z0-9_\-]+', '_', s)


def validate_youtube_url(url: str) -> bool:
    """
    Validate that URL is from YouTube or YouTube Shorts.
    
    Args:
        url: URL string to validate
        
    Returns:
        True if valid YouTube URL, False otherwise
    """
    try:
        parsed = urlparse(url)
        valid_domains = ['www.youtube.com', 'youtube.com', 'youtu.be', 'm.youtube.com']
        return parsed.netloc in valid_domains
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse URL: {url}, error: {e}")
        return False


def read_file_bytes(path: Path) -> bytes:
    """
    Read file and return bytes with proper resource management.
    
    Args:
        path: Path to file to read
        
    Returns:
        File contents as bytes
        
    Raises:
        IOError: If file cannot be read
    """
    try:
        with open(path, "rb") as f:
            return f.read()
    except IOError as e:
        logger.error(f"Failed to read file {path}: {e}")
        raise


def safe_write_text(path: Path, content: str, encoding: str = "utf-8") -> bool:
    """
    Safely write text to file with error handling.
    
    Args:
        path: Path where file should be written
        content: Text content to write
        encoding: Text encoding (default: utf-8)
        
    Returns:
        True if write succeeded, False otherwise
    """
    try:
        path.write_text(content, encoding=encoding)
        logger.debug(f"Successfully wrote to {path}")
        return True
    except (IOError, OSError) as e:
        logger.error(f"Failed to write to {path}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error writing to {path}: {e}")
        return False


def truncate_title(title: str, max_length: Optional[int] = None) -> str:
    """
    Truncate title with ellipsis if too long.
    
    Args:
        title: Title string to truncate
        max_length: Maximum length (default: from config)
        
    Returns:
        Truncated title string
    """
    if max_length is None:
        max_length = config.project_title_max_length
    if len(title) > max_length:
        return title[:max_length-3] + "..."
    return title


def extract_video_id(url: str) -> str:
    """
    Extract YouTube video ID from various URL formats.
    
    Args:
        url: YouTube URL (youtube.com, youtu.be, shorts)
        
    Returns:
        Video ID string, or empty string if extraction fails
    """
    try:
        parsed = urlparse(url)
        
        if 'youtube.com' in parsed.netloc:
            # Handle /shorts/ URLs
            if '/shorts/' in parsed.path:
                return parsed.path.split('/shorts/')[1].split('/')[0]
            # Handle ?v= parameter
            elif parsed.query:
                params = parse_qs(parsed.query)
                return params.get('v', [''])[0]
        
        # Handle youtu.be URLs
        elif 'youtu.be' in parsed.netloc:
            return parsed.path.lstrip('/')
        
        return ""
    except (ValueError, IndexError, KeyError) as e:
        logger.warning(f"Failed to extract video ID from {url}: {e}")
        return ""


def format_url_for_display(url: str, max_length: Optional[int] = None) -> str:
    """
    Format URL for display, truncating if too long.
    
    Args:
        url: URL to format
        max_length: Maximum length (default: from config)
        
    Returns:
        Formatted URL string
    """
    if max_length is None:
        max_length = config.url_display_max_length
    if len(url) > max_length:
        return url[:max_length] + "..."
    return url


def format_timestamp(seconds: float) -> str:
    """
    Convert seconds into HH:MM:SS.mmm format.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string
    """
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hrs:02d}:{mins:02d}:{secs:06.3f}"


def to_srt(segments: List[Dict[str, Any]]) -> str:
    """
    Convert verbose_json segments to SRT format.
    
    Args:
        segments: List of segment dictionaries with 'start', 'end', and 'text' keys
        
    Returns:
        SRT formatted string
    """
    srt_lines = []
    for i, seg in enumerate(segments, start=1):
        start = format_timestamp(seg["start"]).replace('.', ',')
        end = format_timestamp(seg["end"]).replace('.', ',')
        text = seg["text"].strip()
        srt_lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(srt_lines)


# -----------------------------
# DOCUMENT TEXT EXTRACTION
# -----------------------------
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        file_bytes: PDF file as bytes
        
    Returns:
        Extracted text content
        
    Raises:
        Exception: If PDF cannot be read or parsed
    """
    pdf_file = io.BytesIO(file_bytes)
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = []
    for page in pdf_reader.pages:
        text.append(page.extract_text())
    return "\n\n".join(text)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """
    Extract text from a DOCX file.
    
    Args:
        file_bytes: DOCX file as bytes
        
    Returns:
        Extracted text content
        
    Raises:
        Exception: If DOCX cannot be read or parsed
    """
    docx_file = io.BytesIO(file_bytes)
    doc = docx.Document(docx_file)
    text = []
    for paragraph in doc.paragraphs:
        text.append(paragraph.text)
    return "\n\n".join(text)


def extract_text_from_txt(file_bytes: bytes) -> str:
    """
    Extract text from a TXT file.
    
    Args:
        file_bytes: TXT file as bytes
        
    Returns:
        Decoded text content
        
    Raises:
        UnicodeDecodeError: If file cannot be decoded as UTF-8
    """
    return file_bytes.decode('utf-8')


def extract_text_from_document(uploaded_file: Any) -> str:
    """
    Extract text from various document formats.
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Returns:
        Extracted text content
        
    Raises:
        ValueError: If file format is not supported
    """
    file_bytes = uploaded_file.read()
    file_name = uploaded_file.name.lower()
    
    if file_name.endswith('.pdf'):
        return extract_text_from_pdf(file_bytes)
    elif file_name.endswith('.docx'):
        return extract_text_from_docx(file_bytes)
    elif file_name.endswith('.txt'):
        return extract_text_from_txt(file_bytes)
    else:
        raise ValueError(f"Unsupported file format: {file_name}")


# -----------------------------
# YOUTUBE DOWNLOADER
# -----------------------------
def download_audio(url: str, session_dir: Path) -> Tuple[Path, Dict[str, Any]]:
    """
    Download audio from YouTube video.
    
    Args:
        url: YouTube video URL
        session_dir: Directory to save audio file
        
    Returns:
        Tuple of (audio_path, video_info_dict)
        
    Raises:
        FileNotFoundError: If audio file was not created
        Exception: If download fails
    """
    # Use a simple filename without extension - yt-dlp will add .mp3
    output_template = str(session_dir / "audio")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': str(config.audio_quality),
        }],
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # The file will be saved as audio.mp3
    audio_path = session_dir / "audio.mp3"

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file was not created at {audio_path}")

    return audio_path, info


# -----------------------------
# TRANSCRIPTION USING OPENAI
# -----------------------------
def transcribe_audio_with_timestamps(audio_path: Path) -> Any:
    """
    Transcribe audio file using OpenAI Whisper API with retry logic.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Transcription result object with segments and text
        
    Raises:
        ValueError: If client is not initialized
        Exception: If transcription fails after retries
    """
    if client is None:
        raise ValueError("OpenAI client is not initialized. Check OPENAI_API_KEY.")
    
    logger.info(f"Starting transcription for {audio_path.name}, size: {audio_path.stat().st_size / (1024*1024):.2f} MB")
    
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            with open(audio_path, "rb") as audio_file:
                result = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                    timeout=config.api_timeout_seconds
                )
            logger.info("Transcription completed successfully")
            return result
        except Exception as e:
            logger.warning(f"Transcription attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
            else:
                logger.error(f"Transcription failed after {max_retries} attempts")
                raise


# -----------------------------
# SUMMARIZATION & KEY FACTORS
# -----------------------------
def call_openai_with_retry(messages: List[Dict[str, str]], max_tokens: int, max_retries: int = 3) -> str:
    """
    Call OpenAI API with retry logic.
    
    Args:
        messages: List of message dictionaries for chat completion
        max_tokens: Maximum tokens in response
        max_retries: Maximum number of retry attempts
        
    Returns:
        Response content string
        
    Raises:
        ValueError: If client is not initialized
        Exception: If API call fails after retries
    """
    if client is None:
        raise ValueError("OpenAI client is not initialized. Check OPENAI_API_KEY.")
    
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=config.openai_model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=config.api_timeout_seconds
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"OpenAI API call attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
            else:
                logger.error(f"OpenAI API call failed after {max_retries} attempts")
                raise


def validate_and_truncate_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Validate and truncate text to fit within API limits.
    
    Args:
        text: Text to validate
        max_length: Maximum length (default: from config)
        
    Returns:
        Validated and potentially truncated text
    """
    if max_length is None:
        max_length = config.max_text_input_length
    
    if len(text) > max_length:
        logger.warning(f"Text too long ({len(text)} chars), truncating to {max_length}")
        return text[:max_length]
    return text


def summarize_text(text: str) -> str:
    """
    Summarize text using OpenAI GPT with retry logic.
    
    Args:
        text: Text to summarize
        
    Returns:
        Summary text
        
    Raises:
        ValueError: If client is not initialized
        Exception: If summarization fails
    """
    text = validate_and_truncate_text(text)
    prompt = PROMPTS["summarize"].format(text=text)
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant that creates clear, concise summaries."},
        {"role": "user", "content": prompt}
    ]
    
    return call_openai_with_retry(messages, config.summary_max_tokens)


def extract_title_from_transcript(text: str) -> str:
    """
    Generate a descriptive title based on transcript content.
    
    Args:
        text: Transcript text
        
    Returns:
        Generated title string
        
    Raises:
        ValueError: If client is not initialized
        Exception: If title generation fails
    """
    # Limit text to first TITLE_SAMPLE_SIZE characters to save tokens
    sample_text = text[:config.title_sample_size] if len(text) > config.title_sample_size else text
    prompt = PROMPTS["extract_title"].format(text=sample_text)
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant that creates clear, descriptive titles."},
        {"role": "user", "content": prompt}
    ]
    
    result = call_openai_with_retry(messages, config.title_max_tokens)
    return result.strip().strip('"\'')


def extract_key_factors(text: str) -> str:
    """
    Extract key factors from text using OpenAI GPT.
    
    Args:
        text: Text to analyze
        
    Returns:
        Extracted key factors as formatted text
        
    Raises:
        ValueError: If client is not initialized
        Exception: If extraction fails
    """
    text = validate_and_truncate_text(text)
    prompt = PROMPTS["extract_key_factors"].format(text=text)
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant that extracts key information from transcripts."},
        {"role": "user", "content": prompt}
    ]
    
    return call_openai_with_retry(messages, config.key_factors_max_tokens)


# -----------------------------
# BUSINESS LOGIC (No UI Code)
# -----------------------------
def process_youtube_video(
    url: str, 
    session_dir: Path,
    progress_callback: Optional[callable] = None
) -> Dict[str, Any]:
    """
    Process a YouTube video - pure business logic with no UI code.
    Can be tested independently and reused in CLI, API, or other contexts.
    
    Args:
        url: YouTube video URL
        session_dir: Directory to save output files
        progress_callback: Optional callback function(progress: int, message: str) for UI updates
        
    Returns:
        Dictionary with all processing results and metadata:
            - session_dir: Output directory path
            - metadata: Video metadata dict
            - full_text: Transcript text
            - timestamped_lines: List of timestamped transcript lines
            - summary: Generated summary
            - key_factors: Extracted key factors
            - file_size: Audio file size in MB
            
    Raises:
        FileNotFoundError: If audio file is not created
        ValueError: If file size exceeds limit or API client not initialized
        Exception: If processing fails
    """
    def update_progress(pct: int, msg: str):
        """Helper to update progress if callback is provided."""
        if progress_callback:
            progress_callback(pct, msg)
        # Log with emoji fallback for Windows console
        try:
            logger.info(f"Progress: {pct}% - {msg}")
        except UnicodeEncodeError:
            # Strip emojis for Windows console if needed
            msg_no_emoji = msg.encode('ascii', 'ignore').decode('ascii')
            logger.info(f"Progress: {pct}% - {msg_no_emoji}")
    
    try:
        logger.info(f"Processing YouTube video: {url}")
        update_progress(10, "🎬 Starting video processing...")
        
        # Download audio
        update_progress(15, "⬇️ Downloading audio...")
        logger.info("Step 1/6: Downloading audio...")
        audio_path, video_info = download_audio(url, session_dir)
        video_title = video_info.get('title', 'Unknown Video') if video_info else 'Unknown Video'
        logger.info(f"Audio downloaded successfully: {video_title}")
        update_progress(25, f"✅ Audio downloaded: {video_title[:40]}...")
        
        # Verify file exists
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found at {audio_path}")
        
        file_size = audio_path.stat().st_size / (1024 * 1024)  # MB
        logger.info(f"Audio file size: {file_size:.2f} MB")
        
        # Check file size limit for Whisper API
        if file_size > config.max_audio_file_size_mb:
            error_msg = (
                f"Audio file is too large ({file_size:.2f} MB). "
                f"OpenAI Whisper API has a {config.max_audio_file_size_mb}MB limit. "
                f"Please try a shorter video or reduce audio quality in settings."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Transcribe audio
        update_progress(30, "🎤 Transcribing audio with Whisper API...")
        logger.info("Step 2/6: Transcribing audio with Whisper API...")
        result = transcribe_audio_with_timestamps(audio_path)
        segments = result.segments if hasattr(result, 'segments') else []
        full_text = result.text if hasattr(result, 'text') else ""
        logger.info(f"Transcription received: {len(segments)} segments, {len(full_text.split())} words")
        update_progress(50, f"✅ Transcribed: {len(full_text.split())} words")
        
        # Save transcription files
        update_progress(52, "💾 Saving transcription files...")
        logger.info("Step 3/6: Saving transcription files...")
        if not safe_write_text(session_dir / "transcript.txt", full_text):
            raise IOError("Failed to save transcript file")
        
        # Create timestamped transcript
        timestamped_lines = []
        for seg in segments:
            start = format_timestamp(seg.start)
            end = format_timestamp(seg.end)
            timestamped_lines.append(f"[{start} → {end}]\n{seg.text.strip()}\n")
        
        if not safe_write_text(session_dir / "transcript_with_timestamps.txt", "\n".join(timestamped_lines)):
            raise IOError("Failed to save timestamped transcript file")
        
        # Create SRT subtitle file
        srt_segments = [{"start": seg.start, "end": seg.end, "text": seg.text} for seg in segments]
        srt_output = to_srt(srt_segments)
        if not safe_write_text(session_dir / "transcript.srt", srt_output):
            raise IOError("Failed to save SRT file")
        
        logger.info("Transcription files saved successfully")
        update_progress(60, "✅ Transcription files saved")
        
        # Generate summary
        update_progress(65, "📝 Generating summary with GPT...")
        logger.info("Step 4/6: Generating summary with GPT...")
        summary = summarize_text(full_text)
        if not safe_write_text(session_dir / "summary.txt", summary):
            raise IOError("Failed to save summary file")
        logger.info("Summary generated successfully")
        update_progress(75, "✅ Summary generated")
        
        # Extract key factors
        update_progress(80, "🎯 Extracting key factors with GPT...")
        logger.info("Step 5/6: Extracting key factors with GPT...")
        key_factors = extract_key_factors(full_text)
        if not safe_write_text(session_dir / "key_factors.txt", key_factors):
            raise IOError("Failed to save key factors file")
        logger.info("Key factors extracted successfully")
        update_progress(90, "✅ Key factors extracted")
        
        # Generate content-based title
        update_progress(95, "📋 Generating content-based title...")
        logger.info("Step 6/6: Generating content-based title...")
        transcript_title = extract_title_from_transcript(full_text)
        logger.info(f"Content title generated: {transcript_title}")
        
        # Create metadata
        metadata = {
            "url": url,
            "title": video_title,
            "transcript_title": transcript_title,
            "timestamp": datetime.now().isoformat(),
            "video_id": session_dir.name,
            "word_count": len(full_text.split()),
            "segment_count": len(segments),
        }
        
        if not safe_write_text(session_dir / "metadata.json", json.dumps(metadata, indent=4)):
            raise IOError("Failed to save metadata file")
        
        update_progress(100, "✅ Processing complete!")
        logger.info(f"✅ Processing completed successfully for: {video_title}")
        
        # Return all results for display
        return {
            "session_dir": session_dir,
            "metadata": metadata,
            "full_text": full_text,
            "timestamped_lines": timestamped_lines,
            "summary": summary,
            "key_factors": key_factors,
            "file_size": file_size,
        }
    
    except Exception as e:
        logger.error(f"Processing failed for {url}: {e}")
        # Cleanup partial files on failure
        if session_dir.exists():
            try:
                shutil.rmtree(session_dir)
                logger.info(f"Cleaned up failed processing directory: {session_dir}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup directory {session_dir}: {cleanup_error}")
        raise


def process_document(
    uploaded_file: Any, 
    session_dir: Path,
    progress_callback: Optional[callable] = None
) -> Dict[str, Any]:
    """
    Process a document - pure business logic with no UI code.
    Can be tested independently and reused in CLI, API, or other contexts.
    
    Args:
        uploaded_file: Uploaded file object (or file-like object for testing)
        session_dir: Directory to save output files
        progress_callback: Optional callback function(progress: int, message: str) for UI updates
        
    Returns:
        Dictionary with all processing results and metadata:
            - session_dir: Output directory path
            - metadata: Document metadata dict
            - full_text: Extracted text
            - summary: Generated summary
            - key_factors: Extracted key factors
            
    Raises:
        ValueError: No text could be extracted or API client not initialized
        IOError: If file writes fail
        Exception: If processing fails
    """
    def update_progress(pct: int, msg: str):
        """Helper to update progress if callback is provided."""
        if progress_callback:
            progress_callback(pct, msg)
        # Log with emoji fallback for Windows console
        try:
            logger.info(f"Progress: {pct}% - {msg}")
        except UnicodeEncodeError:
            # Strip emojis for Windows console if needed
            msg_no_emoji = msg.encode('ascii', 'ignore').decode('ascii')
            logger.info(f"Progress: {pct}% - {msg_no_emoji}")

    try:
        logger.info(f"Processing document: {uploaded_file.name}")
        update_progress(10, f"📄 Starting document processing...")
        
        # Extract text from document
        update_progress(20, "📖 Extracting text from document...")
        logger.info("Step 1/4: Extracting text from document...")
        full_text = extract_text_from_document(uploaded_file)
        
        if not full_text.strip():
            raise ValueError("No text could be extracted from the document.")
        
        logger.info(f"Text extracted: {len(full_text.split())} words, {len(full_text)} characters")
        update_progress(40, f"✅ Extracted: {len(full_text.split())} words")
        
        # Save original text
        if not safe_write_text(session_dir / "extracted_text.txt", full_text):
            raise IOError("Failed to save extracted text file")
        
        # Generate summary
        update_progress(50, "📝 Generating summary with GPT...")
        logger.info("Step 2/4: Generating summary with GPT...")
        summary = summarize_text(full_text)
        if not safe_write_text(session_dir / "summary.txt", summary):
            raise IOError("Failed to save summary file")
        logger.info("Summary generated successfully")
        update_progress(70, "✅ Summary generated")
        
        # Extract key factors
        update_progress(75, "🎯 Extracting key factors with GPT...")
        logger.info("Step 3/4: Extracting key factors with GPT...")
        key_factors = extract_key_factors(full_text)
        if not safe_write_text(session_dir / "key_factors.txt", key_factors):
            raise IOError("Failed to save key factors file")
        logger.info("Key factors extracted successfully")
        update_progress(90, "✅ Key factors extracted")
        
        # Generate content-based title
        update_progress(95, "📋 Generating content-based title...")
        logger.info("Step 4/4: Generating content-based title...")
        content_title = extract_title_from_transcript(full_text)
        logger.info(f"Content title generated: {content_title}")
        
        # Create metadata
        metadata = {
            "filename": uploaded_file.name,
            "content_title": content_title,
            "timestamp": datetime.now().isoformat(),
            "doc_id": session_dir.name,
            "word_count": len(full_text.split()),
            "character_count": len(full_text),
        }
        
        if not safe_write_text(session_dir / "metadata.json", json.dumps(metadata, indent=4)):
            raise IOError("Failed to save metadata file")
        
        update_progress(100, "✅ Processing complete!")
        logger.info(f"✅ Processing completed successfully for: {uploaded_file.name}")
        
        # Return all results for display
        return {
            "session_dir": session_dir,
            "metadata": metadata,
            "full_text": full_text,
            "summary": summary,
            "key_factors": key_factors,
        }
    
    except Exception as e:
        logger.error(f"Processing failed for {uploaded_file.name}: {e}")
        # Cleanup partial files on failure
        if session_dir.exists():
            try:
                shutil.rmtree(session_dir)
                logger.info(f"Cleaned up failed processing directory: {session_dir}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup directory {session_dir}: {cleanup_error}")
        raise


# -----------------------------
# UI RENDERING (Streamlit-specific)
# -----------------------------
def render_youtube_results(results: Dict[str, Any]) -> None:
    """
    Render YouTube processing results in Streamlit UI.
    
    Args:
        results: Processing results dictionary from process_youtube_video
    """
    session_dir = results["session_dir"]
    
    st.subheader("📄 Transcript")
    with st.expander("View Full Transcript"):
        st.text(results["full_text"])

    st.subheader("⏱️ Timestamped Transcript")
    with st.expander("View Timestamped Transcript"):
        st.text("\n".join(results["timestamped_lines"]))

    st.subheader("📝 Summary")
    with st.expander("View Summary"):
        st.markdown(results["summary"])

    st.subheader("🎯 Key Factors")
    with st.expander("View Key Factors"):
        st.markdown(results["key_factors"])

    st.subheader("⬇️ Download Files")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button("📄 Transcript (TXT)", read_file_bytes(session_dir / "transcript.txt"),
                          file_name="transcript.txt")
        st.download_button("⏱️ Timestamped (TXT)", read_file_bytes(session_dir / "transcript_with_timestamps.txt"),
                          file_name="transcript_with_timestamps.txt")

    with col2:
        st.download_button("🎬 Subtitles (SRT)", read_file_bytes(session_dir / "transcript.srt"),
                          file_name="transcript.srt")
        st.download_button("📝 Summary (TXT)", read_file_bytes(session_dir / "summary.txt"),
                          file_name="summary.txt")

    with col3:
        st.download_button("🎯 Key Factors (TXT)", read_file_bytes(session_dir / "key_factors.txt"),
                          file_name="key_factors.txt")
        st.download_button("📊 Metadata (JSON)", read_file_bytes(session_dir / "metadata.json"),
                          file_name="metadata.json")


def render_document_results(results: Dict[str, Any]) -> None:
    """
    Render document processing results in Streamlit UI.
    
    Args:
        results: Processing results dictionary from process_document
    """
    session_dir = results["session_dir"]
    
    st.subheader("📄 Extracted Text")
    with st.expander("View Full Text"):
        st.text(results["full_text"])
    
    st.subheader("📝 Summary")
    with st.expander("View Summary"):
        st.markdown(results["summary"])
    
    st.subheader("🎯 Key Factors")
    with st.expander("View Key Factors"):
        st.markdown(results["key_factors"])
    
    st.subheader("⬇️ Download Files")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.download_button("📄 Extracted Text (TXT)", 
                         read_file_bytes(session_dir / "extracted_text.txt"),
                         file_name="extracted_text.txt")
    
    with col2:
        st.download_button("📝 Summary (TXT)", 
                         read_file_bytes(session_dir / "summary.txt"),
                         file_name="summary.txt")
    
    with col3:
        st.download_button("🎯 Key Factors (TXT)", 
                         read_file_bytes(session_dir / "key_factors.txt"),
                         file_name="key_factors.txt")
        st.download_button("📊 Metadata (JSON)", 
                         read_file_bytes(session_dir / "metadata.json"),
                         file_name="metadata.json")


# -----------------------------
# PROJECT MANAGEMENT
# -----------------------------
@st.cache_data(ttl=60)  # Cache for 60 seconds
def list_projects() -> List[Dict[str, Any]]:
    """
    List all project directories with their metadata.
    
    Returns:
        List of project metadata dictionaries, sorted by timestamp (newest first)
    """
    projects = []
    for project_dir in config.output_dir.iterdir():
        if project_dir.is_dir():
            metadata_file = project_dir / "metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                        metadata['project_dir'] = project_dir.name
                        projects.append(metadata)
                except (json.JSONDecodeError, IOError) as e:
                    # Skip projects with corrupted metadata
                    logger.warning(f"Failed to load metadata from {project_dir.name}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error loading metadata from {project_dir.name}: {e}")
                    continue
    # Sort by timestamp, newest first
    projects.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return projects


def delete_project(project_dir_name: str) -> bool:
    """
    Delete a project directory and all its contents.
    
    Args:
        project_dir_name: Name of project directory to delete
        
    Returns:
        True if deletion succeeded, False otherwise
    """
    # Validate directory name doesn't contain path traversal attempts
    if '/' in project_dir_name or '\\' in project_dir_name or '..' in project_dir_name:
        logger.warning(f"Invalid project directory name: {project_dir_name}")
        return False
    
    project_path = config.output_dir / project_dir_name
    if project_path.exists() and project_path.parent == config.output_dir:
        try:
            shutil.rmtree(project_path)
            logger.info(f"Deleted project: {project_dir_name}")
            return True
        except (PermissionError, OSError) as e:
            logger.error(f"Failed to delete project {project_dir_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting project {project_dir_name}: {e}")
            return False
    return False


def update_project_metadata_with_title(project_dir_name: str) -> bool:
    """
    Update project metadata to include titles if missing.
    
    Args:
        project_dir_name: Name of project directory to update
        
    Returns:
        True if update succeeded, False otherwise
    """
    project_path = config.output_dir / project_dir_name
    metadata_file = project_path / "metadata.json"
    
    if not metadata_file.exists():
        return False
    
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        updated = False
        
        # For YouTube videos: fetch video title if missing
        if 'url' in metadata and 'title' not in metadata:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(metadata['url'], download=False)
                    video_title = info.get('title', 'Unknown Video')
                    metadata['title'] = video_title
                    updated = True
                    logger.info(f"Updated YouTube title for {project_dir_name}: {video_title}")
            except Exception as e:
                logger.warning(f"Failed to fetch YouTube title for {project_dir_name}: {e}")
        
        # For both videos and documents: generate transcript/content title if missing
        if 'transcript_title' not in metadata and 'content_title' not in metadata:
            # Try to find transcript or extracted text file
            transcript_file = project_path / "transcript.txt"
            extracted_text_file = project_path / "extracted_text.txt"
            
            text_content = None
            title_key = None
            
            # Only read the first TITLE_SAMPLE_SIZE characters to save memory
            if transcript_file.exists():
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    text_content = f.read(config.title_sample_size)
                title_key = 'transcript_title'
            elif extracted_text_file.exists():
                with open(extracted_text_file, 'r', encoding='utf-8') as f:
                    text_content = f.read(config.title_sample_size)
                title_key = 'content_title'
            
            if text_content and text_content.strip() and title_key:
                try:
                    generated_title = extract_title_from_transcript(text_content)
                    metadata[title_key] = generated_title
                    updated = True
                    logger.info(f"Generated content title for {project_dir_name}: {generated_title}")
                except Exception as e:
                    logger.warning(f"Failed to generate content title for {project_dir_name}: {e}")
        
        if updated:
            # Save updated metadata
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=4)
            return True
        
        return False
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to update metadata for {project_dir_name}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error updating metadata for {project_dir_name}: {e}")
        return False


# -----------------------------
# STREAMLIT UI
# -----------------------------
st.set_page_config(page_title="Content Analyzer", layout="wide")

st.title("📊 Content Analyzer")
st.write("Analyze YouTube videos or documents - transcribe, summarize, and extract insights.")

# -----------------------------
# SIDEBAR: PROJECT HISTORY
# -----------------------------
with st.sidebar:
    st.header("📁 Project History")
    
    projects = list_projects()
    
    if projects:
        st.write(f"**Total projects:** {len(projects)}")
        
        # Add a button to update old projects with titles
        needs_update = any(
            ('url' in p and 'title' not in p) or 
            ('transcript_title' not in p and 'content_title' not in p)
            for p in projects
        )
        if needs_update:
            if st.button("🔄 Update Old Projects", help="Generate titles from content for old projects", use_container_width=True):
                with st.spinner("Updating project titles..."):
                    updated_count = 0
                    for proj in projects:
                        if update_project_metadata_with_title(proj['project_dir']):
                            updated_count += 1
                    if updated_count > 0:
                        st.success(f"✅ Updated {updated_count} project(s)!")
                        st.rerun()
                    else:
                        st.info("No projects needed updating.")
        
        st.markdown("---")
        
        for idx, proj in enumerate(projects):
            # Create a meaningful title for the project
            if 'url' in proj:
                # For YouTube videos, prioritize transcript_title, then title
                project_icon = "🎥"
                
                # Use transcript-based title if available, otherwise YouTube title
                if 'transcript_title' in proj and proj['transcript_title']:
                    title = proj['transcript_title']
                elif 'title' in proj and proj['title']:
                    title = proj['title']
                else:
                    title = None
                
                if title:
                    # Truncate if too long
                    project_name = truncate_title(title)
                else:
                    # Fallback to video ID extraction
                    vid_id = extract_video_id(proj['url'])
                    if vid_id:
                        # Determine if it's a short or regular video
                        if '/shorts/' in proj['url']:
                            project_name = f"Short {vid_id[:11]}"
                        else:
                            project_name = f"Video {vid_id[:11]}"
                    else:
                        project_name = f"Video {idx + 1}"
            elif 'filename' in proj:
                # For documents, use content_title if available, otherwise filename
                project_icon = "📄"
                
                if 'content_title' in proj and proj['content_title']:
                    project_name = truncate_title(proj['content_title'])
                else:
                    project_name = truncate_title(proj['filename'])
            else:
                project_icon = "📄"
                project_name = f"Project {idx + 1}"
            
            with st.expander(f"{project_icon} {project_name}", expanded=False):
                # Display project info
                if 'url' in proj:
                    st.write("**Type:** YouTube Video")
                    if 'transcript_title' in proj and proj['transcript_title']:
                        st.write(f"**Content Title:** {proj['transcript_title']}")
                    if 'title' in proj and proj['title']:
                        st.write(f"**Video Title:** {proj['title']}")
                    st.write(f"**URL:** {format_url_for_display(proj['url'])}")
                elif 'filename' in proj:
                    st.write("**Type:** Document")
                    if 'content_title' in proj and proj['content_title']:
                        st.write(f"**Content Title:** {proj['content_title']}")
                    st.write(f"**File:** {proj['filename']}")
                
                # Format timestamp nicely
                try:
                    dt = datetime.fromisoformat(proj['timestamp'])
                    formatted_date = dt.strftime("%b %d, %Y %I:%M %p")
                    st.write(f"**Date:** {formatted_date}")
                except (ValueError, KeyError) as e:
                    logger.warning(f"Failed to format timestamp for project {proj.get('project_dir', 'unknown')}: {e}")
                    st.write(f"**Date:** {proj.get('timestamp', 'Unknown')[:19]}")
                
                st.write(f"**Words:** {proj.get('word_count', 'N/A'):,}")
                
                # Delete button with confirmation
                col1, col2 = st.columns([1, 1])
                with col1:
                    delete_key = f"del_{proj['project_dir']}"
                    if delete_key not in st.session_state:
                        st.session_state[delete_key] = False
                    
                    if not st.session_state[delete_key]:
                        if st.button("🗑️ Delete", key=f"btn_{delete_key}", use_container_width=True):
                            st.session_state[delete_key] = True
                            st.rerun()
                    else:
                        if st.button("✅ Confirm", key=f"conf_{delete_key}", type="primary", use_container_width=True):
                            if delete_project(proj['project_dir']):
                                st.success("Deleted!")
                                st.session_state[delete_key] = False
                                st.rerun()
                            else:
                                st.error("Failed to delete")
                                st.session_state[delete_key] = False
                
                with col2:
                    if st.session_state.get(delete_key, False):
                        if st.button("❌ Cancel", key=f"canc_{delete_key}", use_container_width=True):
                            st.session_state[delete_key] = False
                            st.rerun()
        
        # Bulk delete option
        st.markdown("---")
        if st.button("🗑️ Delete All Projects", type="secondary", use_container_width=True):
            confirm_all_key = "confirm_delete_all"
            if confirm_all_key not in st.session_state:
                st.session_state[confirm_all_key] = True
                st.warning("⚠️ Click again to confirm deletion of ALL projects!")
                st.rerun()
            else:
                deleted_count = 0
                for proj in projects:
                    if delete_project(proj['project_dir']):
                        deleted_count += 1
                st.success(f"Deleted {deleted_count} project(s)!")
                st.session_state[confirm_all_key] = False
                st.rerun()
    else:
        st.info("No projects yet.\n\nProcess a video or document to get started!")

# Mode selector
mode = st.radio("Select input type:", ["YouTube Video", "Document File"], horizontal=True)

st.markdown("---")

if mode == "YouTube Video":
    st.subheader("🎧 YouTube Video Analysis")
    url = st.text_input("Enter a YouTube URL:", "")
    process_button = st.button("Process Video")
    
    if process_button:
        if not url.strip():
            st.error("Please enter a valid YouTube URL.")
            st.stop()
        
        # Validate YouTube URL
        if not validate_youtube_url(url):
            st.error("❌ Invalid YouTube URL. Please enter a valid YouTube, YouTube Shorts, or youtu.be link.")
            logger.warning(f"Invalid YouTube URL attempted: {url}")
            st.stop()
        
        # Rate limiting
        if 'last_process_time' not in st.session_state:
            st.session_state.last_process_time = 0
        
        current_time = time.time()
        time_since_last = current_time - st.session_state.last_process_time
        if time_since_last < config.rate_limit_seconds:
            wait_time = config.rate_limit_seconds - time_since_last
            st.warning(f"⏳ Please wait {wait_time:.1f} more seconds before processing another request.")
            st.stop()
        
        st.session_state.last_process_time = current_time

        try:
            # Create session directory
            video_id = safe_filename(str(uuid.uuid4()))
            session_dir = config.output_dir / video_id
            session_dir.mkdir(exist_ok=True)
            
            # Create progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Callback function to update UI
            def update_ui(progress: int, message: str):
                """Update progress bar and status text from processing function."""
                progress_bar.progress(progress)
                status_text.text(message)
            
            # Call business logic function with progress callback
            results = process_youtube_video(url, session_dir, progress_callback=update_ui)
            
            # Brief pause to show completion
            time.sleep(0.5)
            progress_bar.empty()
            status_text.empty()
            
            st.success("✅ Processing complete!")
            
            # Render results using UI function
            render_youtube_results(results)

        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            st.exception(e)

else:  # Document File mode
    st.subheader("📄 Document Analysis")
    uploaded_file = st.file_uploader(
        "Upload a document (PDF, DOCX, or TXT):",
        type=['pdf', 'docx', 'txt']
    )
    
    process_doc_button = st.button("Process Document")
    
    if process_doc_button:
        if uploaded_file is None:
            st.error("Please upload a document file.")
            st.stop()
        
        # Rate limiting (shared with video processing)
        if 'last_process_time' not in st.session_state:
            st.session_state.last_process_time = 0
        
        current_time = time.time()
        time_since_last = current_time - st.session_state.last_process_time
        if time_since_last < config.rate_limit_seconds:
            wait_time = config.rate_limit_seconds - time_since_last
            st.warning(f"⏳ Please wait {wait_time:.1f} more seconds before processing another request.")
            st.stop()
        
        st.session_state.last_process_time = current_time
        
        try:
            # Create session directory
            doc_id = safe_filename(str(uuid.uuid4()))
            session_dir = config.output_dir / doc_id
            session_dir.mkdir(exist_ok=True)
            
            # Create progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Callback function to update UI
            def update_ui(progress: int, message: str):
                """Update progress bar and status text from processing function."""
                progress_bar.progress(progress)
                status_text.text(message)
            
            # Call business logic function with progress callback
            results = process_document(uploaded_file, session_dir, progress_callback=update_ui)
            
            # Brief pause to show completion
            time.sleep(0.5)
            progress_bar.empty()
            status_text.empty()
            
            st.success("✅ Processing complete!")
            
            # Render results using UI function
            render_document_results(results)
        
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            st.exception(e)

st.markdown("---")
st.caption("Built with ❤️ using Python, Streamlit, yt-dlp, and OpenAI Whisper + GPT-4o-mini")