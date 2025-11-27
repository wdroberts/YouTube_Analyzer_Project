"""
Tests for file upload validation functionality.

Tests cover:
- Filename sanitization and security
- File extension validation
- Content-type verification (magic bytes)
- Malicious file detection
"""
import pytest
import sys
import os
from io import BytesIO
from unittest.mock import Mock

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

from app import validate_uploaded_file, FILE_SIGNATURES


class MockUploadedFile:
    """Mock Streamlit uploaded file object for testing."""
    
    def __init__(self, name: str, content: bytes, size: int = None):
        self.name = name
        self._content = content
        self.size = size if size is not None else len(content)
        self._position = 0
    
    def read(self):
        """Read all file content."""
        self._position = len(self._content)
        return self._content
    
    def tell(self):
        """Get current position."""
        return self._position
    
    def seek(self, position: int):
        """Set position."""
        self._position = position


class TestFileValidation:
    """Test file validation functionality."""
    
    def test_valid_pdf_file(self):
        """Test that valid PDF files pass validation."""
        # Create a mock PDF file with correct signature
        pdf_content = b'%PDF-1.4\n' + b'x' * 100
        file_obj = MockUploadedFile("test.pdf", pdf_content)
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is True
        assert error == ""
    
    def test_valid_docx_file(self):
        """Test that valid DOCX files pass validation."""
        # DOCX files are ZIP archives, start with PK signature
        docx_content = b'PK\x03\x04' + b'x' * 100
        file_obj = MockUploadedFile("test.docx", docx_content)
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is True
        assert error == ""
    
    def test_valid_txt_file(self):
        """Test that valid text files pass validation."""
        txt_content = b"This is a valid text file with UTF-8 content."
        file_obj = MockUploadedFile("test.txt", txt_content)
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is True
        assert error == ""
    
    def test_invalid_file_extension(self):
        """Test that files with invalid extensions are rejected."""
        file_obj = MockUploadedFile("test.exe", b"binary content")
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is False
        assert "Unsupported file type" in error
    
    def test_file_signature_mismatch_pdf(self):
        """Test that PDF files with wrong signature are rejected."""
        # File has .pdf extension but wrong content
        fake_pdf = b'NOTAPDF' + b'x' * 100
        file_obj = MockUploadedFile("fake.pdf", fake_pdf)
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is False
        assert "does not match declared type" in error
    
    def test_file_signature_mismatch_docx(self):
        """Test that DOCX files with wrong signature are rejected."""
        # File has .docx extension but wrong content
        fake_docx = b'NOTADOCX' + b'x' * 100
        file_obj = MockUploadedFile("fake.docx", fake_docx)
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is False
        assert "does not match declared type" in error
    
    def test_binary_file_masked_as_txt(self):
        """Test that binary files with .txt extension are rejected."""
        # Binary content that's not text
        binary_content = bytes(range(256))  # All possible byte values
        file_obj = MockUploadedFile("binary.txt", binary_content)
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is False
        assert "binary data" in error.lower() or "text" in error.lower()
    
    def test_directory_traversal_attempt(self):
        """Test that directory traversal attempts are rejected."""
        file_obj = MockUploadedFile("../../../etc/passwd.pdf", b'%PDF-1.4')
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is False
        assert "forbidden" in error.lower() or "invalid" in error.lower()
    
    def test_path_separators_in_filename(self):
        """Test that path separators in filenames are rejected."""
        file_obj = MockUploadedFile("path/to/file.pdf", b'%PDF-1.4')
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is False
        assert "forbidden" in error.lower() or "invalid" in error.lower()
    
    def test_null_bytes_in_filename(self):
        """Test that null bytes in filenames are rejected."""
        file_obj = MockUploadedFile("file\x00name.pdf", b'%PDF-1.4')
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is False
        assert "forbidden" in error.lower() or "invalid" in error.lower()
    
    def test_windows_forbidden_chars(self):
        """Test that Windows forbidden characters are rejected."""
        for char in ['<', '>', '|', ':', '"', '*', '?']:
            file_obj = MockUploadedFile(f"file{char}name.pdf", b'%PDF-1.4')
            
            is_valid, error = validate_uploaded_file(file_obj)
            assert is_valid is False, f"Should reject filename with '{char}'"
            assert "forbidden" in error.lower() or "invalid" in error.lower()
    
    def test_empty_file(self):
        """Test that empty files are rejected."""
        file_obj = MockUploadedFile("empty.pdf", b'')
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_none_file(self):
        """Test that None file is rejected."""
        is_valid, error = validate_uploaded_file(None)
        assert is_valid is False
        assert "No file provided" in error
    
    def test_pdf_with_embedded_script(self):
        """Test that PDFs with embedded scripts are rejected."""
        # PDF with script tag in first 10KB
        pdf_with_script = b'%PDF-1.4\n' + b'<script>alert("xss")</script>' + b'x' * 1000
        file_obj = MockUploadedFile("malicious.pdf", pdf_with_script)
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is False
        assert "unsafe" in error.lower() or "script" in error.lower()
    
    def test_valid_txt_with_unicode(self):
        """Test that text files with Unicode characters are accepted."""
        txt_content = "This is a test with unicode: 测试 🎉".encode('utf-8')
        file_obj = MockUploadedFile("unicode.txt", txt_content)
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is True
        assert error == ""
    
    def test_txt_file_with_high_printable_ratio(self):
        """Test that text files with mostly printable characters pass."""
        # Create content that's mostly printable (80%+)
        printable_content = b'ABCDEFGHIJKLMNOPQRSTUVWXYZ ' * 20
        file_obj = MockUploadedFile("text.txt", printable_content)
        
        is_valid, error = validate_uploaded_file(file_obj)
        assert is_valid is True
        assert error == ""


# Run with: pytest tests/test_file_validation.py -v

