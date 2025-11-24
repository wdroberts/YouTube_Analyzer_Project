"""
YouTube Analyzer - Main Application
Transcribe and analyze YouTube videos and documents using OpenAI's Whisper and GPT.
"""
# Standard library imports
import io
import json
import logging
import os
import re
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs

# Third-party imports
import chardet
import docx
import PyPDF2
import streamlit as st
import yt_dlp
from dotenv import load_dotenv
from openai import OpenAI
from pydub import AudioSegment
from faster_whisper import WhisperModel

# Load environment variables from .env file
load_dotenv()

# -----------------------------
# CONSTANTS
# -----------------------------
VALID_YOUTUBE_DOMAINS = frozenset([
    'www.youtube.com',
    'youtube.com',
    'youtu.be',
    'm.youtube.com'
])

# -----------------------------
# CUSTOM EXCEPTIONS
# -----------------------------
class YouTubeAnalyzerError(Exception):
    """Base exception for YouTube Analyzer application."""
    pass


class AudioDownloadError(YouTubeAnalyzerError):
    """Error downloading audio from video source."""
    pass


class TranscriptionError(YouTubeAnalyzerError):
    """Error during audio transcription with Whisper API."""
    pass


class APIQuotaError(YouTubeAnalyzerError):
    """OpenAI API quota or rate limit exceeded."""
    pass


class FileSizeError(YouTubeAnalyzerError):
    """File size exceeds API limits."""
    pass


class DocumentProcessingError(YouTubeAnalyzerError):
    """Error processing document file."""
    pass


class APIConnectionError(YouTubeAnalyzerError):
    """Error connecting to external APIs."""
    pass


# -----------------------------
# LOGGING CONFIGURATION
# -----------------------------

# Configure logging with rotation to prevent log files from growing too large
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            'app.log',
            maxBytes=10*1024*1024,  # 10MB max file size
            backupCount=3,  # Keep 3 backup files
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Fix Windows console encoding for emoji support
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
    audio_chunk_size_mb: int = 20  # Target size for audio chunks when splitting
    audio_chunk_overlap_ms: int = 500  # Overlap between chunks to prevent word cuts
    max_document_upload_mb: int = 50  # Maximum document upload size
    max_pdf_pages: int = 1000  # Maximum PDF pages to process
    max_pdf_page_chars: int = 200000  # Maximum characters per PDF page
    # Data storage paths
    data_root: Path = Path(os.getenv("DATA_ROOT", r"D:\Documents\Software_Projects\YouTube_Analyzer_Project\Data"))
    output_dir: Path = None  # Will be set in __post_init__
    database_path: Path = None  # Will be set in __post_init__
    max_text_input_length: int = 100000  # Max characters for API calls
    api_timeout_seconds: int = 300  # 5 minutes
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.audio_quality < 32 or self.audio_quality > 320:
            raise ValueError(f"Invalid audio quality: {self.audio_quality}. Must be between 32-320 kbps")
        if self.max_audio_file_size_mb > 25:
            raise ValueError(f"Max file size cannot exceed 25MB (Whisper API limit)")
        
        # Set up paths based on data_root
        if self.output_dir is None:
            self.output_dir = self.data_root / "outputs"
        if self.database_path is None:
            self.database_path = self.data_root / "youtube_analyzer.db"
        
        # Create directories
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info(f"Configuration initialized: audio_quality={self.audio_quality}, model={self.openai_model}")
        logger.info(f"Data root: {self.data_root}")
        logger.info(f"Database: {self.database_path}")

# Initialize configuration
config = Config()

# Initialize database
from database import DatabaseManager
db_manager = DatabaseManager(config.database_path)

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
def sanitize_url_for_log(url: str, max_length: int = 50) -> str:
    """
    Sanitize URL for logging to prevent exposing sensitive information.
    
    Args:
        url: URL to sanitize
        max_length: Maximum length of sanitized URL
        
    Returns:
        Sanitized URL safe for logging
    """
    try:
        # Truncate long URLs to prevent log pollution
        if len(url) > max_length:
            return url[:max_length] + "..."
        return url
    except:
        return "[invalid URL]"


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
        return parsed.netloc in VALID_YOUTUBE_DOMAINS
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse URL: {sanitize_url_for_log(url)}, error: {e}")
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
        logger.warning(f"Failed to extract video ID from {sanitize_url_for_log(url)}: {e}")
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
    if not url:
        return ""
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
    Extract text from a PDF file with security limits.
    
    Args:
        file_bytes: PDF file as bytes
        
    Returns:
        Extracted text content
        
    Raises:
        DocumentProcessingError: If PDF exceeds limits or cannot be parsed
    """
    try:
        pdf_file = io.BytesIO(file_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        # Security: Limit number of pages to prevent DoS
        num_pages = len(pdf_reader.pages)
        if num_pages > config.max_pdf_pages:
            raise DocumentProcessingError(
                f"PDF too large: {num_pages} pages (maximum: {config.max_pdf_pages} pages). "
                f"Please split the document or process fewer pages."
            )
        
        logger.info(f"Processing PDF with {num_pages} pages")
        
        text = []
        for i, page in enumerate(pdf_reader.pages):
            try:
                page_text = page.extract_text()
                
                # Security: Limit text per page to prevent memory exhaustion
                if page_text and len(page_text) > config.max_pdf_page_chars:
                    logger.warning(f"Page {i+1} text truncated (too large)")
                    page_text = page_text[:config.max_pdf_page_chars]
                
                if page_text:
                    text.append(page_text)
            except Exception as e:
                logger.warning(f"Failed to extract text from page {i+1}: {e}")
                continue
        
        if not text:
            raise DocumentProcessingError("No text could be extracted from PDF")
        
        return "\n\n".join(text)
        
    except DocumentProcessingError:
        raise
    except Exception as e:
        raise DocumentProcessingError(f"Failed to parse PDF: {str(e)}") from e


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
    Extract text from a TXT file with automatic encoding detection.
    
    Args:
        file_bytes: TXT file as bytes
        
    Returns:
        Decoded text content
        
    Raises:
        UnicodeDecodeError: If file cannot be decoded
    """
    
    # Detect encoding for better compatibility
    detected = chardet.detect(file_bytes)
    encoding = detected.get('encoding', 'utf-8')
    confidence = detected.get('confidence', 0)
    
    logger.info(f"Detected text encoding: {encoding} (confidence: {confidence:.2%})")
    
    try:
        # Try detected encoding first
        if encoding and confidence > 0.7:
            return file_bytes.decode(encoding)
        else:
            # Fallback to UTF-8
            return file_bytes.decode('utf-8')
    except (UnicodeDecodeError, LookupError):
        # Last resort: UTF-8 with error replacement
        logger.warning(f"Encoding detection failed, using UTF-8 with error replacement")
        return file_bytes.decode('utf-8', errors='replace')


def extract_text_from_document(uploaded_file: Any) -> str:
    """
    Extract text from various document formats.
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Returns:
        Extracted text content
        
    Raises:
        DocumentProcessingError: If file format is not supported or extraction fails
    """
    try:
        file_bytes = uploaded_file.read()
        file_name = uploaded_file.name.lower()
        
        if file_name.endswith('.pdf'):
            text = extract_text_from_pdf(file_bytes)
        elif file_name.endswith('.docx'):
            text = extract_text_from_docx(file_bytes)
        elif file_name.endswith('.txt'):
            text = extract_text_from_txt(file_bytes)
        else:
            raise DocumentProcessingError(
                f"Unsupported file format: {file_name}. "
                f"Please use PDF, DOCX, or TXT files."
            )
        
        if not text or not text.strip():
            raise DocumentProcessingError(
                "Could not extract any text from the document. "
                "The file may be empty, corrupted, or contain only images."
            )
        
        return text
        
    except DocumentProcessingError:
        # Re-raise our custom errors
        raise
    except Exception as e:
        raise DocumentProcessingError(
            f"Failed to extract text from document: {str(e)}"
        ) from e


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
        AudioDownloadError: If download fails for any reason
        FileNotFoundError: If audio file was not created
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

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:
        error_msg = str(e).lower()
        if 'private' in error_msg or 'unavailable' in error_msg:
            raise AudioDownloadError(
                "Video is private, deleted, or unavailable in your region."
            ) from e
        elif 'age' in error_msg or 'sign in' in error_msg:
            raise AudioDownloadError(
                "Video is age-restricted or requires authentication."
            ) from e
        elif 'copyright' in error_msg or 'blocked' in error_msg:
            raise AudioDownloadError(
                "Video is blocked due to copyright or regional restrictions."
            ) from e
        else:
            raise AudioDownloadError(
                f"Could not download video: {str(e)}"
            ) from e

    # The file will be saved as audio.mp3
    audio_path = session_dir / "audio.mp3"

    if not audio_path.exists():
        raise AudioDownloadError(
            f"Audio file was not created. Check FFmpeg installation."
        )

    return audio_path, info


# -----------------------------
# AUDIO CHUNKING FOR LARGE FILES
# -----------------------------
def split_audio_file(audio_path: Path) -> List[Path]:
    """
    Split audio file into smaller chunks if it exceeds size limit.
    
    Uses pydub to intelligently split large audio files into chunks that meet
    Whisper API's size requirements, with overlap to prevent mid-word cuts.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        List of paths to audio chunks (single item if no split needed)
        
    Raises:
        AudioDownloadError: If audio splitting fails
    """
    file_size_mb = audio_path.stat().st_size / (1024 * 1024)
    
    # If file is small enough, return as-is
    if file_size_mb <= config.max_audio_file_size_mb:
        logger.info(f"Audio file size ({file_size_mb:.2f}MB) is within limit - no splitting needed")
        return [audio_path]
    
    logger.info(f"Audio file ({file_size_mb:.2f}MB) exceeds limit ({config.max_audio_file_size_mb}MB). Splitting into chunks...")
    
    try:
        # Load audio file
        audio = AudioSegment.from_mp3(audio_path)
        total_duration_ms = len(audio)
        logger.info(f"Audio duration: {total_duration_ms / 1000:.2f} seconds")
        
        # Calculate chunk duration based on target size
        # Formula: (target_size_MB * 1024 * 1024 * 8) / bitrate_bps * 1000 = duration_ms
        file_bitrate_bps = (audio_path.stat().st_size * 8) / (total_duration_ms / 1000)
        chunk_duration_ms = int((config.audio_chunk_size_mb * 1024 * 1024 * 8) / file_bitrate_bps * 1000)
        
        # Safety check: ensure chunk duration is reasonable (at least 5 minutes)
        min_chunk_duration_ms = 300000  # 5 minutes
        if chunk_duration_ms < min_chunk_duration_ms:
            logger.warning(f"Calculated chunk duration ({chunk_duration_ms/1000:.1f}s) too small, using minimum ({min_chunk_duration_ms/1000:.1f}s)")
            chunk_duration_ms = min_chunk_duration_ms
        
        # Ensure chunk duration + overlap makes progress
        if chunk_duration_ms <= config.audio_chunk_overlap_ms:
            chunk_duration_ms = config.audio_chunk_overlap_ms * 2
            logger.warning(f"Adjusted chunk duration to {chunk_duration_ms/1000:.1f}s to ensure progress")
        
        logger.info(f"Estimated bitrate: {file_bitrate_bps / 1000:.1f} kbps, chunk duration: {chunk_duration_ms / 1000:.1f}s")
        
        chunks = []
        chunk_dir = audio_path.parent / "chunks"
        chunk_dir.mkdir(exist_ok=True)
        
        # Split audio into chunks with overlap
        start = 0
        chunk_num = 0
        max_chunks = 100  # Safety limit to prevent infinite loops
        
        while start < total_duration_ms and chunk_num < max_chunks:
            end = min(start + chunk_duration_ms, total_duration_ms)
            
            # Safety check: ensure we're making progress
            if end <= start:
                logger.error(f"Invalid chunk boundaries: start={start}, end={end}")
                break
            
            # Extract chunk
            chunk = audio[start:end]
            chunk_path = chunk_dir / f"chunk_{chunk_num:03d}.mp3"
            
            # Export chunk with same quality settings
            chunk.export(
                chunk_path,
                format="mp3",
                bitrate=f"{config.audio_quality}k"
            )
            
            chunk_size_mb = chunk_path.stat().st_size / (1024 * 1024)
            chunks.append(chunk_path)
            
            logger.info(f"Created chunk {chunk_num + 1}: {chunk_path.name} "
                       f"({chunk_size_mb:.2f}MB, {(end-start)/1000:.1f}s)")
            
            # Move to next chunk with overlap (prevents cutting mid-word)
            # Ensure overlap doesn't cause us to go backwards
            new_start = end - config.audio_chunk_overlap_ms
            if new_start <= start:
                # If overlap would cause us to go backwards, just move forward slightly
                new_start = start + (chunk_duration_ms // 2)
            start = new_start
            chunk_num += 1
        
        if chunk_num >= max_chunks:
            logger.error(f"Hit safety limit of {max_chunks} chunks - stopping")
            raise AudioDownloadError(f"Audio file too complex to split (would need >{max_chunks} chunks)")
        
        logger.info(f"Successfully split audio into {len(chunks)} chunks")
        return chunks
        
    except Exception as e:
        logger.error(f"Failed to split audio file: {e}")
        raise AudioDownloadError(f"Failed to split audio file: {e}") from e


# -----------------------------
# TRANSCRIPTION USING OPENAI
# -----------------------------
def _transcribe_single_file(audio_path: Path) -> Any:
    """
    Helper function to transcribe a single audio file using OpenAI Whisper API.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Transcription result object with segments and text
        
    Raises:
        ValueError: If client is not initialized
        TranscriptionError: If transcription fails
        FileSizeError: If file is too large
        APIQuotaError: If API quota exceeded
        APIConnectionError: If connection to API fails
    """
    if client is None:
        raise ValueError("OpenAI client is not initialized. Check OPENAI_API_KEY.")
    
    logger.info(f"Transcribing {audio_path.name}, size: {audio_path.stat().st_size / (1024*1024):.2f} MB")
    
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
            logger.info(f"Transcription completed: {audio_path.name}")
            return result
        except Exception as e:
            error_str = str(e).lower()
            
            # Check for specific error types
            if '413' in str(e) or 'payload too large' in error_str or 'file size' in error_str:
                raise FileSizeError(
                    f"Audio file too large for Whisper API (limit: {config.max_audio_file_size_mb}MB). "
                    f"Try a shorter video or reduce audio quality."
                ) from e
            
            if 'rate_limit' in error_str or 'quota' in error_str or '429' in str(e):
                raise APIQuotaError(
                    "OpenAI API rate limit or quota exceeded. "
                    "Check your usage at https://platform.openai.com/usage"
                ) from e
            
            if 'connection' in error_str or 'timeout' in error_str or 'network' in error_str:
                if attempt < max_retries - 1:
                    logger.warning(f"Connection error, retrying... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    raise APIConnectionError(
                        "Could not connect to OpenAI API. Check your internet connection."
                    ) from e
            
            # Generic retry for other errors
            logger.warning(f"Transcription attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
            else:
                logger.error(f"Transcription failed after {max_retries} attempts")
                raise TranscriptionError(
                    f"Transcription failed after {max_retries} attempts: {str(e)}"
                ) from e


def transcribe_audio_with_timestamps(audio_path: Path, progress_callback: Optional[callable] = None) -> Any:
    """
    Transcribe audio file, automatically splitting if too large for Whisper API.
    
    For large audio files, this function splits them into chunks, transcribes each
    chunk separately, and merges the results with corrected timestamps.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Transcription result object with segments and text
        
    Raises:
        ValueError: If client is not initialized
        TranscriptionError: If transcription fails
        FileSizeError: If file is too large
        APIQuotaError: If API quota exceeded
        APIConnectionError: If connection to API fails
        AudioDownloadError: If audio splitting fails
    """
    if client is None:
        raise ValueError("OpenAI client is not initialized. Check OPENAI_API_KEY.")
    
    # Split audio if needed
    audio_chunks = split_audio_file(audio_path)
    
    if len(audio_chunks) == 1:
        # Single file - transcribe normally
        logger.info("Transcribing audio file (no splitting needed)")
        return _transcribe_single_file(audio_chunks[0])
    else:
        # Multiple chunks - transcribe and merge
        logger.info(f"Transcribing {len(audio_chunks)} audio chunks...")
        
        # Update progress callback if provided
        if progress_callback:
            progress_callback(30, f"🎤 Transcribing {len(audio_chunks)} audio chunks...")
        
        all_segments = []
        cumulative_time = 0.0
        full_text_parts = []
        
        for i, chunk_path in enumerate(audio_chunks):
            # Calculate progress (30-50% range for transcription)
            chunk_progress = 30 + int((i / len(audio_chunks)) * 20)
            progress_msg = f"🎤 Transcribing chunk {i+1}/{len(audio_chunks)}..."
            
            logger.info(progress_msg)
            if progress_callback:
                progress_callback(chunk_progress, progress_msg)
            
            # Transcribe this chunk
            result = _transcribe_single_file(chunk_path)
            
            # Adjust timestamps for this chunk based on cumulative time
            if hasattr(result, 'segments'):
                for segment in result.segments:
                    # Create adjusted segment (handle both dict and object types)
                    if isinstance(segment, dict):
                        adjusted_segment = {
                            'start': segment['start'] + cumulative_time,
                            'end': segment['end'] + cumulative_time,
                            'text': segment['text']
                        }
                    else:
                        # segment is an object with attributes
                        adjusted_segment = {
                            'start': segment.start + cumulative_time,
                            'end': segment.end + cumulative_time,
                            'text': segment.text
                        }
                    all_segments.append(adjusted_segment)
            
            # Collect text
            if hasattr(result, 'text'):
                full_text_parts.append(result.text)
            
            # Update cumulative time for next chunk
            # Subtract overlap to account for the overlapping section
            chunk_duration_s = AudioSegment.from_mp3(chunk_path).duration_seconds
            cumulative_time += chunk_duration_s - (config.audio_chunk_overlap_ms / 1000.0)
        
        # Create combined result object
        class CombinedTranscriptionResult:
            """Combined transcription result from multiple chunks."""
            def __init__(self, segments: List[Dict], text: str):
                self.segments = segments
                self.text = text
        
        combined_text = " ".join(full_text_parts)
        logger.info(f"Successfully merged {len(audio_chunks)} chunks into single transcript")
        
        if progress_callback:
            progress_callback(50, f"✅ Merged {len(audio_chunks)} chunks successfully")
        
        # Cleanup chunk files
        chunk_dir = audio_path.parent / "chunks"
        if chunk_dir.exists():
            try:
                shutil.rmtree(chunk_dir)
                logger.info("Cleaned up temporary audio chunks")
            except Exception as e:
                logger.warning(f"Failed to cleanup chunks directory: {e}")
        
        return CombinedTranscriptionResult(all_segments, combined_text)


# -----------------------------
# LOCAL GPU TRANSCRIPTION
# -----------------------------
# Global variable to cache the loaded model
_gpu_model_cache = None

def transcribe_audio_with_local_gpu(audio_path: Path, progress_callback: Optional[callable] = None) -> Any:
    """
    Transcribe audio file using local GPU with faster-whisper.
    
    Uses the GTX 1080 GPU for fast, free transcription.
    Model is cached after first load for better performance.
    
    Args:
        audio_path: Path to audio file
        progress_callback: Optional callback function(progress: int, message: str) for UI updates
        
    Returns:
        Transcription result object with segments and text (compatible with OpenAI format)
        
    Raises:
        TranscriptionError: If transcription fails
    """
    global _gpu_model_cache
    
    try:
        # Load model (cached after first use)
        if _gpu_model_cache is None:
            logger.info("Loading Whisper model on GPU (first time, may take a few seconds)...")
            if progress_callback:
                progress_callback(30, "🎮 Loading Whisper model on GPU...")
            
            # Use small model with int8 for GTX 1080 (best balance of speed/quality)
            _gpu_model_cache = WhisperModel("small", device="cuda", compute_type="int8")
            logger.info("Whisper model loaded on GPU")
        
        if progress_callback:
            progress_callback(32, "🎮 Transcribing with local GPU (faster-whisper)...")
        
        logger.info(f"Transcribing {audio_path.name} with local GPU")
        
        # Transcribe
        segments_iter, info = _gpu_model_cache.transcribe(
            str(audio_path),
            language="en",
            beam_size=5,
            word_timestamps=False
        )
        
        # Collect segments and build text
        segments_list = []
        full_text_parts = []
        last_progress_update = 0
        
        for segment in segments_iter:
            # Convert faster-whisper segment to compatible format
            seg_dict = {
                'start': segment.start,
                'end': segment.end,
                'text': segment.text
            }
            segments_list.append(seg_dict)
            full_text_parts.append(segment.text)
            
            # Update progress periodically (every 5%)
            if info.duration > 0:
                progress_pct = (segment.end / info.duration) * 100
                if progress_pct - last_progress_update >= 5:
                    current_progress = 32 + int((progress_pct / 100) * 18)  # 32-50% range
                    if progress_callback:
                        progress_callback(current_progress, f"🎮 GPU transcribing... {progress_pct:.0f}%")
                    last_progress_update = progress_pct
        
        full_text = " ".join(full_text_parts)
        
        logger.info(f"GPU transcription complete: {len(segments_list)} segments, {len(full_text.split())} words")
        
        # Create result object compatible with OpenAI format
        class GPUTranscriptionResult:
            """GPU transcription result compatible with OpenAI Whisper format."""
            def __init__(self, segments: List[Dict], text: str):
                # Convert dict segments to objects with attributes
                class Segment:
                    def __init__(self, start, end, text):
                        self.start = start
                        self.end = end
                        self.text = text
                
                self.segments = [Segment(s['start'], s['end'], s['text']) for s in segments]
                self.text = text
        
        return GPUTranscriptionResult(segments_list, full_text)
        
    except Exception as e:
        logger.error(f"GPU transcription failed: {e}")
        raise TranscriptionError(f"GPU transcription failed: {str(e)}") from e


# -----------------------------
# SUMMARIZATION & KEY FACTORS
# -----------------------------
def call_openai_with_retry(messages: List[Dict[str, str]], max_tokens: int, max_retries: int = 3) -> str:
    """
    Call OpenAI API with retry logic and better error handling.
    
    Args:
        messages: List of message dictionaries for chat completion
        max_tokens: Maximum tokens in response
        max_retries: Maximum number of retry attempts
        
    Returns:
        Response content string
        
    Raises:
        ValueError: If client is not initialized
        APIQuotaError: If API quota exceeded
        APIConnectionError: If connection fails
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
            error_str = str(e).lower()
            
            # Check for quota/rate limit errors
            if 'rate_limit' in error_str or 'quota' in error_str or '429' in str(e):
                raise APIQuotaError(
                    "OpenAI API rate limit or quota exceeded. "
                    "Check your usage at https://platform.openai.com/usage"
                ) from e
            
            # Check for connection errors
            if 'connection' in error_str or 'timeout' in error_str or 'network' in error_str:
                if attempt < max_retries - 1:
                    logger.warning(f"Connection error, retrying... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    raise APIConnectionError(
                        "Could not connect to OpenAI API. Check your internet connection."
                    ) from e
            
            # Retry for other errors
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
    progress_callback: Optional[callable] = None,
    use_local_gpu: bool = False
) -> Dict[str, Any]:
    """
    Process a YouTube video - pure business logic with no UI code.
    Can be tested independently and reused in CLI, API, or other contexts.
    
    Args:
        url: YouTube video URL
        session_dir: Directory to save output files
        progress_callback: Optional callback function(progress: int, message: str) for UI updates
        use_local_gpu: If True, use local GPU transcription; if False, use OpenAI API
        
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
        logger.info(f"Processing YouTube video: {sanitize_url_for_log(url)}")
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
        
        # Note: Large files (>24MB) will be automatically split into chunks
        # by the transcribe_audio_with_timestamps function
        if file_size > config.max_audio_file_size_mb:
            logger.info(f"Audio file ({file_size:.2f} MB) exceeds single-file limit. Will use automatic chunking.")
        
        # Transcribe audio (choose method based on user selection)
        if use_local_gpu:
            update_progress(30, "🎮 Transcribing audio with local GPU...")
            logger.info("Step 2/6: Transcribing audio with local GPU (faster-whisper)...")
            result = transcribe_audio_with_local_gpu(audio_path, progress_callback=progress_callback)
        else:
            update_progress(30, "🎤 Transcribing audio with OpenAI Whisper API...")
            logger.info("Step 2/6: Transcribing audio with OpenAI Whisper API...")
            result = transcribe_audio_with_timestamps(audio_path, progress_callback=progress_callback)
        
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
        
        # Save to database
        update_progress(97, "💾 Saving to database...")
        try:
            from database import Project
            project = Project(
                type='youtube',
                title=video_title,
                content_title=transcript_title,
                source=url,
                created_at=metadata['timestamp'],
                word_count=metadata['word_count'],
                segment_count=metadata['segment_count'],
                project_dir=session_dir.name,
                notes='',
                tags=[]
            )
            db_manager.insert_project(project, transcript=full_text, summary=summary, key_factors=key_factors)
            logger.info("Project saved to database")
        except Exception as e:
            logger.warning(f"Failed to save to database: {e}")
            # Don't fail the whole process if database save fails
        
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
        logger.error(f"Processing failed for {sanitize_url_for_log(url)}: {e}")
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
        DocumentProcessingError: If document extraction or processing fails
        APIQuotaError: If API quota exceeded
        APIConnectionError: If connection to API fails
        ValueError: No text could be extracted or API client not initialized
        IOError: If file writes fail
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
            raise DocumentProcessingError("No text could be extracted from the document.")
        
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
        
        # Save to database
        update_progress(97, "💾 Saving to database...")
        try:
            from database import Project
            project = Project(
                type='document',
                title=uploaded_file.name,
                content_title=content_title,
                source=uploaded_file.name,
                created_at=metadata['timestamp'],
                word_count=metadata['word_count'],
                segment_count=0,
                project_dir=session_dir.name,
                notes='',
                tags=[]
            )
            db_manager.insert_project(project, transcript=full_text, summary=summary, key_factors=key_factors)
            logger.info("Project saved to database")
        except Exception as e:
            logger.warning(f"Failed to save to database: {e}")
            # Don't fail the whole process if database save fails
        
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
# API KEY CHECK
# -----------------------------
if client is None:
    st.error("⚠️ **OpenAI API Key Not Configured**")
    
    with st.expander("📋 **Setup Instructions** - Click to expand", expanded=True):
        st.markdown("""
        The application requires an OpenAI API key to function.
        
        ### Quick Setup (2 minutes):
        
        1. **Get an API key**
           - Visit: https://platform.openai.com/api-keys
           - Create an account (if needed)
           - Generate a new API key
        
        2. **Create `.env` file**
           ```bash
           # Windows
           copy env.template .env
           
           # Mac/Linux
           cp env.template .env
           ```
        
        3. **Add your API key to `.env`**
           ```ini
           OPENAI_API_KEY=sk-your-actual-key-here
           ```
        
        4. **Restart the application**
           ```bash
           streamlit run app.py.py
           ```
        
        ### Need Help?
        - See `SETUP.md` for detailed instructions
        - Check `README.md` for troubleshooting
        - Your `.env` file is protected by `.gitignore` and will never be committed
        """)
    
    st.info("💡 **Note for developers:** Your `.env` file stays local and is never pushed to GitHub!")
    st.stop()  # Don't show the rest of the UI

# -----------------------------
# MIGRATION CHECK
# -----------------------------
# Check if migration is needed on first run
old_outputs_dir = Path("outputs")
if old_outputs_dir.exists() and old_outputs_dir != config.output_dir:
    from migration import perform_migration_check_and_migrate
    
    if 'migration_completed' not in st.session_state:
        st.info("🔄 **First-time setup detected!** Migrating existing projects to new database and D: drive...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        def migration_progress(current, total, message):
            progress = int((current / total) * 100)
            progress_bar.progress(progress)
            status_text.text(message)
        
        try:
            migrated, message = perform_migration_check_and_migrate(
                db_manager,
                old_outputs_dir,
                config.output_dir,
                progress_callback=migration_progress
            )
            
            if migrated:
                st.success(f"✅ {message}")
                st.info(f"📁 Your data is now stored at: {config.data_root}")
                st.session_state.migration_completed = True
                st.rerun()
            else:
                st.session_state.migration_completed = True
        except Exception as e:
            st.error(f"❌ Migration failed: {e}")
            st.warning("You may need to manually check your data directories.")
            logger.error(f"Migration error: {e}")

# -----------------------------
# PAGE NAVIGATION
# -----------------------------
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Process"

# -----------------------------
# SIDEBAR: NAVIGATION & PROJECT HISTORY
# -----------------------------
with st.sidebar:
    st.header("🧭 Navigation")
    
    page = st.radio(
        "Select Page",
        options=["Process", "Database Explorer"],
        index=0 if st.session_state.current_page == "Process" else 1,
        label_visibility="collapsed"
    )
    
    if page != st.session_state.current_page:
        st.session_state.current_page = page
        st.rerun()
    
    st.markdown("---")
    st.header("📁 Project History")
    
    # Quick search in sidebar
    search_query = st.text_input("🔍 Quick search", placeholder="Search projects...", key="sidebar_search")
    
    # Get projects from database
    try:
        if search_query:
            db_projects = db_manager.list_projects(search_query=search_query, limit=20)
        else:
            db_projects = db_manager.list_projects(limit=20, order_by="created_at", order_desc=True)
        
        # Convert to dict format for compatibility
        projects = []
        for p in db_projects:
            # Ensure source is a string
            source = str(p.source) if p.source else ''
            
            proj_dict = {
                'project_dir': p.project_dir,
                'title': p.title or '',
                'transcript_title': p.content_title if p.type == 'youtube' else None,
                'content_title': p.content_title if p.type == 'document' else None,
                'url': source if p.type == 'youtube' else None,
                'filename': source if p.type == 'document' else None,
                'timestamp': p.created_at or '',
                'word_count': p.word_count or 0,
                'tags': list(p.tags) if p.tags else []
            }
            projects.append(proj_dict)
    except Exception as e:
        logger.error(f"Failed to load projects from database: {e}")
        # Fallback to file-based loading
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
                    if proj.get('url'):
                        vid_id = extract_video_id(str(proj['url']))
                        if vid_id:
                            # Determine if it's a short or regular video
                            if '/shorts/' in str(proj['url']):
                                project_name = f"Short {vid_id[:11]}"
                            else:
                                project_name = f"Video {vid_id[:11]}"
                        else:
                            project_name = f"Video {idx + 1}"
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
                if 'url' in proj and proj['url']:
                    st.write("**Type:** YouTube Video")
                    if 'transcript_title' in proj and proj['transcript_title']:
                        st.write(f"**Content Title:** {proj['transcript_title']}")
                    if 'title' in proj and proj['title']:
                        st.write(f"**Video Title:** {proj['title']}")
                    st.write(f"**URL:** {format_url_for_display(proj['url'])}")
                elif 'filename' in proj and proj['filename']:
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

# -----------------------------
# PAGE ROUTING
# -----------------------------
if st.session_state.current_page == "Database Explorer":
    # Show database explorer UI
    from ui_database_explorer import render_database_explorer
    render_database_explorer(db_manager, config.output_dir)
    st.stop()

# Otherwise, show the main processing interface
# Mode selector
mode = st.radio("Select input type:", ["YouTube Video", "Document File"], horizontal=True)

st.markdown("---")

if mode == "YouTube Video":
    st.subheader("🎧 YouTube Video Analysis")
    url = st.text_input("Enter a YouTube URL:", "")
    
    # Transcription method selection
    st.markdown("### Transcription Method")
    transcription_method = st.radio(
        "Choose how to transcribe:",
        options=["Local GPU (Faster, FREE)", "OpenAI API (Best Quality)"],
        index=0,  # Default to Local GPU
        help="Local GPU: 2x faster, free, ~90-95% accuracy. OpenAI API: Best quality (~98-99%), ~$0.60/video"
    )
    use_local_gpu = (transcription_method == "Local GPU (Faster, FREE)")
    
    # Show info about selected method
    if use_local_gpu:
        st.info("🎮 **Using Local GPU (GTX 1080)**: ~5 min for 100-min video, FREE, good accuracy")
    else:
        st.info("☁️ **Using OpenAI API**: ~10 min for 100-min video, ~$0.60, best accuracy")
    
    process_button = st.button("Process Video")
    
    if process_button:
        # Clear previous results when starting new video
        if 'youtube_results' in st.session_state:
            st.session_state.pop('youtube_results')
        
        if not url.strip():
            st.error("Please enter a valid YouTube URL.")
            st.stop()
        
        # Validate YouTube URL
        if not validate_youtube_url(url):
            st.error("❌ Invalid YouTube URL. Please enter a valid YouTube, YouTube Shorts, or youtu.be link.")
            logger.warning(f"Invalid YouTube URL attempted: {sanitize_url_for_log(url)}")
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
            results = process_youtube_video(url, session_dir, progress_callback=update_ui, use_local_gpu=use_local_gpu)
            
            # Brief pause to show completion
            time.sleep(0.5)
            progress_bar.empty()
            status_text.empty()
            
            st.success("✅ Processing complete!")
            
            # Save results to session state for persistent display
            st.session_state['youtube_results'] = results
            
            # Render results using UI function
            render_youtube_results(results)

        except AudioDownloadError as e:
            st.error(f"❌ **Download Failed**")
            st.error(str(e))
            st.info("**Suggestions:**\n"
                   "- Verify the video is public and available\n"
                   "- Check if the video is available in your region\n"
                   "- Try a different video URL")
            logger.error(f"Audio download error: {e}")
            
        except FileSizeError as e:
            st.error(f"❌ **File Too Large**")
            st.error(str(e))
            st.info("**Suggestions:**\n"
                   "- Try a shorter video (under 30 minutes)\n"
                   "- Lower the audio quality in your .env file (AUDIO_QUALITY=64)\n"
                   "- The Whisper API has a 25MB file size limit")
            logger.error(f"File size error: {e}")
            
        except TranscriptionError as e:
            st.error(f"❌ **Transcription Failed**")
            st.error(str(e))
            st.info("**Suggestions:**\n"
                   "- Check that your OpenAI API key is valid\n"
                   "- Ensure you have API credits available\n"
                   "- Visit: https://platform.openai.com/usage")
            logger.error(f"Transcription error: {e}")
            
        except APIQuotaError as e:
            st.error(f"❌ **API Quota Exceeded**")
            st.error(str(e))
            st.warning("**What to do:**\n"
                      "1. Check your OpenAI usage dashboard\n"
                      "2. Add credits or upgrade your plan\n"
                      "3. Wait for your rate limit to reset\n"
                      "4. Visit: https://platform.openai.com/usage")
            logger.error(f"API quota error: {e}")
            
        except APIConnectionError as e:
            st.error(f"❌ **Connection Failed**")
            st.error(str(e))
            st.info("**Suggestions:**\n"
                   "- Check your internet connection\n"
                   "- Verify OpenAI services are operational\n"
                   "- Check: https://status.openai.com/\n"
                   "- Try again in a few moments")
            logger.error(f"API connection error: {e}")
            
        except Exception as e:
            st.error(f"❌ **Unexpected Error**")
            st.error(str(e))
            st.info("**Troubleshooting:**\n"
                   "- Check the app.log file for details\n"
                   "- Verify all dependencies are installed\n"
                   "- Ensure FFmpeg is installed and in PATH\n"
                   "- Try restarting the application")
            logger.error(f"Unexpected error: {e}")
            if st.checkbox("Show technical details"):
                st.exception(e)
    
    # Display persistent results if available (even after clicking download buttons)
    if 'youtube_results' in st.session_state and not process_button:
        st.divider()
        st.info("📥 **Previous Results** - Downloads remain available until you process a new video")
        
        # Add clear button
        if st.button("🗑️ Clear Results"):
            st.session_state.pop('youtube_results')
            st.rerun()
        
        render_youtube_results(st.session_state['youtube_results'])

else:  # Document File mode
    st.subheader("📄 Document Analysis")
    uploaded_file = st.file_uploader(
        "Upload a document (PDF, DOCX, or TXT):",
        type=['pdf', 'docx', 'txt']
    )
    
    process_doc_button = st.button("Process Document")
    
    if process_doc_button:
        # Clear previous results when starting new document
        if 'document_results' in st.session_state:
            st.session_state.pop('document_results')
        
        if uploaded_file is None:
            st.error("Please upload a document file.")
            st.stop()
        
        # Validate file size (security: prevent memory exhaustion)
        file_size_mb = uploaded_file.size / (1024 * 1024)
        if file_size_mb > config.max_document_upload_mb:
            st.error(f"❌ **File Too Large**")
            st.error(f"File size: {file_size_mb:.1f}MB (Maximum: {config.max_document_upload_mb}MB)")
            st.info("**Suggestions:**\n"
                   "- Split large documents into smaller files\n"
                   "- Remove unnecessary images or formatting\n"
                   "- Convert to plain text format")
            logger.warning(f"File upload rejected: {file_size_mb:.1f}MB exceeds limit")
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
            
            # Save results to session state for persistent display
            st.session_state['document_results'] = results
            
            # Render results using UI function
            render_document_results(results)
        
        except DocumentProcessingError as e:
            st.error(f"❌ **Document Processing Failed**")
            st.error(str(e))
            st.info("**Suggestions:**\n"
                   "- Ensure the document is not corrupted\n"
                   "- Try converting to a different format (PDF, DOCX, or TXT)\n"
                   "- Check that the file contains readable text\n"
                   "- Verify the file is not password-protected")
            logger.error(f"Document processing error: {e}")
            
        except APIQuotaError as e:
            st.error(f"❌ **API Quota Exceeded**")
            st.error(str(e))
            st.warning("**What to do:**\n"
                      "1. Check your OpenAI usage dashboard\n"
                      "2. Add credits or upgrade your plan\n"
                      "3. Wait for your rate limit to reset\n"
                      "4. Visit: https://platform.openai.com/usage")
            logger.error(f"API quota error: {e}")
            
        except APIConnectionError as e:
            st.error(f"❌ **Connection Failed**")
            st.error(str(e))
            st.info("**Suggestions:**\n"
                   "- Check your internet connection\n"
                   "- Verify OpenAI services are operational\n"
                   "- Check: https://status.openai.com/\n"
                   "- Try again in a few moments")
            logger.error(f"API connection error: {e}")
            
        except Exception as e:
            st.error(f"❌ **Unexpected Error**")
            st.error(str(e))
            st.info("**Troubleshooting:**\n"
                   "- Check the app.log file for details\n"
                   "- Verify all dependencies are installed (PyPDF2, python-docx)\n"
                   "- Ensure the document format is supported\n"
                   "- Try restarting the application")
            logger.error(f"Unexpected document error: {e}")
            if st.checkbox("Show technical details", key="doc_details"):
                st.exception(e)
    
    # Display persistent results if available (even after clicking download buttons)
    if 'document_results' in st.session_state and not process_doc_button:
        st.divider()
        st.info("📥 **Previous Results** - Downloads remain available until you process a new document")
        
        # Add clear button
        if st.button("🗑️ Clear Results", key="clear_doc_results"):
            st.session_state.pop('document_results')
            st.rerun()
        
        render_document_results(st.session_state['document_results'])

st.markdown("---")
st.caption("Built with ❤️ using Python, Streamlit, yt-dlp, and OpenAI Whisper + GPT-4o-mini")