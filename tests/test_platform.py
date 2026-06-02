"""Tests for platform detection."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from emcenvchainer.platform import Platform, PlatformDetector
from emcenvchainer.config import Config


class TestPlatform:
    """Test Platform class."""
    
    def test_platform_initialization(self):
        """Test platform initialization."""
        config = {
            "name": "Test Platform",
            "spack_stack_path": "/test/path",
            "model_applications": {}
        }
        platform = Platform("test", "/test/path", config)
        
        assert platform.name == "test"
        assert str(platform.spack_stack_path) == "/test/path"
        assert platform.config == config
    
    def test_spack_installations_discovery(self):
        """Test Spack installations discovery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock directory structure
            spack_stack_path = Path(tmpdir) / "spack-stack"
            install_dir = spack_stack_path / "spack-stack-1.5.0" / "envs" / "unified-env" / "install"
            install_dir.mkdir(parents=True)

            config = {
                "name": "Test Platform",
                "spack_stack_path": str(spack_stack_path),
                "model_applications": {}
            }
            platform = Platform("test", str(spack_stack_path), config)

            installations = platform.spack_installations
            assert len(installations) == 1
            result = installations[0]
            assert result["version"] == "1.5.0"
            assert result["environment"] == "unified-env"
            assert result["name"] == "unified-env (v1.5.0)"
            assert result["type"] == "spack_installation"
            assert result["install_path"] == str(install_dir)
    
    def test_spack_installations_nonexistent_path(self):
        """Test Spack installations discovery when spack_stack_path does not exist."""
        config = {
            "name": "Test Platform",
            "spack_stack_path": "/nonexistent/path/that/does/not/exist",
            "model_applications": {}
        }
        platform = Platform("test", "/nonexistent/path/that/does/not/exist", config)
        
        assert platform.spack_installations == []
    
    @pytest.mark.parametrize("config_extra", [
        ({"model_applications": {}}),
        ({}),
    ], ids=["empty_dict", "missing_key"])
    def test_model_applications_empty_or_missing(self, config_extra):
        """Test model_applications returns empty list when the key is absent or maps to an empty dict."""
        config = {"name": "Test Platform", "spack_stack_path": "/test/path", **config_extra}
        platform = Platform("test", "/test/path", config)
        assert platform.model_applications == []

    def test_model_applications_with_data(self):
        """Test model_applications property with actual applications."""
        config = {
            "name": "Test Platform",
            "spack_stack_path": "/test/path",
            "model_applications": {
                "ufs-weather-model": {"version": "1.0.0", "path": "/apps/ufs"},
                "gfs-utils": {"version": "2.0.0", "path": "/apps/gfs"}
            }
        }
        platform = Platform("test", "/test/path", config)
        
        apps = platform.model_applications
        assert len(apps) == 2

        # Check that items are tuples of (name, config)
        app_names = [app[0] for app in apps]
        assert "ufs-weather-model" in app_names
        assert "gfs-utils" in app_names
        
        # Verify we can access the configuration
        for name, app_config in apps:
            if name == "ufs-weather-model":
                assert app_config["version"] == "1.0.0"
                assert app_config["path"] == "/apps/ufs"
            elif name == "gfs-utils":
                assert app_config["version"] == "2.0.0"
                assert app_config["path"] == "/apps/gfs"


class TestPlatformDetector:
    """Test PlatformDetector class."""
    
    def test_auto_detect_platform_none(self, monkeypatch):
        """Test auto-detection returns None when hostname and SITE_OVERRIDE do not match any platform."""
        monkeypatch.delenv("SITE_OVERRIDE", raising=False)
        detector = PlatformDetector()
        with patch('socket.getfqdn', return_value='no-match.example.invalid'):
            platform = detector.detect_platform()
        assert platform is None
    
    def test_detect_platform_with_site_override(self, monkeypatch):
        """Test platform detection with SITE_OVERRIDE environment variable."""
        mock_config = Mock(spec=Config)
        mock_config.get_platforms.return_value = {
            "test_platform": {
                "name": "Test Platform",
                "spack_stack_path": "/test/spack",
                "hostname_patterns": ["testhost.*"],
                "model_applications": {}
            }
        }

        detector = PlatformDetector(config=mock_config)
        monkeypatch.setenv("SITE_OVERRIDE", "test_platform")

        # Patch getfqdn so hostname detection does not inadvertently match
        with patch("socket.getfqdn", return_value="unrelated.host.example"):
            platform = detector.detect_platform()
        assert platform is not None
        assert platform.name == "Test Platform"
        assert str(platform.spack_stack_path) == "/test/spack"
    
    def test_detect_platform_with_hostname_match(self, monkeypatch):
        """Test platform detection with hostname pattern match."""
        mock_config = Mock(spec=Config)
        mock_config.get_platforms.return_value = {
            "test_platform": {
                "name": "Test Platform",
                "spack_stack_path": "/test/spack",
                "hostname_patterns": [".*\\.test\\.domain"],
                "model_applications": {}
            }
        }

        detector = PlatformDetector(config=mock_config)
        monkeypatch.delenv("SITE_OVERRIDE", raising=False)

        with patch("socket.getfqdn", return_value="server.test.domain"):
            platform = detector.detect_platform()
        assert platform is not None
        assert platform.name == "Test Platform"
    
    @pytest.mark.parametrize("patterns,hostname,expected_result,description", [
        (None, "any.host.com", False, "missing hostname_patterns key"),
        ([], "any.host.com", False, "empty patterns list"),
        (["node.*\\.cluster\\.local"], "node01.cluster.local", True, "matching pattern"),
        (["node.*\\.cluster\\.local"], "server.different.domain", False, "non-matching pattern"),
        (["node.*\\.cluster1\\.local", "node.*\\.cluster2\\.local"], "node05.cluster2.local", True, "multiple patterns - second matches"),
    ])
    def test_check_platform_hostname(self, patterns, hostname, expected_result, description):
        """Test _check_platform_hostname with various pattern configurations."""
        detector = PlatformDetector()
        platform_config = {"name": "Test Platform", "spack_stack_path": "/test/path"}
        if patterns is not None:
            platform_config["hostname_patterns"] = patterns

        with patch("socket.getfqdn", return_value=hostname):
            result = detector._check_platform_hostname(platform_config)
        assert result == expected_result, f"Failed test case: {description}"
