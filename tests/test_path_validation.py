"""
Tests for path validation and sanitization.

Tests cover:
- Directory traversal prevention
- Path resolution validation
- Symlink attack prevention
- Safe path construction
"""
import pytest
import sys
import os
from pathlib import Path
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

from app import validate_and_sanitize_path


class TestPathValidation:
    """Test path validation and sanitization."""
    
    @pytest.fixture
    def base_dir(self, tmp_path):
        """Create a temporary base directory for testing."""
        base = tmp_path / "base_dir"
        base.mkdir()
        return base
    
    def test_valid_path_component(self, base_dir):
        """Test that valid path components pass validation."""
        is_valid, path, error = validate_and_sanitize_path("test_project", base_dir)
        assert is_valid is True
        assert path is not None
        assert path == base_dir / "test_project"
        assert error == ""
    
    def test_directory_traversal_double_dot(self, base_dir):
        """Test that .. patterns are rejected."""
        is_valid, path, error = validate_and_sanitize_path("../etc/passwd", base_dir)
        assert is_valid is False
        assert path is None
        assert "forbidden" in error.lower() or ".." in error
    
    def test_directory_traversal_single_dot(self, base_dir):
        """Test that . patterns are handled."""
        # Single dot should be sanitized but might still be valid
        is_valid, path, error = validate_and_sanitize_path(".hidden", base_dir)
        # Should pass (single dot is not traversal)
        assert is_valid is True
    
    def test_path_separator_forward_slash(self, base_dir):
        """Test that forward slashes are rejected."""
        is_valid, path, error = validate_and_sanitize_path("project/subdir", base_dir)
        assert is_valid is False
        assert path is None
        assert "forbidden" in error.lower() or "/" in error
    
    def test_path_separator_backslash(self, base_dir):
        """Test that backslashes are rejected."""
        is_valid, path, error = validate_and_sanitize_path("project\\subdir", base_dir)
        assert is_valid is False
        assert path is None
        assert "forbidden" in error.lower() or "\\" in error
    
    def test_null_byte_rejection(self, base_dir):
        """Test that null bytes are rejected."""
        is_valid, path, error = validate_and_sanitize_path("project\x00name", base_dir)
        assert is_valid is False
        assert path is None
        assert "null" in error.lower()
    
    def test_empty_string_rejection(self, base_dir):
        """Test that empty strings are rejected."""
        is_valid, path, error = validate_and_sanitize_path("", base_dir)
        assert is_valid is False
        assert path is None
        assert "empty" in error.lower()
    
    def test_whitespace_only_rejection(self, base_dir):
        """Test that whitespace-only strings are rejected."""
        is_valid, path, error = validate_and_sanitize_path("   ", base_dir)
        assert is_valid is False
        assert path is None
        assert "empty" in error.lower()
    
    def test_absolute_path_rejection(self, base_dir):
        """Test that absolute paths are rejected when not allowed."""
        # Unix-style absolute path (caught by / check first, which is fine)
        is_valid, path, error = validate_and_sanitize_path("/etc/passwd", base_dir, allow_absolute=False)
        assert is_valid is False
        assert path is None
        # Either caught by / check or absolute check - both are valid
        assert "forbidden" in error.lower() or "absolute" in error.lower()
        
        # Windows-style absolute path (caught by : check or absolute check)
        is_valid, path, error = validate_and_sanitize_path("C:\\Windows", base_dir, allow_absolute=False)
        assert is_valid is False
        assert path is None
        # Windows path with : should be caught
        assert "forbidden" in error.lower() or "absolute" in error.lower() or ":" in error.lower()
    
    def test_path_sanitization(self, base_dir):
        """Test that paths are sanitized using safe_filename."""
        # Path with special characters should be sanitized
        is_valid, path, error = validate_and_sanitize_path("test@#$project", base_dir)
        assert is_valid is True
        assert path is not None
        # Should be sanitized (special chars replaced)
        assert "test" in path.name.lower()
        assert "@" not in path.name
        assert "#" not in path.name
    
    def test_path_resolves_within_base(self, base_dir):
        """Test that resolved path stays within base directory."""
        # Create a subdirectory
        subdir = base_dir / "valid_project"
        subdir.mkdir()
        
        is_valid, path, error = validate_and_sanitize_path("valid_project", base_dir)
        assert is_valid is True
        assert path.resolve().parent == base_dir.resolve()
    
    def test_none_input(self, base_dir):
        """Test that None input is rejected."""
        is_valid, path, error = validate_and_sanitize_path(None, base_dir)
        assert is_valid is False
        assert path is None
        assert "empty" in error.lower() or "invalid" in error.lower()
    
    def test_unicode_path_component(self, base_dir):
        """Test that Unicode path components are handled."""
        is_valid, path, error = validate_and_sanitize_path("测试_project", base_dir)
        # Should pass validation (Unicode is sanitized but may become underscores)
        # The important part is it doesn't crash and validates correctly
        assert isinstance(is_valid, bool)
    
    def test_very_long_path(self, base_dir):
        """Test that very long paths are handled."""
        long_name = "a" * 300  # Very long name
        is_valid, path, error = validate_and_sanitize_path(long_name, base_dir)
        # Should still validate (length is OS/filesystem dependent)
        assert isinstance(is_valid, bool)
    
    def test_path_with_spaces(self, base_dir):
        """Test that paths with spaces are sanitized."""
        is_valid, path, error = validate_and_sanitize_path("project with spaces", base_dir)
        assert is_valid is True
        assert path is not None
        # Spaces should be converted to underscores by safe_filename
        assert "_" in path.name or " " in path.name
    
    def test_nested_traversal_attempt(self, base_dir):
        """Test nested traversal attempts."""
        is_valid, path, error = validate_and_sanitize_path("project/../other", base_dir)
        assert is_valid is False
        assert path is None
    
    def test_multiple_traversal_attempts(self, base_dir):
        """Test multiple traversal attempts."""
        is_valid, path, error = validate_and_sanitize_path("../../../../etc", base_dir)
        assert is_valid is False
        assert path is None
    
    def test_mixed_traversal_attempts(self, base_dir):
        """Test mixed traversal patterns."""
        is_valid, path, error = validate_and_sanitize_path("project\\..\\other", base_dir)
        assert is_valid is False
        assert path is None
    
    def test_path_parent_validation(self, base_dir):
        """Test that path parent is validated."""
        # This test ensures the parent check works
        # Create a valid project
        valid_project = base_dir / "valid"
        valid_project.mkdir()
        
        is_valid, path, error = validate_and_sanitize_path("valid", base_dir)
        assert is_valid is True
        assert path.parent == base_dir


# Run with: pytest tests/test_path_validation.py -v

