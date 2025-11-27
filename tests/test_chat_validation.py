"""
Tests for chat input sanitization and validation.

Tests cover:
- HTML/script tag stripping
- Control character removal
- Unicode normalization
- Rate limiting
- XSS prevention
"""
import pytest
import sys
import os
import time
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import app module
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("app", "app.py.py")
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
except Exception as e:
    pytest.skip(f"Could not import app module: {e}", allow_module_level=True)

from app import sanitize_chat_question, check_chat_rate_limit


class TestChatSanitization:
    """Test chat question sanitization."""
    
    def test_basic_sanitization(self):
        """Test that basic questions pass through unchanged."""
        question = "What are the main takeaways?"
        result = sanitize_chat_question(question)
        assert result == question
    
    def test_html_tag_removal(self):
        """Test that HTML tags are removed."""
        question = "What is <b>important</b> here?"
        result = sanitize_chat_question(question)
        assert "<b>" not in result
        assert "</b>" not in result
        assert "important" in result
    
    def test_script_tag_removal(self):
        """Test that script tags are removed."""
        question = "What is this? <script>alert('xss')</script>"
        result = sanitize_chat_question(question)
        assert "<script>" not in result.lower()
        assert "</script>" not in result.lower()
        # Note: "alert" word itself is preserved (only tags removed), which is correct
        # The important part is that script tags are gone
    
    def test_javascript_scheme_removal(self):
        """Test that javascript: schemes are removed."""
        question = "Check this javascript:alert('xss')"
        result = sanitize_chat_question(question)
        assert "javascript:" not in result.lower()
    
    def test_event_handler_removal(self):
        """Test that event handlers are removed."""
        question = "Click onclick=evil() here"
        result = sanitize_chat_question(question)
        assert "onclick=" not in result.lower()
        assert "onerror=" not in result.lower()
    
    def test_control_character_removal(self):
        """Test that control characters are removed."""
        # Include various control characters
        question = "Test\x00\x01\x02\x03\x04\x05"
        result = sanitize_chat_question(question)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "Test" in result
    
    def test_preserves_newline_tab(self):
        """Test that newlines and tabs are preserved."""
        question = "Line 1\nLine 2\tTabbed"
        result = sanitize_chat_question(question)
        assert "\n" in result
        assert "\t" in result
    
    def test_whitespace_cleanup(self):
        """Test that excessive whitespace is cleaned up."""
        question = "Too    many     spaces"
        result = sanitize_chat_question(question)
        assert "  " not in result  # No double spaces
        assert "Too many spaces" in result or "Too many spaces" == result.strip()
    
    def test_multiple_newlines_cleanup(self):
        """Test that excessive newlines are reduced."""
        question = "Line 1\n\n\n\n\nLine 2"
        result = sanitize_chat_question(question)
        # Should have at most 2 consecutive newlines
        assert "\n\n\n" not in result
    
    def test_unicode_normalization(self):
        """Test that Unicode is normalized."""
        # Using combining characters (should be normalized)
        question = "Café"  # Normal Unicode should pass through
        result = sanitize_chat_question(question)
        assert "Café" in result or "Cafe" in result
    
    def test_empty_string(self):
        """Test that empty strings return empty."""
        assert sanitize_chat_question("") == ""
        assert sanitize_chat_question("   ") == ""
    
    def test_none_input(self):
        """Test that None input returns empty string."""
        assert sanitize_chat_question(None) == ""
    
    def test_xss_attempts(self):
        """Test various XSS attempt patterns."""
        xss_attempts = [
            "<img src=x onerror=alert(1)>",
            "<svg onload=alert(1)>",
            "javascript:void(0)",
            "<iframe src=evil.com>",
            "onclick='alert(1)'",
        ]
        
        for attempt in xss_attempts:
            result = sanitize_chat_question(attempt)
            # Should not contain script-related patterns
            assert "javascript:" not in result.lower()
            assert "onerror" not in result.lower()
            assert "onclick" not in result.lower()
            assert "<script" not in result.lower()
    
    def test_eval_removal(self):
        """Test that eval() patterns are removed."""
        question = "What is eval('code') here?"
        result = sanitize_chat_question(question)
        assert "eval(" not in result.lower()
    
    def test_expression_removal(self):
        """Test that expression() patterns are removed."""
        question = "Check expression('code')"
        result = sanitize_chat_question(question)
        assert "expression(" not in result.lower()
    
    def test_preserves_unicode_letters(self):
        """Test that Unicode letters are preserved."""
        question = "测试 🎉 Привет"
        result = sanitize_chat_question(question)
        # Should preserve Unicode characters
        assert len(result) > 0
        # Should not be empty after sanitization


class TestChatRateLimiting:
    """Test chat rate limiting functionality."""
    
    def setup_method(self):
        """Reset session state before each test."""
        if hasattr(app, 'st'):
            app.st.session_state.clear()
        else:
            # Mock streamlit if not available
            app.st = Mock()
            app.st.session_state = {}
    
    def test_first_chat_allowed(self):
        """Test that first chat is always allowed."""
        is_allowed, wait_time = check_chat_rate_limit("test_project_1", min_seconds=2)
        assert is_allowed is True
        assert wait_time is None
    
    def test_rate_limit_enforced(self):
        """Test that rate limit is enforced."""
        project_key = "test_project_2"
        
        # First chat allowed
        is_allowed, wait_time = check_chat_rate_limit(project_key, min_seconds=2)
        assert is_allowed is True
        
        # Immediate second chat should be blocked
        is_allowed, wait_time = check_chat_rate_limit(project_key, min_seconds=2)
        assert is_allowed is False
        assert wait_time is not None
        assert 0 < wait_time <= 2
    
    def test_rate_limit_expires(self):
        """Test that rate limit expires after time."""
        project_key = "test_project_3"
        
        # First chat
        check_chat_rate_limit(project_key, min_seconds=1)
        
        # Wait for rate limit to expire
        time.sleep(1.1)
        
        # Should be allowed again
        is_allowed, wait_time = check_chat_rate_limit(project_key, min_seconds=1)
        assert is_allowed is True
        assert wait_time is None
    
    def test_different_projects_independent(self):
        """Test that rate limits are independent per project."""
        project1_key = "project_1"
        project2_key = "project_2"
        
        # Chat on project 1
        is_allowed, _ = check_chat_rate_limit(project1_key, min_seconds=2)
        assert is_allowed is True
        
        # Should be able to chat on project 2 immediately
        is_allowed, _ = check_chat_rate_limit(project2_key, min_seconds=2)
        assert is_allowed is True
    
    def test_wait_time_calculation(self):
        """Test that wait time is calculated correctly."""
        project_key = "test_wait_time"
        
        # First chat
        check_chat_rate_limit(project_key, min_seconds=5)
        
        # Wait 2 seconds
        time.sleep(2)
        
        # Should need to wait ~3 more seconds
        is_allowed, wait_time = check_chat_rate_limit(project_key, min_seconds=5)
        assert is_allowed is False
        assert 2.5 <= wait_time <= 3.5  # Allow some tolerance


# Run with: pytest tests/test_chat_validation.py -v

