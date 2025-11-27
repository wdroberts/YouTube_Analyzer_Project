"""
Tests for utility functions in app.py.py

Tests cover:
- Filename sanitization
- URL validation and parsing
- Timestamp formatting
- Text truncation
- SRT conversion
"""
import pytest
from pathlib import Path
import sys
import os

# Add parent directory to path to import app module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import functions to test - use try/except to handle import variations
try:
    from app import (
        safe_filename,
        validate_youtube_url,
        extract_video_id,
        format_timestamp,
        format_url_for_display,
        truncate_title,
        to_srt
    )
except ImportError:
    # If module name is different, try alternative
    import importlib.util
    spec = importlib.util.spec_from_file_location("app", "app.py.py")
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    
    safe_filename = app.safe_filename
    validate_youtube_url = app.validate_youtube_url
    extract_video_id = app.extract_video_id
    format_timestamp = app.format_timestamp
    format_url_for_display = app.format_url_for_display
    truncate_title = app.truncate_title
    to_srt = app.to_srt


class TestSafeFilename:
    """Test filename sanitization function."""
    
    def test_simple_text(self):
        """Test simple alphanumeric text remains unchanged."""
        assert safe_filename("hello123") == "hello123"
        assert safe_filename("test_file") == "test_file"
        assert safe_filename("video-2024") == "video-2024"
    
    def test_special_characters(self):
        """Test special characters are replaced with underscores."""
        assert safe_filename("hello world!") == "hello_world_"
        assert safe_filename("test@#$%file") == "test_file"
        assert safe_filename("file:name*here?") == "file_name_here_"
    
    def test_spaces(self):
        """Test spaces are replaced."""
        assert safe_filename("my video file") == "my_video_file"
        assert safe_filename("  multiple   spaces  ") == "__multiple___spaces__"
    
    def test_empty_string(self):
        """Test empty string handling."""
        assert safe_filename("") == ""
    
    def test_unicode_characters(self):
        """Test unicode characters are replaced."""
        assert safe_filename("café") == "caf_"
        assert safe_filename("测试") == "__"


class TestValidateYoutubeUrl:
    """Test YouTube URL validation with enhanced security checks."""
    
    # Valid 11-character YouTube video IDs for testing
    VALID_VIDEO_ID = "dQw4w9WgXcQ"  # Standard format
    VALID_SHORT_ID = "abc123xyz45"  # Alphanumeric
    
    def test_valid_youtube_urls(self):
        """Test valid YouTube URLs with proper video IDs return True."""
        assert validate_youtube_url(f"https://www.youtube.com/watch?v={self.VALID_VIDEO_ID}") is True
        assert validate_youtube_url(f"https://youtube.com/watch?v={self.VALID_SHORT_ID}") is True
        assert validate_youtube_url(f"https://www.youtube.com/watch?v={self.VALID_VIDEO_ID}&t=10s") is True
    
    def test_valid_youtu_be_urls(self):
        """Test valid youtu.be short URLs return True."""
        assert validate_youtube_url(f"https://youtu.be/{self.VALID_VIDEO_ID}") is True
        assert validate_youtube_url(f"https://youtu.be/{self.VALID_SHORT_ID}?t=30") is True
    
    def test_valid_youtube_shorts(self):
        """Test valid YouTube Shorts URLs return True."""
        assert validate_youtube_url(f"https://www.youtube.com/shorts/{self.VALID_VIDEO_ID}") is True
        assert validate_youtube_url(f"https://youtube.com/shorts/{self.VALID_SHORT_ID}") is True
    
    def test_valid_mobile_urls(self):
        """Test valid mobile YouTube URLs return True."""
        assert validate_youtube_url(f"https://m.youtube.com/watch?v={self.VALID_VIDEO_ID}") is True
    
    def test_invalid_urls(self):
        """Test non-YouTube URLs return False."""
        assert validate_youtube_url("https://vimeo.com/123456") is False
        assert validate_youtube_url("https://dailymotion.com/video/x123") is False
        assert validate_youtube_url("https://google.com") is False
        assert validate_youtube_url("not a url") is False
    
    def test_empty_string(self):
        """Test empty string returns False."""
        assert validate_youtube_url("") is False
        assert validate_youtube_url(None) is False
    
    def test_malformed_urls(self):
        """Test malformed URLs return False."""
        assert validate_youtube_url("htp://broken") is False
        assert validate_youtube_url("youtube.com") is False  # Missing protocol
    
    def test_invalid_video_id_length(self):
        """Test URLs with invalid video ID lengths are rejected."""
        assert validate_youtube_url("https://youtube.com/watch?v=short") is False  # Too short
        assert validate_youtube_url("https://youtube.com/watch?v=waytoolongvideoid") is False  # Too long
        assert validate_youtube_url("https://youtube.com/watch?v=abc123") is False  # 6 chars, need 11
    
    def test_missing_video_id(self):
        """Test URLs without video IDs are rejected."""
        assert validate_youtube_url("https://youtube.com/watch") is False
        assert validate_youtube_url("https://youtube.com/") is False
        assert validate_youtube_url("https://youtu.be/") is False
    
    def test_suspicious_schemes(self):
        """Test suspicious URL schemes are rejected."""
        assert validate_youtube_url("javascript:alert('xss')") is False
        assert validate_youtube_url("data:text/html,<script>alert('xss')</script>") is False
        assert validate_youtube_url("vbscript:msgbox('xss')") is False
        assert validate_youtube_url("file:///etc/passwd") is False
    
    def test_invalid_protocols(self):
        """Test non-HTTP(S) protocols are rejected."""
        assert validate_youtube_url("ftp://youtube.com/watch?v=abc123xyz45") is False
        assert validate_youtube_url("mailto:test@example.com") is False
    
    def test_suspicious_parameters(self):
        """Test URLs with suspicious query parameters are rejected."""
        assert validate_youtube_url(f"https://youtube.com/watch?v={self.VALID_VIDEO_ID}&javascript=alert(1)") is False
        assert validate_youtube_url(f"https://youtube.com/watch?v={self.VALID_VIDEO_ID}&onclick=evil()") is False
        assert validate_youtube_url(f"https://youtube.com/watch?v={self.VALID_VIDEO_ID}&eval=code") is False
    
    def test_valid_with_safe_parameters(self):
        """Test URLs with safe parameters are still accepted."""
        assert validate_youtube_url(f"https://youtube.com/watch?v={self.VALID_VIDEO_ID}&t=10s") is True
        assert validate_youtube_url(f"https://youtube.com/watch?v={self.VALID_VIDEO_ID}&feature=share") is True
        assert validate_youtube_url(f"https://youtube.com/watch?v={self.VALID_VIDEO_ID}&list=PLxxx") is True


class TestExtractVideoId:
    """Test video ID extraction from various URL formats."""
    
    def test_standard_youtube_url(self):
        """Test extraction from standard YouTube URLs."""
        assert extract_video_id("https://www.youtube.com/watch?v=abc123") == "abc123"
        assert extract_video_id("https://youtube.com/watch?v=xyz789") == "xyz789"
    
    def test_youtube_url_with_parameters(self):
        """Test extraction from URLs with additional parameters."""
        assert extract_video_id("https://youtube.com/watch?v=abc123&t=10s") == "abc123"
        assert extract_video_id("https://youtube.com/watch?v=xyz&feature=share") == "xyz"
    
    def test_youtu_be_short_url(self):
        """Test extraction from youtu.be short URLs."""
        assert extract_video_id("https://youtu.be/abc123") == "abc123"
        assert extract_video_id("https://youtu.be/xyz789?t=30") == "xyz789"
    
    def test_youtube_shorts(self):
        """Test extraction from YouTube Shorts URLs."""
        assert extract_video_id("https://www.youtube.com/shorts/abc123") == "abc123"
        assert extract_video_id("https://youtube.com/shorts/xyz789") == "xyz789"
    
    def test_invalid_urls(self):
        """Test invalid URLs return empty string."""
        assert extract_video_id("https://vimeo.com/123") == ""
        assert extract_video_id("not a url") == ""
        assert extract_video_id("") == ""


class TestFormatTimestamp:
    """Test timestamp formatting function."""
    
    def test_zero_seconds(self):
        """Test zero seconds formatting."""
        assert format_timestamp(0) == "00:00:00.000"
    
    def test_seconds_only(self):
        """Test formatting with seconds only."""
        assert format_timestamp(45.5) == "00:00:45.500"
        assert format_timestamp(5.123) == "00:00:05.123"
    
    def test_minutes_and_seconds(self):
        """Test formatting with minutes and seconds."""
        assert format_timestamp(90) == "00:01:30.000"
        assert format_timestamp(125.750) == "00:02:05.750"
    
    def test_hours_minutes_seconds(self):
        """Test formatting with hours, minutes, and seconds."""
        assert format_timestamp(3661) == "01:01:01.000"
        assert format_timestamp(7265.5) == "02:01:05.500"
    
    def test_large_values(self):
        """Test formatting with large time values."""
        assert format_timestamp(10000) == "02:46:40.000"


class TestFormatUrlForDisplay:
    """Test URL formatting for display."""
    
    def test_short_url(self):
        """Test short URLs remain unchanged."""
        url = "https://youtube.com/watch?v=abc"
        assert format_url_for_display(url, max_length=50) == url
    
    def test_long_url_truncation(self):
        """Test long URLs are truncated."""
        url = "https://www.youtube.com/watch?v=abc123&feature=share&t=100"
        result = format_url_for_display(url, max_length=30)
        assert len(result) == 33  # 30 + "..."
        assert result.endswith("...")
    
    def test_exact_length(self):
        """Test URL at exact max length."""
        url = "https://youtube.com/abc"  # 24 chars
        result = format_url_for_display(url, max_length=24)
        assert result == url


class TestTruncateTitle:
    """Test title truncation function."""
    
    def test_short_title(self):
        """Test short titles remain unchanged."""
        title = "Short Title"
        assert truncate_title(title, max_length=30) == title
    
    def test_long_title_truncation(self):
        """Test long titles are truncated with ellipsis."""
        title = "This is a very long title that needs to be truncated"
        result = truncate_title(title, max_length=20)
        assert len(result) == 20
        assert result.endswith("...")
        assert result == "This is a very lo..."
    
    def test_exact_length(self):
        """Test title at exact max length."""
        title = "Exactly Twenty Chars"  # 20 chars
        assert truncate_title(title, max_length=20) == title
    
    def test_empty_title(self):
        """Test empty title handling."""
        assert truncate_title("", max_length=10) == ""


class TestToSrt:
    """Test SRT subtitle format conversion."""
    
    def test_single_segment(self):
        """Test conversion of single segment."""
        segments = [
            {"start": 0.0, "end": 2.5, "text": "Hello world"}
        ]
        result = to_srt(segments)
        assert "1" in result
        assert "00:00:00,000 --> 00:00:02,500" in result
        assert "Hello world" in result
    
    def test_multiple_segments(self):
        """Test conversion of multiple segments."""
        segments = [
            {"start": 0.0, "end": 2.5, "text": "First segment"},
            {"start": 2.5, "end": 5.0, "text": "Second segment"},
        ]
        result = to_srt(segments)
        assert "1" in result
        assert "2" in result
        assert "First segment" in result
        assert "Second segment" in result
    
    def test_timestamp_format(self):
        """Test SRT timestamp format uses commas."""
        segments = [
            {"start": 1.5, "end": 3.0, "text": "Test"}
        ]
        result = to_srt(segments)
        # SRT format uses comma for milliseconds
        assert "00:00:01,500" in result
        assert "00:00:03,000" in result
    
    def test_empty_segments(self):
        """Test handling of empty segments list."""
        result = to_srt([])
        assert result == ""
    
    def test_text_stripping(self):
        """Test that text is stripped of whitespace."""
        segments = [
            {"start": 0.0, "end": 1.0, "text": "  Text with spaces  "}
        ]
        result = to_srt(segments)
        assert "Text with spaces" in result
        assert "  Text with spaces  " not in result


# Run with: pytest tests/test_utilities.py -v
# Coverage: pytest tests/test_utilities.py --cov=app --cov-report=html

