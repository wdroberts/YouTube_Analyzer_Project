"""
YouTube Analyzer - Main Application
Transcribe and analyze YouTube videos and documents using OpenAI's Whisper and GPT.
"""
# Standard library imports
import html
import io
import json
import logging
import os
import random
import re
import shutil
import sys
import unicodedata
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar
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
from sidebar_ops import record_sidebar_operation
from telemetry import evaluate_health_alerts

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

# Fix Windows console encoding for emoji support before attaching any handlers
if sys.platform == 'win32':
    for stream_attr in ("stdout", "stderr"):
        stream = getattr(sys, stream_attr, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding='utf-8')
            except (AttributeError, ValueError):
                # If reconfigure is unavailable or fails, continue gracefully
                pass

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

# -----------------------------
# CONFIGURATION
# -----------------------------
@dataclass
class Config:
    """Application configuration with validation."""
    audio_quality: int = field(default_factory=lambda: int(os.getenv("AUDIO_QUALITY", "96")))
    summary_max_tokens: int = 1000
    key_factors_max_tokens: int = 1500
    title_max_tokens: int = 50
    title_sample_size: int = 2000
    project_title_max_length: int = 30
    url_display_max_length: int = 45
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
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
    
    # Q&A Service Configuration
    qa_temperature: float = float(os.getenv("QA_TEMPERATURE", "0.7"))  # Creativity (0.0-2.0)
    qa_max_tokens: int = int(os.getenv("QA_MAX_TOKENS", "800"))  # Max response length
    qa_max_context_chars: int = int(os.getenv("QA_MAX_CONTEXT_CHARS", "15000"))  # Max context length
    qa_min_question_length: int = 5  # Minimum question length
    qa_max_question_length: int = 500  # Maximum question length
    telemetry_trash_warning_mb: int = int(os.getenv("TELEMETRY_TRASH_WARNING_MB", "500"))
    telemetry_failure_threshold: int = int(os.getenv("TELEMETRY_FAILURE_THRESHOLD", "3"))
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.audio_quality < 32 or self.audio_quality > 320:
            raise ValueError(f"Invalid audio quality: {self.audio_quality}. Must be between 32-320 kbps")
        if self.max_audio_file_size_mb > 25:
            raise ValueError(f"Max file size cannot exceed 25MB (Whisper API limit)")

        missing_openai_key = not os.getenv("OPENAI_API_KEY")
        running_under_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
        running_in_ci = os.getenv("CI") not in (None, "", "0", "false", "False")

        if missing_openai_key:
            logger.warning("OPENAI_API_KEY is not set; the app will not contact OpenAI until it is configured.")

        if missing_openai_key and not (running_under_pytest or running_in_ci):
            raise ValueError(
                "Missing required configuration: OPENAI_API_KEY must be set in your .env file before starting the app."
            )
        
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
from database import DatabaseManager, ProjectNotFoundError
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
    """Convert string to safe filename by replacing invalid chars with underscores."""
    result_chars = []
    punctuation_sequence = False

    for ch in s:
        if re.match(r"[a-zA-Z0-9_\-]", ch):
            result_chars.append(ch)
            punctuation_sequence = False
        elif ch.isspace():
            result_chars.append("_")
            punctuation_sequence = False
        else:
            category = unicodedata.category(ch)
            is_punctuation_or_symbol = category.startswith("P") or category.startswith("S")

            if is_punctuation_or_symbol:
                if not punctuation_sequence:
                    result_chars.append("_")
                    punctuation_sequence = True
            else:
                result_chars.append("_")
                punctuation_sequence = False

    return "".join(result_chars)


def validate_and_sanitize_path(path_component: str, base_dir: Path, allow_absolute: bool = False) -> Tuple[bool, Optional[Path], str]:
    """
    Validate and sanitize a path component to prevent directory traversal attacks.
    
    Ensures the resulting path:
    - Stays within the base directory
    - Doesn't contain traversal patterns (.., /, \\)
    - Resolves to a path that's actually within base_dir (prevents symlink attacks)
    - Uses only safe characters
    
    Args:
        path_component: Path component to validate (e.g., project directory name)
        base_dir: Base directory that the path must stay within
        allow_absolute: If False, rejects absolute paths
        
    Returns:
        Tuple of (is_valid: bool, sanitized_path: Optional[Path], error_message: str)
        If valid, sanitized_path is the safe Path object, error_message is empty
    """
    if not path_component or not isinstance(path_component, str):
        return False, None, "Path component is empty or invalid"
    
    # Reject empty strings or whitespace-only
    if not path_component.strip():
        return False, None, "Path component cannot be empty"
    
    # Check for directory traversal patterns
    traversal_patterns = ['..', '/', '\\']
    for pattern in traversal_patterns:
        if pattern in path_component:
            logger.warning(f"Rejected path with traversal pattern '{pattern}': {sanitize_url_for_log(path_component)}")
            return False, None, f"Path contains forbidden pattern: {pattern}"
    
    # Check for null bytes
    if '\x00' in path_component:
        logger.warning(f"Rejected path with null byte: {sanitize_url_for_log(path_component)}")
        return False, None, "Path contains null byte"
    
    # Reject absolute paths if not allowed
    if not allow_absolute:
        # Check for absolute path indicators
        if path_component.startswith('/') or (len(path_component) > 1 and path_component[1] == ':'):
            logger.warning(f"Rejected absolute path: {sanitize_url_for_log(path_component)}")
            return False, None, "Absolute paths are not allowed"
    
    # Sanitize the path component
    sanitized_component = safe_filename(path_component)
    if not sanitized_component:
        return False, None, "Path component became empty after sanitization"
    
    # Construct the full path
    try:
        full_path = base_dir / sanitized_component
        
        # Resolve to absolute path to check for symlink attacks
        # This ensures we're actually within base_dir even if there are symlinks
        resolved_path = full_path.resolve()
        resolved_base = base_dir.resolve()
        
        # Ensure resolved path is actually within base directory
        try:
            # Use relative_to to check if path is within base
            resolved_path.relative_to(resolved_base)
        except ValueError:
            # Path is outside base directory (possible symlink attack)
            logger.warning(f"Rejected path outside base directory: {sanitize_url_for_log(path_component)} "
                         f"(resolved to {resolved_path}, base is {resolved_base})")
            return False, None, "Path resolves outside allowed directory"
        
        # Additional check: ensure parent is exactly base_dir (prevents ../ attacks)
        if full_path.parent.resolve() != resolved_base:
            logger.warning(f"Rejected path with invalid parent: {sanitize_url_for_log(path_component)}")
            return False, None, "Path has invalid parent directory"
        
        return True, full_path, ""
        
    except (OSError, ValueError) as e:
        logger.error(f"Path validation error for {sanitize_url_for_log(path_component)}: {e}")
        return False, None, f"Path validation failed: {e}"


def validate_youtube_url(url: str) -> bool:
    """
    Validate that URL is from YouTube or YouTube Shorts with enhanced security checks.
    
    Performs strict validation including:
    - Domain whitelist check
    - Protocol validation (http/https only)
    - Video ID format validation (11 alphanumeric characters)
    - Rejection of suspicious parameters and schemes
    
    Args:
        url: URL string to validate
        
    Returns:
        True if valid YouTube URL, False otherwise
    """
    if url is None or not isinstance(url, str) or not url.strip():
        return False
    
    # Reject suspicious schemes immediately
    url_lower = url.lower().strip()
    suspicious_schemes = ['javascript:', 'data:', 'vbscript:', 'file:', 'about:']
    if any(url_lower.startswith(scheme) for scheme in suspicious_schemes):
        logger.warning(f"Rejected suspicious URL scheme: {sanitize_url_for_log(url)}")
        return False
    
    try:
        parsed = urlparse(url)
        
        # Must have valid domain
        if parsed.netloc not in VALID_YOUTUBE_DOMAINS:
            return False
        
        # Must use http or https protocol
        if parsed.scheme not in ('http', 'https'):
            logger.warning(f"Rejected non-HTTP(S) protocol: {sanitize_url_for_log(url)}")
            return False
        
        # Extract and validate video ID
        video_id = extract_video_id(url)
        
        # Video ID must be present and valid format
        if not video_id:
            logger.warning(f"No video ID found in URL: {sanitize_url_for_log(url)}")
            return False
        
        # YouTube video IDs are exactly 11 alphanumeric characters
        # Allow hyphens and underscores for edge cases
        if len(video_id) != 11 or not all(c.isalnum() or c in ('-', '_') for c in video_id):
            logger.warning(f"Invalid video ID format: {sanitize_url_for_log(video_id)}")
            return False
        
        # Additional security: check for suspicious query parameters
        if parsed.query:
            suspicious_params = ['javascript', 'onclick', 'onerror', 'eval', 'script']
            query_lower = parsed.query.lower()
            if any(param in query_lower for param in suspicious_params):
                logger.warning(f"Rejected URL with suspicious parameters: {sanitize_url_for_log(url)}")
                return False
        
        return True
        
    except (ValueError, TypeError, AttributeError) as e:
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


T = TypeVar("T")


def _run_with_backoff(
    operation_name: str,
    func: Callable[[], T],
    *,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter: float = 0.3,
    retry_exceptions: Tuple[type, ...] = (Exception,),
    context: Optional[str] = None
) -> T:
    """
    Execute `func` with exponential backoff and jitter.
    Logs retry attempts and surfaces the final exception if all retries fail.
    """
    attempt = 0
    delay = initial_delay
    start_time = time.perf_counter()
    context_info = f" [{context}]" if context else ""

    while True:
        attempt += 1
        try:
            result = func()
            elapsed = time.perf_counter() - start_time
            logger.info(f"{operation_name}{context_info} succeeded on attempt {attempt} in {elapsed:.2f}s")
            return result
        except retry_exceptions as exc:
            if attempt >= max_retries:
                logger.error(f"{operation_name}{context_info} failed after {attempt} attempts: {exc}")
                raise

            sleep_time = delay + random.uniform(0, jitter)
            logger.warning(
                f"{operation_name}{context_info} attempt {attempt} failed: {exc}. Retrying in {sleep_time:.1f}s."
            )
            time.sleep(sleep_time)
            delay *= backoff_factor


# Q&A functionality moved to qa_service.py for better modularity
# Import it here for backward compatibility
from qa_service import answer_question_from_transcript as _qa_function


def sanitize_chat_question(question: str) -> str:
    """
    Sanitize chat question input for security.
    
    Performs:
    - HTML/script tag stripping
    - Control character removal (except newline, tab, carriage return)
    - Unicode normalization
    - Excessive whitespace cleanup
    - Basic XSS prevention
    
    Args:
        question: Raw question input from user
        
    Returns:
        Sanitized question string safe for processing
    """
    if not question or not isinstance(question, str):
        return ""
    
    # Remove HTML/XML tags (basic XSS prevention)
    # This regex removes <...> tags but preserves content
    question = re.sub(r'<[^>]+>', '', question)
    
    # Remove script-related patterns (case-insensitive)
    script_patterns = [
        r'javascript:',
        r'on\w+\s*=',  # Event handlers like onclick=, onerror=
        r'<script',
        r'</script>',
        r'eval\s*\(',
        r'expression\s*\(',
    ]
    for pattern in script_patterns:
        question = re.sub(pattern, '', question, flags=re.IGNORECASE)
    
    # Remove control characters except newline (\n), tab (\t), and carriage return (\r)
    # Control characters are in range 0x00-0x1F except 0x09 (tab), 0x0A (newline), 0x0D (carriage return)
    # Also remove DEL (0x7F) and other non-printable Unicode characters
    sanitized_chars = []
    for char in question:
        code_point = ord(char)
        # Allow printable ASCII (32-126), tab (9), newline (10), carriage return (13)
        if (32 <= code_point <= 126) or code_point in (9, 10, 13):
            sanitized_chars.append(char)
        # Allow common Unicode characters (letters, numbers, punctuation, symbols)
        elif unicodedata.category(char)[0] in ('L', 'N', 'P', 'S', 'Z'):
            sanitized_chars.append(char)
        # Remove everything else (control chars, private use, etc.)
    
    question = ''.join(sanitized_chars)
    
    # Unicode normalization (prevent homograph attacks)
    question = unicodedata.normalize('NFKC', question)
    
    # Clean up excessive whitespace (multiple spaces, newlines)
    # Preserve tabs and single newlines, but clean up excessive spaces
    question = re.sub(r' +', ' ', question)  # Multiple spaces -> single space
    question = re.sub(r'\n{3,}', '\n\n', question)  # More than 2 newlines -> 2 newlines
    question = question.strip()
    
    return question


def check_chat_rate_limit(project_key: str, min_seconds: int = 2) -> Tuple[bool, Optional[float]]:
    """
    Check if chat question can be submitted based on rate limiting.
    
    Args:
        project_key: Unique key for the project/chat session
        min_seconds: Minimum seconds between chat submissions
        
    Returns:
        Tuple of (is_allowed: bool, wait_time: Optional[float])
        If not allowed, wait_time is the seconds to wait
    """
    rate_limit_key = f"chat_rate_limit_{project_key}"
    current_time = time.time()
    
    if rate_limit_key not in st.session_state:
        st.session_state[rate_limit_key] = current_time
        return True, None
    
    last_chat_time = st.session_state[rate_limit_key]
    time_since_last = current_time - last_chat_time
    
    if time_since_last < min_seconds:
        wait_time = min_seconds - time_since_last
        return False, wait_time
    
    # Update last chat time
    st.session_state[rate_limit_key] = current_time
    return True, None


def answer_question_from_transcript(question: str, transcript: str, title: str, 
                                    summary: str = "") -> str:
    """
    Answer questions about transcript content using GPT.
    
    This is a wrapper function that calls the qa_service module.
    The actual implementation is in qa_service.py for better modularity.
    
    Args:
        question: User's question about the content
        transcript: Full transcript text
        title: Project title for context
        summary: Optional summary for additional context
        
    Returns:
        AI-generated answer based on the transcript
        
    Raises:
        ValueError: If OpenAI client not initialized
    """
    return _qa_function(
        question=question,
        transcript=transcript,
        title=title,
        summary=summary,
        client=client,
        model=config.openai_model
    )


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


# File signature (magic bytes) for supported formats
FILE_SIGNATURES = {
    'pdf': [b'%PDF'],
    'docx': [b'PK\x03\x04', b'PK\x05\x06'],  # ZIP-based format (DOCX is a ZIP)
    'txt': []  # Text files have no signature, validate by content
}


def validate_uploaded_file(uploaded_file: Any) -> Tuple[bool, str]:
    """
    Validate uploaded file with security checks.
    
    Performs:
    - Filename sanitization
    - File extension validation
    - Content-type verification via magic bytes
    - Basic malicious file detection
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Returns:
        Tuple of (is_valid: bool, error_message: str)
        If valid, error_message is empty string
    """
    if uploaded_file is None:
        return False, "No file provided"
    
    # Get original filename and sanitize
    original_name = uploaded_file.name if hasattr(uploaded_file, 'name') else 'unknown'
    sanitized_name = safe_filename(original_name)
    
    # Check for suspicious filename patterns
    suspicious_patterns = [
        '..',  # Directory traversal
        '/', '\\',  # Path separators
        '\x00',  # Null bytes
        '<', '>', '|', ':', '"', '*', '?',  # Windows forbidden chars
    ]
    
    for pattern in suspicious_patterns:
        if pattern in original_name:
            logger.warning(f"Rejected file with suspicious pattern '{pattern}': {sanitize_url_for_log(original_name)}")
            return False, f"Invalid filename: contains forbidden characters"
    
    # Validate file extension
    file_name_lower = original_name.lower()
    valid_extensions = ['.pdf', '.docx', '.txt']
    file_ext = None
    
    for ext in valid_extensions:
        if file_name_lower.endswith(ext):
            file_ext = ext[1:]  # Remove the dot
            break
    
    if not file_ext:
        return False, f"Unsupported file type. Please use PDF, DOCX, or TXT files."
    
    # Read file bytes for signature verification
    try:
        # Save current position
        current_pos = uploaded_file.tell() if hasattr(uploaded_file, 'tell') else 0
        file_bytes = uploaded_file.read()
        # Reset position for later processing
        if hasattr(uploaded_file, 'seek'):
            uploaded_file.seek(current_pos)
    except Exception as e:
        logger.error(f"Failed to read file for validation: {e}")
        return False, "Unable to read file for validation"
    
    # Check for empty file first
    if len(file_bytes) == 0:
        return False, "File is empty"
    
    # Verify file signature (magic bytes)
    if file_ext in FILE_SIGNATURES and FILE_SIGNATURES[file_ext]:
        signatures = FILE_SIGNATURES[file_ext]
        file_start = file_bytes[:min(10, len(file_bytes))]
        
        if not any(file_start.startswith(sig) for sig in signatures):
            logger.warning(f"File signature mismatch for {sanitize_url_for_log(original_name)}: "
                         f"expected {file_ext}, got {file_bytes[:4]}")
            return False, (f"File content does not match declared type ({file_ext.upper()}). "
                          f"The file may be corrupted or mislabeled.")
    
    # Additional validation for text files (check if it's actually text)
    if file_ext == 'txt':
        try:
            # Try to decode as UTF-8 to verify it's text
            sample = file_bytes[:1024]  # Check first 1KB
            sample.decode('utf-8', errors='strict')
        except UnicodeDecodeError:
            # If strict decode fails, check if it's binary
            # Text files should have mostly printable characters
            printable_ratio = sum(1 for b in sample if 32 <= b <= 126 or b in (9, 10, 13)) / len(sample) if sample else 0
            if printable_ratio < 0.7:  # Less than 70% printable = likely binary
                return False, "File appears to be binary data, not text. Please ensure it's a valid text file."
    
    # Check for suspiciously large files (additional safety beyond size limit)
    if len(file_bytes) == 0:
        return False, "File is empty"
    
    # Check for embedded scripts in PDFs (basic check)
    if file_ext == 'pdf' and b'<script' in file_bytes[:10000].lower():
        logger.warning(f"Rejected PDF with potential embedded script: {sanitize_url_for_log(original_name)}")
        return False, "File contains potentially unsafe content"
    
    return True, ""


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

    def _download_attempt():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)

    try:
        info = _run_with_backoff(
            "YouTube download",
            _download_attempt,
            max_retries=3,
            initial_delay=1.0,
            backoff_factor=2.0,
            jitter=0.5,
            context=url
        )
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

    def _whisper_api_call():
        with open(audio_path, "rb") as audio_file:
            return client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                timeout=config.api_timeout_seconds
            )

    try:
        result = _run_with_backoff(
            "Whisper-1 transcription",
            _whisper_api_call,
            max_retries=3,
            initial_delay=2.0,
            backoff_factor=2.0,
            jitter=0.6,
            context=audio_path.name
        )
        return result
    except Exception as e:
        error_str = str(e).lower()
        
        if '413' in error_str or 'payload too large' in error_str or 'file size' in error_str:
            raise FileSizeError(
                f"Audio file too large for Whisper API (limit: {config.max_audio_file_size_mb}MB). "
                f"Try a shorter video or reduce audio quality."
            ) from e

        if 'rate_limit' in error_str or 'quota' in error_str or '429' in error_str:
            raise APIQuotaError(
                "OpenAI API rate limit or quota exceeded. "
                "Check your usage at https://platform.openai.com/usage"
            ) from e

        if 'connection' in error_str or 'timeout' in error_str or 'network' in error_str:
            raise APIConnectionError(
                "Could not connect to OpenAI API. Check your internet connection."
            ) from e

        raise TranscriptionError(
            f"Transcription failed after multiple retries: {str(e)}"
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
        def _gpu_transcription():
            return _gpu_model_cache.transcribe(
                str(audio_path),
                language="en",
                beam_size=5,
                word_timestamps=False
            )

        segments_iter, info = _run_with_backoff(
            "Local GPU transcription",
            _gpu_transcription,
            max_retries=2,
            initial_delay=0.5,
            backoff_factor=2.0,
            jitter=0.3,
            context=audio_path.name
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

    def _chat_call():
        return client.chat.completions.create(
            model=config.openai_model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=config.api_timeout_seconds
        )

    try:
        response = _run_with_backoff(
            "OpenAI chat completion",
            _chat_call,
            max_retries=max_retries,
            initial_delay=1.0,
            backoff_factor=2.0,
            jitter=0.4,
            context=f"model={config.openai_model}"
        )
    except Exception as e:
        error_str = str(e).lower()

        if 'rate_limit' in error_str or 'quota' in error_str or '429' in error_str:
            raise APIQuotaError(
                "OpenAI API rate limit or quota exceeded. "
                "Check your usage at https://platform.openai.com/usage"
            ) from e

        if 'connection' in error_str or 'timeout' in error_str or 'network' in error_str:
            raise APIConnectionError(
                "Could not connect to OpenAI API. Check your internet connection."
            ) from e

        raise

    usage = getattr(response, "usage", None)
    tokens_used = None
    if usage:
        tokens_used = getattr(usage, "total_tokens", None)
        if tokens_used is None and isinstance(usage, dict):
            tokens_used = usage.get("total_tokens")

    logger.info(
        f"OpenAI chat completion tokens={tokens_used or 'unknown'}, model={config.openai_model}"
    )

    return response.choices[0].message.content


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
            
            # Cleanup audio file after successful database save
            update_progress(98, "🗑️ Cleaning up audio file...")
            try:
                if audio_path.exists():
                    audio_path.unlink()
                    logger.info(f"Cleaned up audio file: {audio_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup audio file {audio_path}: {cleanup_error}")
                # Don't fail the whole process if cleanup fails
                
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


@dataclass
class DeletionResult:
    project_dir: str
    success: bool = False
    disk_removed: bool = False
    db_deleted: bool = False
    message: str = ""
    trash_path: Optional[Path] = None
    project_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def _safe_read_text_file(path: Path) -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read {path}: {e}")
    return ""


def _read_project_metadata(project_path: Path) -> Dict[str, Any]:
    metadata_file = project_path / "metadata.json"
    if metadata_file.exists():
        try:
            return json.loads(metadata_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to parse metadata for {project_path.name}: {e}")
    return {}


def _create_trash_destination(project_dir_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trash_dir = config.data_root / "trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    return trash_dir / f"{project_dir_name}_{timestamp}"


def _append_deletion_log(entry: Dict[str, Any]) -> None:
    log_dir = config.data_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "deletions.log"
    entry['timestamp'] = datetime.now().isoformat()
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def delete_project(project_dir_name: str) -> DeletionResult:
    """
    Delete a project directory, remove its database entry, and log the action.
    
    Args:
        project_dir_name: Name of project directory to delete
        
    Returns:
        DeletionResult describing the outcome.
    """
    result = DeletionResult(project_dir=project_dir_name)

    # Validate and sanitize directory name to prevent path traversal
    is_valid, project_path, error_msg = validate_and_sanitize_path(
        project_dir_name,
        config.output_dir,
        allow_absolute=False
    )
    
    if not is_valid:
        result.message = error_msg or "Invalid directory name."
        logger.warning(f"Invalid project directory name: {project_dir_name} - {error_msg}")
        _append_deletion_log({
            "action": "delete",
            "project_dir": project_dir_name,
            "message": result.message
        })
        return result
    result.metadata = _read_project_metadata(project_path)

    project = None
    try:
        project = db_manager.get_project_by_dir(project_dir_name)
    except Exception as e:
        logger.warning(f"Unable to locate project {project_dir_name} in database: {e}")

    if project:
        result.project_id = project.id

    message_parts = []

    # Move files to trash for safe cleanup
    # Additional safety check: ensure path is still within output_dir after resolution
    if project_path.exists() and project_path.resolve().parent == config.output_dir.resolve():
        try:
            trash_path = _create_trash_destination(project_dir_name)
            shutil.move(str(project_path), str(trash_path))
            result.disk_removed = True
            result.trash_path = trash_path
            message_parts.append("Project files moved to trash.")
            logger.info(f"Moved {project_dir_name} to trash at {trash_path}")
        except Exception as e:
            message_parts.append(f"Failed to move files: {str(e)}")
            logger.error(f"Failed to move project {project_dir_name} to trash: {e}")
    else:
        message_parts.append("Project files not found.")

    # Clean up database entry when available
    if result.project_id is not None:
        try:
            db_manager.delete_project(result.project_id)
            result.db_deleted = True
            message_parts.append("Database entry removed.")
        except Exception as e:
            message_parts.append(f"Database cleanup failed: {e}")
            logger.error(f"Failed to delete project {project_dir_name} from database: {e}")
    else:
        message_parts.append("No database entry to remove.")

    result.success = result.disk_removed or result.db_deleted
    result.message = " ".join(message_parts).strip()

    _append_deletion_log({
        "action": "delete",
        "project_dir": project_dir_name,
        "disk_removed": result.disk_removed,
        "db_removed": result.db_deleted,
        "trash_path": str(result.trash_path) if result.trash_path else None,
        "message": result.message
    })

    return result


def restore_project_from_trash(tombstone: Dict[str, Any]) -> Tuple[bool, str]:
    trash_path_str = tombstone.get("trash_path") or ""
    project_dir = tombstone.get("project_dir")

    if not project_dir:
        return False, "No project information found."

    # Validate project directory name
    is_valid, target_path, error_msg = validate_and_sanitize_path(
        project_dir,
        config.output_dir,
        allow_absolute=False
    )
    
    if not is_valid:
        logger.warning(f"Invalid project directory in restore request: {project_dir} - {error_msg}")
        return False, error_msg or "Invalid project directory name."

    # Validate trash path
    trash_path = Path(trash_path_str)
    if not trash_path.exists():
        return False, "Trash entry is missing."
    
    # Ensure trash path is within trash directory
    trash_dir = config.data_root / "trash"
    try:
        trash_path.resolve().relative_to(trash_dir.resolve())
    except ValueError:
        logger.warning(f"Trash path outside trash directory: {trash_path}")
        return False, "Invalid trash path location."
    if target_path.exists():
        return False, f"Project {project_dir} already exists."

    try:
        shutil.move(str(trash_path), str(target_path))
    except Exception as e:
        logger.error(f"Failed to move {project_dir} out of trash: {e}")
        return False, f"Failed to move files back: {e}"

    metadata = _read_project_metadata(target_path)
    project_type = "youtube" if metadata.get("url") else "document"
    title = metadata.get("title") or metadata.get("content_title") or project_dir
    content_title = metadata.get("content_title") or metadata.get("transcript_title") or ""
    source = metadata.get("url") or metadata.get("filename") or ""
    created_at = metadata.get("created_at") or metadata.get("timestamp") or datetime.now().isoformat()
    word_count = int(metadata.get("word_count", 0) or 0)
    segment_count = int(metadata.get("segment_count", 0) or 0)
    notes = metadata.get("notes", "")
    tags = metadata.get("tags") if isinstance(metadata.get("tags"), list) else []

    transcript_text = _safe_read_text_file(target_path / "transcript.txt")
    summary_text = _safe_read_text_file(target_path / "summary.txt")
    key_factors_text = _safe_read_text_file(target_path / "key_factors.txt")

    try:
        from database import Project
        project = Project(
            type=project_type,
            title=title,
            content_title=content_title,
            source=source,
            created_at=created_at,
            word_count=word_count,
            segment_count=segment_count,
            project_dir=project_dir,
            notes=notes,
            tags=tags
        )
        db_manager.insert_project(project, transcript=transcript_text, summary=summary_text, key_factors=key_factors_text)
    except Exception as e:
        logger.error(f"Failed to restore database entry for {project_dir}: {e}")
        try:
            trash_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target_path), str(trash_path))
        except Exception as move_back_err:
            logger.error(f"Failed to move {project_dir} back to trash after DB failure: {move_back_err}")
        return False, f"Failed to restore project in database: {e}"

    _append_deletion_log({
        "action": "restore",
        "project_dir": project_dir,
        "message": "Project restored from trash."
    })

    return True, "Project restored successfully."


def update_project_metadata_with_title(project_dir_name: str) -> bool:
    """
    Update project metadata to include titles if missing.
    
    Args:
        project_dir_name: Name of project directory to update
        
    Returns:
        True if update succeeded, False otherwise
    """
    # Validate and sanitize directory name
    is_valid, project_path, error_msg = validate_and_sanitize_path(
        project_dir_name,
        config.output_dir,
        allow_absolute=False
    )
    
    if not is_valid:
        logger.warning(f"Invalid project directory name for update: {project_dir_name} - {error_msg}")
        return False
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
# -----------------------------
# SIDEBAR: NAVIGATION & PROJECT HISTORY
# -----------------------------
with st.sidebar:
    st.header("🧭 Navigation")
    
    st.markdown("Choose a project to review or run a transcript chat.")
    
    # Help button
    if st.button("❓ Help & User Guide", use_container_width=True, help="View complete user guide"):
        st.session_state.show_help = True
    
    st.markdown("---")
    st.header("📁 Project History")
    
    # Quick search in sidebar
    search_query = st.text_input("🔍 Quick search", placeholder="Search projects...", key="sidebar_search")

    projects = []
    try:
        if search_query:
            db_projects = db_manager.list_projects(search_query=search_query, limit=20)
        else:
            db_projects = db_manager.list_projects(limit=20, order_by="created_at", order_desc=True)

        for p in db_projects:
            source = str(p.source) if p.source else ''
            proj_dict = {
                'project_dir': p.project_dir,
                'id': p.id,
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
        projects = list_projects()

    sidebar_query_projects = [p for p in projects if p.get('id')]

    def _sidebar_project_label(project: Dict[str, Any]) -> str:
        base_title = (
            project.get('transcript_title') or
            project.get('content_title') or
            project.get('title') or
            project.get('project_dir') or
            "Untitled"
        )
        icon = "🎥" if project.get('url') else "📄"
        formatted = truncate_title(base_title, max_length=40)
        return f"{icon} {formatted} ({safe_filename(project.get('project_dir', 'project'))})"

    st.markdown("### Sidebar Transcript Query")
    if sidebar_query_projects:
        project_labels = {
            proj['id']: _sidebar_project_label(proj)
            for proj in sidebar_query_projects
        }
        selected_project_id = st.selectbox(
            "Select project for transcript query",
            options=list(project_labels.keys()),
            format_func=lambda pid: project_labels.get(pid, "Unknown Project"),
            key="sidebar_transcript_project_select"
        )
        selected_project = next(
            (proj for proj in sidebar_query_projects if proj['id'] == selected_project_id),
            None
        )

        project_content: Dict[str, Any] = {}
        content_error = ""
        if selected_project:
            try:
                project_content = db_manager.get_project_content(selected_project_id)
            except ProjectNotFoundError:
                content_error = "Project data missing in the database. Please reprocess it."
            except Exception as exc:
                logger.warning(f"Unable to load sidebar transcript content: {exc}")
                content_error = "Unable to load project content right now."

        context_parts = [
            (project_content.get('transcript') or "").strip(),
            (project_content.get('summary') or "").strip(),
            (project_content.get('key_factors') or "").strip()
        ]
        transcript_context = " ".join(part for part in context_parts if part).strip()
        summary_text = project_content.get('summary', '')

        if content_error:
            st.warning(content_error)
        question_key = f"sidebar_transcript_question_{selected_project_id}"
        response_key = f"sidebar_transcript_response_{selected_project_id}"
        st.text_input(
            "Ask a question about the selected project transcript:",
            key=question_key,
            placeholder="e.g., What are the key takeaways?",
            label_visibility="collapsed"
        )

        button_disabled = not bool(transcript_context) or client is None
        if client is None:
            st.caption("OpenAI API key is required to generate answers.")

        if st.button(
            "💬 Run transcript query",
            key=f"sidebar_transcript_btn_{selected_project_id}",
            disabled=button_disabled
        ):
            raw_question = st.session_state.get(question_key, "")
            sanitized_question = sanitize_chat_question(raw_question)
            
            # Check rate limiting
            rate_limit_key = f"sidebar_chat_{selected_project_id}"
            is_allowed, wait_time = check_chat_rate_limit(rate_limit_key, min_seconds=2)
            if not is_allowed:
                st.warning(f"⏳ Please wait {wait_time:.1f} more seconds before asking another question.")
            elif client is None:
                st.error("OpenAI API key is not configured; enable it in .env.")
                record_sidebar_operation(
                    "Transcript Chat",
                    "failed",
                    message="Missing OpenAI API key.",
                    project_dir=selected_project.get('project_dir') if selected_project else None
                )
            elif len(sanitized_question) < config.qa_min_question_length:
                st.warning(f"Please enter at least {config.qa_min_question_length} characters.")
            elif len(sanitized_question) > config.qa_max_question_length:
                st.warning(f"Please limit questions to {config.qa_max_question_length} characters.")
            elif not transcript_context:
                st.warning("Transcript content is not ready yet. Process the project first.")
            else:
                project_title = (
                    selected_project.get('transcript_title') or
                    selected_project.get('content_title') or
                    selected_project.get('title') or
                    selected_project.get('project_dir') or
                    "Project"
                )
                try:
                    with st.spinner("Generating answer..."):
                        answer, tokens_used, cached = answer_question_from_transcript(
                            sanitized_question,
                            transcript_context,
                            project_title,
                            summary=summary_text
                        )
                    st.session_state[response_key] = {
                        "answer": answer,
                        "tokens": tokens_used,
                        "cached": cached,
                        "question": sanitized_question,
                        "timestamp": datetime.now().isoformat()
                    }
                    record_sidebar_operation(
                        "Transcript Chat",
                        "success",
                        message=f"{sanitized_question[:70]}",
                        project_dir=selected_project.get('project_dir')
                    )
                except Exception as exc:
                    logger.exception("Sidebar transcript chat failed", exc_info=exc)
                    st.error("Unable to generate an answer right now. Please try again.")
                    record_sidebar_operation(
                        "Transcript Chat",
                        "failed",
                        message=str(exc),
                        project_dir=selected_project.get('project_dir')
                    )

        response = st.session_state.get(response_key)
        if response:
            st.markdown("**Latest answer**")
            st.write(response.get("answer"))
            meta_parts = []
            if response.get("tokens") is not None:
                meta_parts.append(f"Tokens used: {response['tokens']}")
            if response.get("cached"):
                meta_parts.append("From cache")
            if response.get("timestamp"):
                meta_parts.append(f"Answered: {response['timestamp']}")
            if meta_parts:
                st.caption(" · ".join(meta_parts))
    else:
        st.info("Process a project to enable sidebar transcript queries.")

    if "recent_operations" not in st.session_state:
        st.session_state["recent_operations"] = []

    if st.session_state["recent_operations"]:
        st.caption("📝 Recent Operations")
        for entry in st.session_state["recent_operations"]:
            entry_time = entry.get("timestamp", "")
            try:
                parsed_time = datetime.fromisoformat(entry_time)
                time_label = parsed_time.strftime("%b %d %I:%M %p")
            except Exception:
                time_label = entry_time

            status = entry.get("status", "info").capitalize()
            op_name = entry.get("operation", "Operation")
            project_info = entry.get("project_dir") or ""
            message = entry.get("message", "")
            metadata = f"({project_info})" if project_info else ""
            # Use safe rendering - escape user content to prevent XSS
            safe_message = html.escape(message) if message else ""
            safe_metadata = html.escape(metadata) if metadata else ""
            st.markdown(f"**{time_label}** · {op_name} · {status} {safe_metadata}")
            if safe_message:
                st.caption(safe_message)

    alerts = evaluate_health_alerts(
        config.data_root,
        st.session_state["recent_operations"],
        trash_limit_mb=config.telemetry_trash_warning_mb,
        failure_threshold=config.telemetry_failure_threshold
    )

    for alert in alerts:
        st.warning(alert)

    deleted_project = st.session_state.get("last_deleted_project")
    if deleted_project:
        title = deleted_project.get("title") or deleted_project.get("project_dir")
        deleted_at = deleted_project.get("deleted_at", "Unknown time")
        st.info(f"🗑️ {title} deleted at {deleted_at}")
        if st.button("↩️ Undo last delete", key="undo_last_delete"):
            restored, restore_message = restore_project_from_trash(deleted_project)
            if restored:
                st.success(restore_message)
                record_sidebar_operation(
                    "Restore Project",
                    "success",
                    message=restore_message,
                    project_dir=deleted_project.get("project_dir")
                )
                st.session_state.pop("last_deleted_project", None)
                st.rerun()
            else:
                st.error(restore_message)
                record_sidebar_operation(
                    "Restore Project",
                    "failed",
                    message=restore_message,
                    project_dir=deleted_project.get("project_dir")
                )
    
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
                
                project_content = {'transcript': '', 'summary': '', 'key_factors': ''}
                transcript_text = ""
                project_summary = ""
                key_factors_text = ""
                project_dir_safe = safe_filename(proj.get('project_dir') or f"project_{idx}")
                if proj.get('id'):
                    try:
                        project_content = db_manager.get_project_content(proj['id'])
                    except ProjectNotFoundError:
                        st.warning("Project record missing; transcript chat unavailable.")
                    except Exception as exc:
                        logger.error(f"Failed to load content for {proj.get('project_dir')}: {exc}")
                        st.warning("Unable to load transcript content for this project.")
                project_summary = project_content.get('summary', '') or ''
                key_factors_text = project_content.get('key_factors', '') or ''
                transcript_text = project_content.get('transcript', '') or ''

                if project_summary:
                    st.markdown("**Summary**")
                    st.text_area(
                        f"Summary for {project_name}",
                        value=project_summary,
                        height=120,
                        key=f"summary_{project_dir_safe}_readonly",
                        label_visibility="collapsed",
                        disabled=True
                    )
                else:
                    st.info("Summary not available for this project yet.")

                if key_factors_text:
                    st.markdown("**Key Factors**")
                    st.text_area(
                        f"Key factors for {project_name}",
                        value=key_factors_text,
                        height=140,
                        key=f"key_factors_{project_dir_safe}_readonly",
                        label_visibility="collapsed",
                        disabled=True
                    )
                else:
                    st.info("Key factors not available for this project yet.")

                project_chat_key = str(proj.get('id') or safe_filename(proj['project_dir']))
                question_key = f"project_chat_question_{project_chat_key}"
                response_key = f"project_chat_response_{project_chat_key}"
                transcript_context = transcript_text.strip() or project_summary.strip() or key_factors_text.strip()
                st.markdown("---")
                st.write("**Chat with this transcript**")
                if not transcript_context:
                    st.warning("Transcript content is not ready yet. Please process the project fully first.")
                question = st.text_input(
                    "Ask a question about this project:",
                    key=question_key,
                    placeholder="e.g., What are the main takeaways?",
                    help="Answers are generated by the transcript/summary/key factors.",
                    label_visibility="collapsed"
                )
                button_disabled = not bool(transcript_context)
                if st.button("💬 Run transcript chat", key=f"project_chat_btn_{project_chat_key}", disabled=button_disabled):
                    raw_question = st.session_state.get(question_key, "")
                    sanitized_question = sanitize_chat_question(raw_question)
                    
                    # Check rate limiting
                    is_allowed, wait_time = check_chat_rate_limit(project_chat_key, min_seconds=2)
                    if not is_allowed:
                        st.warning(f"⏳ Please wait {wait_time:.1f} more seconds before asking another question.")
                    elif len(sanitized_question) < config.qa_min_question_length:
                        st.warning(f"Please enter at least {config.qa_min_question_length} characters.")
                    elif len(sanitized_question) > config.qa_max_question_length:
                        st.warning(f"Please limit questions to {config.qa_max_question_length} characters.")
                    elif client is None:
                        st.error("OpenAI API key is not configured; enable it in .env to use transcript chat.")
                        record_sidebar_operation(
                            "Transcript Chat",
                            "failed",
                            message="Missing OpenAI API key.",
                            project_dir=proj.get('project_dir')
                        )
                    else:
                        try:
                            with st.spinner("Generating answer..."):
                                answer, tokens_used, cached = answer_question_from_transcript(
                                    sanitized_question,
                                    transcript_context,
                                    project_name or proj.get('title') or proj.get('project_dir'),
                                    summary=project_summary
                                )
                            st.session_state[response_key] = {
                                "answer": answer,
                                "tokens": tokens_used,
                                "cached": cached,
                                "question": sanitized_question,
                                "timestamp": datetime.now().isoformat()
                            }
                            record_sidebar_operation(
                                "Transcript Chat",
                                "success",
                                message=f"{sanitized_question[:70]}",
                                project_dir=proj.get('project_dir')
                            )
                        except Exception as exc:
                            logger.exception("Transcript chat failed", exc_info=exc)
                            st.error("Unable to generate an answer right now. Please try again.")
                            record_sidebar_operation(
                                "Transcript Chat",
                                "failed",
                                message=str(exc),
                                project_dir=proj.get('project_dir')
                            )

                response = st.session_state.get(response_key)
                if response:
                    st.markdown("**Latest answer**")
                    st.write(response.get("answer"))
                    meta_parts = []
                    if response.get("tokens") is not None:
                        meta_parts.append(f"Tokens used: {response['tokens']}")
                    if response.get("cached"):
                        meta_parts.append("From cache")
                    if response.get("timestamp"):
                        meta_parts.append(f"Answered: {response['timestamp']}")
                    if meta_parts:
                        st.caption(" · ".join(meta_parts))
                st.markdown("---")

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
                            deletion_result = delete_project(proj['project_dir'])
                            if deletion_result.success:
                                st.success(deletion_result.message or "Deleted!")
                                record_sidebar_operation(
                                    "Delete Project",
                                    "success",
                                    message=deletion_result.message or "Deleted project.",
                                    project_dir=proj['project_dir']
                                )
                                st.session_state["last_deleted_project"] = {
                                    "project_dir": proj['project_dir'],
                                    "title": deletion_result.metadata.get("title") or proj.get("title") or proj['project_dir'],
                                    "trash_path": str(deletion_result.trash_path) if deletion_result.trash_path else "",
                                    "deleted_at": datetime.now().isoformat(),
                                    "message": deletion_result.message,
                                    "disk_removed": deletion_result.disk_removed,
                                    "db_removed": deletion_result.db_deleted
                                }
                            else:
                                st.error(deletion_result.message or "Failed to delete project.")
                                record_sidebar_operation(
                                    "Delete Project",
                                    "failed",
                                    message=deletion_result.message or "Delete project failed.",
                                    project_dir=proj['project_dir']
                                )
                            st.session_state[delete_key] = False
                            st.rerun()
                
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
                    result = delete_project(proj['project_dir'])
                    if result.success:
                        deleted_count += 1
                st.success(f"Deleted {deleted_count} project(s)!")
                record_sidebar_operation(
                    "Delete All Projects",
                    "success",
                    message=f"Deleted {deleted_count} project(s)."
                )
                st.session_state[confirm_all_key] = False
                st.rerun()
    else:
        st.info("No projects yet.\n\nProcess a video or document to get started!")

# -----------------------------
# HELP MODAL
# -----------------------------
if 'show_help' not in st.session_state:
    st.session_state.show_help = False

if st.session_state.show_help:
    # Display help guide in a modal-like container
    with st.container():
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 8, 1])
        with col3:
            if st.button("✖ Close", key="close_help"):
                st.session_state.show_help = False
                st.rerun()
        
        with col2:
            # Read and display the user guide
            try:
                user_guide_path = Path(__file__).parent / "USER_GUIDE.md"
                if user_guide_path.exists():
                    with open(user_guide_path, 'r', encoding='utf-8') as f:
                        user_guide_content = f.read()
                    st.markdown(user_guide_content)
                else:
                    st.error("User guide file not found. Please check USER_GUIDE.md exists.")
            except Exception as e:
                st.error(f"Error loading user guide: {e}")
        
        st.markdown("---")
        if st.button("✖ Close Help", key="close_help_bottom", use_container_width=True):
            st.session_state.show_help = False
            st.rerun()
    
    st.stop()  # Don't show main content when help is displayed

# -----------------------------
# PAGE ROUTING
# -----------------------------
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
        
        record_sidebar_operation(
            "Process Video",
            "started",
            message=f"URL: {sanitize_url_for_log(url)}"
        )
        
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
            metadata_summary = results.get("metadata", {})
            summary_title = metadata_summary.get("title") or metadata_summary.get("transcript_title") or session_dir.name
            summary_words = metadata_summary.get("word_count") or len(results.get("full_text", "").split())
            record_sidebar_operation(
                "Process Video",
                "success",
                message=f"{summary_title} ({summary_words:,} words)",
                project_dir=session_dir.name
            )

        except AudioDownloadError as e:
            record_sidebar_operation(
                "Process Video",
                "failed",
                message=f"{type(e).__name__}: {e}"
            )
            st.error(f"❌ **Download Failed**")
            st.error(str(e))
            st.info("**Suggestions:**\n"
                   "- Verify the video is public and available\n"
                   "- Check if the video is available in your region\n"
                   "- Try a different video URL")
            logger.error(f"Audio download error: {e}")
            
        except FileSizeError as e:
            record_sidebar_operation(
                "Process Video",
                "failed",
                message=f"{type(e).__name__}: {e}"
            )
            st.error(f"❌ **File Too Large**")
            st.error(str(e))
            st.info("**Suggestions:**\n"
                   "- Try a shorter video (under 30 minutes)\n"
                   "- Lower the audio quality in your .env file (AUDIO_QUALITY=64)\n"
                   "- The Whisper API has a 25MB file size limit")
            logger.error(f"File size error: {e}")
            
        except TranscriptionError as e:
            record_sidebar_operation(
                "Process Video",
                "failed",
                message=f"{type(e).__name__}: {e}"
            )
            st.error(f"❌ **Transcription Failed**")
            st.error(str(e))
            st.info("**Suggestions:**\n"
                   "- Check that your OpenAI API key is valid\n"
                   "- Ensure you have API credits available\n"
                   "- Visit: https://platform.openai.com/usage")
            logger.error(f"Transcription error: {e}")
            
        except APIQuotaError as e:
            record_sidebar_operation(
                "Process Video",
                "failed",
                message=f"{type(e).__name__}: {e}"
            )
            st.error(f"❌ **API Quota Exceeded**")
            st.error(str(e))
            st.warning("**What to do:**\n"
                      "1. Check your OpenAI usage dashboard\n"
                      "2. Add credits or upgrade your plan\n"
                      "3. Wait for your rate limit to reset\n"
                      "4. Visit: https://platform.openai.com/usage")
            logger.error(f"API quota error: {e}")
            
        except APIConnectionError as e:
            record_sidebar_operation(
                "Process Video",
                "failed",
                message=f"{type(e).__name__}: {e}"
            )
            st.error(f"❌ **Connection Failed**")
            st.error(str(e))
            st.info("**Suggestions:**\n"
                   "- Check your internet connection\n"
                   "- Verify OpenAI services are operational\n"
                   "- Check: https://status.openai.com/\n"
                   "- Try again in a few moments")
            logger.error(f"API connection error: {e}")
            
        except Exception as e:
            record_sidebar_operation(
                "Process Video",
                "failed",
                message=f"{type(e).__name__}: {e}"
            )
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
        
        # Validate file content and security
        is_valid, validation_error = validate_uploaded_file(uploaded_file)
        if not is_valid:
            st.error(f"❌ **File Validation Failed**")
            st.error(validation_error)
            st.info("**Suggestions:**\n"
                   "- Ensure the file is a valid PDF, DOCX, or TXT file\n"
                   "- Check that the file is not corrupted\n"
                   "- Verify the file extension matches the actual file type\n"
                   "- Avoid special characters in the filename")
            logger.warning(f"File upload rejected: {validation_error} - {sanitize_url_for_log(uploaded_file.name)}")
            st.stop()
        
        record_sidebar_operation(
            "Process Document",
            "started",
            message=f"{uploaded_file.name}",
        )
        
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
            record_sidebar_operation(
                "Process Document",
                "success",
                message=f"{uploaded_file.name}",
            )
        
        except DocumentProcessingError as e:
            record_sidebar_operation(
                "Process Document",
                "failed",
                message=f"{type(e).__name__}: {e}"
            )
            st.error(f"❌ **Document Processing Failed**")
            st.error(str(e))
            st.info("**Suggestions:**\n"
                   "- Ensure the document is not corrupted\n"
                   "- Try converting to a different format (PDF, DOCX, or TXT)\n"
                   "- Check that the file contains readable text\n"
                   "- Verify the file is not password-protected")
            logger.error(f"Document processing error: {e}")
            
        except APIQuotaError as e:
            record_sidebar_operation(
                "Process Document",
                "failed",
                message=f"{type(e).__name__}: {e}"
            )
            st.error(f"❌ **API Quota Exceeded**")
            st.error(str(e))
            st.warning("**What to do:**\n"
                      "1. Check your OpenAI usage dashboard\n"
                      "2. Add credits or upgrade your plan\n"
                      "3. Wait for your rate limit to reset\n"
                      "4. Visit: https://platform.openai.com/usage")
            logger.error(f"API quota error: {e}")
            
        except APIConnectionError as e:
            record_sidebar_operation(
                "Process Document",
                "failed",
                message=f"{type(e).__name__}: {e}"
            )
            st.error(f"❌ **Connection Failed**")
            st.error(str(e))
            st.info("**Suggestions:**\n"
                   "- Check your internet connection\n"
                   "- Verify OpenAI services are operational\n"
                   "- Check: https://status.openai.com/\n"
                   "- Try again in a few moments")
            logger.error(f"API connection error: {e}")
            
        except Exception as e:
            record_sidebar_operation(
                "Process Document",
                "failed",
                message=f"{type(e).__name__}: {e}"
            )
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