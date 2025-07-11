"""Tests for configuration management."""

import pytest

from emcenvchainer.config import Config


class TestConfig:
    """Test Config class."""
    
    def test_config_initialization(self):
        """Test config initialization."""
        config = Config()
        assert config._config is not None
        assert "platforms" in config._config
        assert "spack" in config._config
    
    def test_builtin_platforms(self):
        """Test that built-in platforms are available."""
        config = Config()
        platforms = config.get_platforms()
        
        # Check that expected platforms are present
        expected_platforms = ["hera", "orion", "hercules", "derecho", "jet", "gaea"]
        for platform in expected_platforms:
            assert platform in platforms
            assert "name" in platforms[platform]
            assert "spack_stack_path" in platforms[platform]
            assert "detection_paths" in platforms[platform]
    
    def test_config_get_set(self):
        """Test config get/set operations."""
        config = Config()
        
        # Test get with default
        assert config.get("nonexistent.key", "default") == "default"
        
        # Test set and get
        config.set("test.key", "value")
        assert config.get("test.key") == "value"
        
        # Test nested key access
        hera_name = config.get("platforms.hera.name")
        assert hera_name == "NOAA Hera"
    
    def test_platform_configuration(self):
        """Test platform-specific configuration."""
        config = Config()
        
        # Test Hera configuration
        hera_config = config.get("platforms.hera")
        assert hera_config["name"] == "NOAA Hera"
        assert "detection_paths" in hera_config
        assert "model_applications" in hera_config
        
        # Test model applications
        model_apps = hera_config["model_applications"]
        assert "ufs_weather_model" in model_apps
