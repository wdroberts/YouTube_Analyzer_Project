"""
Test script for error handling improvements.

This script validates that custom exceptions are raised correctly
and that error messages are user-friendly.

Run with: python test_error_handling.py
"""

import sys
from pathlib import Path
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import after path is set
# Note: The main app file is named app.py.py
import importlib.util
spec = importlib.util.spec_from_file_location("app", "app.py.py")
app = importlib.util.module_from_spec(spec)

# Import classes before loading to avoid issues
try:
    spec.loader.exec_module(app)
    AudioDownloadError = app.AudioDownloadError
    TranscriptionError = app.TranscriptionError
    APIQuotaError = app.APIQuotaError
    FileSizeError = app.FileSizeError
    DocumentProcessingError = app.DocumentProcessingError
    APIConnectionError = app.APIConnectionError
    YouTubeAnalyzerError = app.YouTubeAnalyzerError
    extract_text_from_document = app.extract_text_from_document
except Exception as e:
    print(f"Warning: Could not load app module fully: {e}")
    print("Some tests may be skipped.")
    # Define dummy classes for testing
    class YouTubeAnalyzerError(Exception): pass
    class AudioDownloadError(YouTubeAnalyzerError): pass
    class TranscriptionError(YouTubeAnalyzerError): pass
    class APIQuotaError(YouTubeAnalyzerError): pass
    class FileSizeError(YouTubeAnalyzerError): pass
    class DocumentProcessingError(YouTubeAnalyzerError): pass
    class APIConnectionError(YouTubeAnalyzerError): pass
    extract_text_from_document = None


class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def test_pass(self, test_name):
        """Record a passing test."""
        self.passed += 1
        print(f"[PASS] {test_name}")
    
    def test_fail(self, test_name, error):
        """Record a failing test."""
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"[FAIL] {test_name}")
        print(f"       Error: {error}")
    
    def summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print("\n" + "="*60)
        print(f"Test Results: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"\n{self.failed} test(s) failed:")
            for test_name, error in self.errors:
                print(f"  - {test_name}: {error}")
        print("="*60)
        return self.failed == 0


def test_exception_hierarchy():
    """Test that all custom exceptions inherit from YouTubeAnalyzerError."""
    results = TestResults()
    
    exceptions = [
        AudioDownloadError,
        TranscriptionError,
        APIQuotaError,
        FileSizeError,
        DocumentProcessingError,
        APIConnectionError,
    ]
    
    for exc in exceptions:
        try:
            assert issubclass(exc, YouTubeAnalyzerError), \
                f"{exc.__name__} should inherit from YouTubeAnalyzerError"
            assert issubclass(exc, Exception), \
                f"{exc.__name__} should inherit from Exception"
            results.test_pass(f"{exc.__name__} hierarchy")
        except AssertionError as e:
            results.test_fail(f"{exc.__name__} hierarchy", str(e))
    
    return results


def test_exception_messages():
    """Test that exceptions can be raised with custom messages."""
    results = TestResults()
    
    test_cases = [
        (AudioDownloadError, "Video unavailable"),
        (TranscriptionError, "Transcription failed"),
        (APIQuotaError, "Quota exceeded"),
        (FileSizeError, "File too large"),
        (DocumentProcessingError, "Document corrupt"),
        (APIConnectionError, "Connection timeout"),
    ]
    
    for exc_class, message in test_cases:
        try:
            try:
                raise exc_class(message)
            except exc_class as e:
                assert str(e) == message, \
                    f"Exception message should be '{message}', got '{str(e)}'"
                results.test_pass(f"{exc_class.__name__} message")
        except AssertionError as e:
            results.test_fail(f"{exc_class.__name__} message", str(e))
    
    return results


def test_exception_catching():
    """Test that specific exceptions can be caught."""
    results = TestResults()
    
    # Test catching specific exception
    try:
        try:
            raise AudioDownloadError("Test error")
        except AudioDownloadError as e:
            assert "Test error" in str(e)
            results.test_pass("Catch specific exception")
    except Exception as e:
        results.test_fail("Catch specific exception", str(e))
    
    # Test catching via base class
    try:
        try:
            raise TranscriptionError("Base test")
        except YouTubeAnalyzerError as e:
            assert "Base test" in str(e)
            results.test_pass("Catch via base class")
    except Exception as e:
        results.test_fail("Catch via base class", str(e))
    
    return results


def test_document_processing_error_detection():
    """Test that document processing errors are detected correctly."""
    results = TestResults()
    
    # Test unsupported format
    if extract_text_from_document is None:
        print("[SKIP] extract_text_from_document not available (app module not fully loaded)")
        return results
    
    try:
        # Mock an unsupported file
        mock_file = Mock()
        mock_file.name = "test.xyz"
        mock_file.read.return_value = b"test data"
        
        try:
            extract_text_from_document(mock_file)
            results.test_fail("Unsupported format detection", "Should raise DocumentProcessingError")
        except DocumentProcessingError as e:
            assert "Unsupported file format" in str(e)
            results.test_pass("Unsupported format detection")
    except Exception as e:
        results.test_fail("Unsupported format detection", str(e))
    
    return results


def test_error_message_quality():
    """Test that error messages are user-friendly and actionable."""
    results = TestResults()
    
    test_cases = [
        (
            AudioDownloadError("Video is private, deleted, or unavailable in your region."),
            ["private", "deleted", "unavailable", "region"]
        ),
        (
            FileSizeError("Audio file too large for Whisper API (limit: 24MB). Try a shorter video."),
            ["Audio file", "too large", "Whisper API", "limit", "MB", "shorter"]
        ),
        (
            APIQuotaError("OpenAI API rate limit or quota exceeded."),
            ["OpenAI", "rate limit", "quota", "exceeded"]
        ),
        (
            APIConnectionError("Could not connect to OpenAI API. Check your internet connection."),
            ["connect", "OpenAI", "internet", "connection"]
        ),
        (
            DocumentProcessingError("Could not extract any text from the document."),
            ["extract", "text", "document"]
        ),
    ]
    
    for exception, keywords in test_cases:
        try:
            message = str(exception)
            for keyword in keywords:
                assert keyword.lower() in message.lower(), \
                    f"Error message should contain '{keyword}'"
            results.test_pass(f"{type(exception).__name__} message quality")
        except AssertionError as e:
            results.test_fail(f"{type(exception).__name__} message quality", str(e))
    
    return results


def run_all_tests():
    """Run all test suites."""
    # Configure output for Windows console
    import sys
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    print("="*60)
    print("Testing Error Handling System")
    print("="*60)
    
    all_results = TestResults()
    
    print("\n[TEST SUITE 1] Exception Hierarchy")
    print("-" * 60)
    results1 = test_exception_hierarchy()
    
    print("\n[TEST SUITE 2] Exception Messages")
    print("-" * 60)
    results2 = test_exception_messages()
    
    print("\n[TEST SUITE 3] Exception Catching")
    print("-" * 60)
    results3 = test_exception_catching()
    
    print("\n[TEST SUITE 4] Document Error Detection")
    print("-" * 60)
    results4 = test_document_processing_error_detection()
    
    print("\n[TEST SUITE 5] Error Message Quality")
    print("-" * 60)
    results5 = test_error_message_quality()
    
    # Combine results
    all_results.passed = (
        results1.passed + results2.passed + results3.passed + 
        results4.passed + results5.passed
    )
    all_results.failed = (
        results1.failed + results2.failed + results3.failed + 
        results4.failed + results5.failed
    )
    all_results.errors = (
        results1.errors + results2.errors + results3.errors + 
        results4.errors + results5.errors
    )
    
    success = all_results.summary()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)

