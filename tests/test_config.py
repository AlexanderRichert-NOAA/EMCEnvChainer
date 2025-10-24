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
    
    def test_builtin_platforms(self):
        """Test that built-in platforms are available."""
        config = Config()
        platforms = config.get_platforms()
        
        # Check that expected platforms are present
        expected_platforms = ["ursa", "orion", "hercules", "jet", "gaea-c5", "gaea-c6"]
        for platform in expected_platforms:
            assert platform in platforms
            assert "name" in platforms[platform]
            assert "spack_stack_path" in platforms[platform]
            assert "hostname_patterns" in platforms[platform]
    
    def test_config_get_set(self):
        """Test config get/set operations."""
        config = Config()
        
        # Test get with default
        assert config.get("nonexistent.key", "default") == "default"
        
        # Test nested key access
        ursa_name = config.get("platforms.ursa.name")
        assert ursa_name == "Ursa (RDHPCS)"
    
    def test_platform_configuration(self):
        """Test platform-specific configuration."""
        config = Config()
        
        # Test Ursa configuration
        ursa_config = config.get("platforms.ursa")
        assert ursa_config["name"] == "Ursa (RDHPCS)"
        assert "hostname_patterns" in ursa_config
        assert "model_applications" in ursa_config
        
        # Test model applications
        model_apps = ursa_config["model_applications"]
        assert "ufs_weather_model" in model_apps
