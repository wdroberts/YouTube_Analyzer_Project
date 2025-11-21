"""
Tests for file operations and safety functions.

Tests cover:
- Safe file writing
- File reading
- Error handling
- Path validation
"""
import pytest
from pathlib import Path
import tempfile
import shutil
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from app import safe_write_text, read_file_bytes
except ImportError:
    import importlib.util
    spec = importlib.util.spec_from_file_location("app", "app.py.py")
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    safe_write_text = app.safe_write_text
    read_file_bytes = app.read_file_bytes


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup
    if temp_path.exists():
        shutil.rmtree(temp_path)


class TestSafeWriteText:
    """Test safe text writing function."""
    
    def test_write_simple_text(self, temp_dir):
        """Test writing simple text file."""
        file_path = temp_dir / "test.txt"
        content = "Hello, World!"
        
        result = safe_write_text(file_path, content)
        
        assert result is True
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == content
    
    def test_write_multiline_text(self, temp_dir):
        """Test writing multiline text."""
        file_path = temp_dir / "multiline.txt"
        content = "Line 1\nLine 2\nLine 3"
        
        result = safe_write_text(file_path, content)
        
        assert result is True
        assert file_path.read_text(encoding="utf-8") == content
    
    def test_write_unicode_text(self, temp_dir):
        """Test writing unicode content."""
        file_path = temp_dir / "unicode.txt"
        content = "Hello 世界 🌍"
        
        result = safe_write_text(file_path, content)
        
        assert result is True
        assert file_path.read_text(encoding="utf-8") == content
    
    def test_overwrite_existing_file(self, temp_dir):
        """Test overwriting existing file."""
        file_path = temp_dir / "overwrite.txt"
        
        # Write initial content
        safe_write_text(file_path, "Initial")
        assert file_path.read_text(encoding="utf-8") == "Initial"
        
        # Overwrite
        result = safe_write_text(file_path, "Overwritten")
        
        assert result is True
        assert file_path.read_text(encoding="utf-8") == "Overwritten"
    
    def test_write_to_nonexistent_directory(self, temp_dir):
        """Test writing to non-existent directory fails gracefully."""
        # Use a path that doesn't exist
        bad_path = temp_dir / "nonexistent" / "deep" / "path" / "file.txt"
        
        result = safe_write_text(bad_path, "content")
        
        # Should return False, not crash
        assert result is False
    
    def test_write_empty_string(self, temp_dir):
        """Test writing empty string."""
        file_path = temp_dir / "empty.txt"
        
        result = safe_write_text(file_path, "")
        
        assert result is True
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == ""
    
    def test_write_large_content(self, temp_dir):
        """Test writing large content."""
        file_path = temp_dir / "large.txt"
        content = "A" * 1000000  # 1 million characters
        
        result = safe_write_text(file_path, content)
        
        assert result is True
        assert file_path.read_text(encoding="utf-8") == content


class TestReadFileBytes:
    """Test file reading function."""
    
    def test_read_existing_file(self, temp_dir):
        """Test reading existing file."""
        file_path = temp_dir / "test.txt"
        content = b"Test content"
        file_path.write_bytes(content)
        
        result = read_file_bytes(file_path)
        
        assert result == content
    
    def test_read_binary_file(self, temp_dir):
        """Test reading binary file."""
        file_path = temp_dir / "binary.bin"
        content = bytes([0, 1, 2, 255, 254, 253])
        file_path.write_bytes(content)
        
        result = read_file_bytes(file_path)
        
        assert result == content
    
    def test_read_nonexistent_file(self, temp_dir):
        """Test reading non-existent file raises error."""
        file_path = temp_dir / "nonexistent.txt"
        
        with pytest.raises(IOError):
            read_file_bytes(file_path)
    
    def test_read_empty_file(self, temp_dir):
        """Test reading empty file."""
        file_path = temp_dir / "empty.txt"
        file_path.write_bytes(b"")
        
        result = read_file_bytes(file_path)
        
        assert result == b""


class TestTextValidation:
    """Test text validation and truncation."""
    
    def test_validate_and_truncate_short_text(self):
        """Test that short text passes through unchanged."""
        from app import validate_and_truncate_text
        
        text = "Short text"
        result = validate_and_truncate_text(text, max_length=100)
        
        assert result == text
    
    def test_validate_and_truncate_long_text(self):
        """Test that long text is truncated."""
        from app import validate_and_truncate_text
        
        text = "A" * 1000
        result = validate_and_truncate_text(text, max_length=100)
        
        assert len(result) == 100
        assert result == "A" * 100
    
    def test_validate_and_truncate_exact_length(self):
        """Test text at exact max length."""
        from app import validate_and_truncate_text
        
        text = "A" * 100
        result = validate_and_truncate_text(text, max_length=100)
        
        assert result == text


# Run with: pytest tests/test_file_operations.py -v

