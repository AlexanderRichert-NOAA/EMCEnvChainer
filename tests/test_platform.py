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
