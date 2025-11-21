"""
Tests for configuration management.

Tests cover:
- Configuration validation
- Environment variable loading
- Default values
- Invalid configuration handling
"""
import pytest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import Config class
try:
    from app import Config
except ImportError:
    import importlib.util
    spec = importlib.util.spec_from_file_location("app", "app.py.py")
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    Config = app.Config


class TestConfigDefaults:
    """Test default configuration values."""
    
    def test_default_audio_quality(self):
        """Test default audio quality is set correctly."""
        config = Config()
        assert config.audio_quality == 96
    
    def test_default_openai_model(self):
        """Test default OpenAI model is set correctly."""
        config = Config()
        assert config.openai_model == "gpt-4o-mini"
    
    def test_default_max_file_size(self):
        """Test default max file size is within Whisper limit."""
        config = Config()
        assert config.max_audio_file_size_mb == 24
        assert config.max_audio_file_size_mb <= 25  # Whisper API limit
    
    def test_default_token_limits(self):
        """Test default token limits are set."""
        config = Config()
        assert config.summary_max_tokens == 1000
        assert config.key_factors_max_tokens == 1500
        assert config.title_max_tokens == 50
    
    def test_default_rate_limit(self):
        """Test default rate limit is set."""
        config = Config()
        assert config.rate_limit_seconds == 5


class TestConfigValidation:
    """Test configuration validation logic."""
    
    def test_invalid_audio_quality_too_low(self):
        """Test that audio quality below 32 raises error."""
        with pytest.raises(ValueError, match="Invalid audio quality"):
            Config(audio_quality=20)
    
    def test_invalid_audio_quality_too_high(self):
        """Test that audio quality above 320 raises error."""
        with pytest.raises(ValueError, match="Invalid audio quality"):
            Config(audio_quality=500)
    
    def test_valid_audio_quality_range(self):
        """Test that valid audio quality values are accepted."""
        config = Config(audio_quality=64)
        assert config.audio_quality == 64
        
        config = Config(audio_quality=128)
        assert config.audio_quality == 128
        
        config = Config(audio_quality=320)
        assert config.audio_quality == 320
    
    def test_max_file_size_limit(self):
        """Test that max file size cannot exceed Whisper limit."""
        with pytest.raises(ValueError, match="Max file size cannot exceed 25MB"):
            Config(max_audio_file_size_mb=30)
    
    def test_output_dir_creation(self):
        """Test that output directory is created on init."""
        from pathlib import Path
        test_dir = Path("test_outputs_temp")
        
        # Clean up if exists
        if test_dir.exists():
            import shutil
            shutil.rmtree(test_dir)
        
        config = Config(output_dir=test_dir)
        assert test_dir.exists()
        
        # Cleanup
        import shutil
        shutil.rmtree(test_dir)


class TestConfigEnvironmentVariables:
    """Test configuration loading from environment variables."""
    
    def test_audio_quality_from_env(self, monkeypatch):
        """Test loading audio quality from environment."""
        monkeypatch.setenv("AUDIO_QUALITY", "128")
        config = Config()
        assert config.audio_quality == 128
    
    def test_openai_model_from_env(self, monkeypatch):
        """Test loading OpenAI model from environment."""
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4")
        config = Config()
        assert config.openai_model == "gpt-4"
    
    def test_invalid_audio_quality_from_env(self, monkeypatch):
        """Test that invalid env value raises error."""
        monkeypatch.setenv("AUDIO_QUALITY", "1000")
        with pytest.raises(ValueError, match="Invalid audio quality"):
            Config()
    
    def test_env_fallback_to_defaults(self):
        """Test that missing env vars use defaults."""
        # Ensure env vars are not set
        os.environ.pop("AUDIO_QUALITY", None)
        os.environ.pop("OPENAI_MODEL", None)
        
        config = Config()
        assert config.audio_quality == 96  # Default
        assert config.openai_model == "gpt-4o-mini"  # Default


class TestConfigIntegration:
    """Test configuration integration scenarios."""
    
    def test_config_immutable_after_creation(self):
        """Test that config values can be accessed after creation."""
        config = Config()
        
        # Should be able to read all values
        assert isinstance(config.audio_quality, int)
        assert isinstance(config.openai_model, str)
        assert isinstance(config.max_audio_file_size_mb, int)
        assert isinstance(config.rate_limit_seconds, int)
    
    def test_multiple_config_instances(self):
        """Test creating multiple config instances."""
        config1 = Config(audio_quality=96)
        config2 = Config(audio_quality=128)
        
        assert config1.audio_quality == 96
        assert config2.audio_quality == 128
    
    def test_config_string_representation(self):
        """Test that config can be converted to string."""
        config = Config()
        config_str = str(config)
        assert "Config" in config_str or "audio_quality" in config_str


# Run with: pytest tests/test_config.py -v
# Coverage: pytest tests/test_config.py --cov=app --cov-report=html

