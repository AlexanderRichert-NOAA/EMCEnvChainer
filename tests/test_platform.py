"""Tests for platform detection."""

import os
import tempfile
from pathlib import Path
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
            version_dir = spack_stack_path / "spack-stack-1.5.0"
            envs_dir = version_dir / "envs"
            env_dir = envs_dir / "unified-env"
            install_dir = env_dir / "install"
            install_dir.mkdir(parents=True)
            
            # Create .spack-db to make it look like real install
            spack_db = install_dir / ".spack-db"
            spack_db.mkdir()
            
            config = {
                "name": "Test Platform",
                "spack_stack_path": str(spack_stack_path),
                "model_applications": {}
            }
            platform = Platform("test", str(spack_stack_path), config)
            
            installations = platform.spack_installations
            assert len(installations) == 1
            assert installations[0]["version"] == "1.5.0"
            assert installations[0]["environment"] == "unified-env"
    
    def test_spack_installations_nonexistent_path(self):
        """Test Spack installations discovery when spack_stack_path does not exist."""
        config = {
            "name": "Test Platform",
            "spack_stack_path": "/nonexistent/path/that/does/not/exist",
            "model_applications": {}
        }
        platform = Platform("test", "/nonexistent/path/that/does/not/exist", config)
        
        # Should return empty list when path doesn't exist
        installations = platform.spack_installations
        assert installations == []
        assert isinstance(installations, list)
    
    def test_model_applications_empty(self):
        """Test model_applications property with empty configuration."""
        config = {
            "name": "Test Platform",
            "spack_stack_path": "/test/path",
            "model_applications": {}
        }
        platform = Platform("test", "/test/path", config)
        
        apps = platform.model_applications
        assert apps == []
        assert isinstance(apps, list)
    
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
        assert isinstance(apps, list)
        
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
    
    def test_model_applications_missing_key(self):
        """Test model_applications property when key is missing from config."""
        config = {
            "name": "Test Platform",
            "spack_stack_path": "/test/path"
            # No model_applications key
        }
        platform = Platform("test", "/test/path", config)
        
        apps = platform.model_applications
        assert apps == []
        assert isinstance(apps, list)
    
    def test_model_applications_cached(self):
        """Test that model_applications property is cached after first access."""
        config = {
            "name": "Test Platform",
            "spack_stack_path": "/test/path",
            "model_applications": {
                "app1": {"version": "1.0.0"}
            }
        }
        platform = Platform("test", "/test/path", config)
        
        # First access
        apps1 = platform.model_applications
        # Second access should return the same object (cached)
        apps2 = platform.model_applications
        assert apps1 is apps2
        
        # Verify the private variable is set
        assert platform._model_applications is not None
    
    def test_get_spack_root(self):
        """Test get_spack_root method."""
        config = {
            "name": "Test Platform",
            "spack_stack_path": "/test/path",
            "model_applications": {}
        }
        platform = Platform("test", "/test/path", config)
        
        # Create a mock installation dict
        installation = {
            "name": "unified-env (v1.5.0)",
            "version": "1.5.0",
            "environment": "unified-env",
            "install_path": "/test/path/spack-stack-1.5.0/envs/unified-env/install",
            "spack_root": "/test/path/spack-stack-1.5.0/spack",
            "type": "spack_installation"
        }
        
        spack_root = platform.get_spack_root(installation)
        assert spack_root == "/test/path/spack-stack-1.5.0/spack"
        assert isinstance(spack_root, str)
    
    def test_get_spack_root_different_versions(self):
        """Test get_spack_root with different installation versions."""
        config = {
            "name": "Test Platform",
            "spack_stack_path": "/test/path",
            "model_applications": {}
        }
        platform = Platform("test", "/test/path", config)
        
        # Test with version 2.0.0
        installation1 = {
            "spack_root": "/opt/spack-stack-2.0.0/spack"
        }
        assert platform.get_spack_root(installation1) == "/opt/spack-stack-2.0.0/spack"
        
        # Test with version 1.0.0
        installation2 = {
            "spack_root": "/home/user/spack-stack-1.0.0/spack"
        }
        assert platform.get_spack_root(installation2) == "/home/user/spack-stack-1.0.0/spack"


class TestPlatformDetector:
    """Test PlatformDetector class."""
    
    def test_detector_initialization(self):
        """Test detector initialization."""
        detector = PlatformDetector()
        assert detector.config is not None
    
    def test_auto_detect_platform_none(self):
        """Test auto-detection when no platform matches."""
        detector = PlatformDetector()
        platform = detector.detect_platform()
        # Should return None since test environment won't match patterns
        assert platform is None or isinstance(platform, Platform)
    
    def test_detect_platform_with_site_override(self, monkeypatch):
        """Test platform detection with SITE_OVERRIDE environment variable."""
        from unittest.mock import Mock, patch
        
        # Create a mock config with a known platform
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
        
        # Set SITE_OVERRIDE to match the platform key
        monkeypatch.setenv("SITE_OVERRIDE", "test_platform")
        
        platform = detector.detect_platform()
        assert platform is not None
        assert platform.name == "Test Platform"
        assert str(platform.spack_stack_path) == "/test/spack"
    
    def test_detect_platform_with_hostname_match(self, monkeypatch):
        """Test platform detection with hostname pattern match."""
        from unittest.mock import Mock, patch
        
        # Create a mock config
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
        
        # Mock socket.getfqdn to return a matching hostname
        with patch('socket.getfqdn', return_value='server.test.domain'):
            platform = detector.detect_platform()
            assert platform is not None
            assert platform.name == "Test Platform"
    
    @pytest.mark.parametrize("patterns,hostname,expected_result,description", [
        ([], "any.host.com", False, "no patterns"),
        (["node.*\\.cluster\\.local"], "node01.cluster.local", True, "matching pattern"),
        (["node.*\\.cluster\\.local"], "server.different.domain", False, "non-matching pattern"),
        (["node.*\\.cluster1\\.local", "node.*\\.cluster2\\.local"], "node05.cluster2.local", True, "multiple patterns - second matches"),
    ])
    def test_check_platform_hostname(self, patterns, hostname, expected_result, description, monkeypatch):
        """Test _check_platform_hostname with various pattern configurations."""
        from unittest.mock import patch
        
        detector = PlatformDetector()
        platform_config = {
            "name": "Test Platform",
            "spack_stack_path": "/test/path",
            "hostname_patterns": patterns
        }
        
        with patch('socket.getfqdn', return_value=hostname):
            result = detector._check_platform_hostname(platform_config)
            assert result == expected_result, f"Failed test case: {description}"
    
    def test_check_platform_hostname_missing_key(self):
        """Test _check_platform_hostname when hostname_patterns key is missing."""
        detector = PlatformDetector()
        platform_config = {
            "name": "Test Platform",
            "spack_stack_path": "/test/path"
        }
        
        result = detector._check_platform_hostname(platform_config)
        assert result is False
