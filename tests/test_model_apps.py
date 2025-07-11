"""Tests for model application management."""

import pytest
from unittest.mock import Mock, patch
from src.emcenvchainer.model_apps import ModelApplication, ModelApplicationManager


class TestModelApplication:
    """Test ModelApplication class."""
    
    def test_model_application_initialization(self):
        """Test ModelApplication initialization."""
        config = {
            "name": "UFS Weather Model",
            "module_url_templates": [
                "https://example.com/ufs_hera.intel.lua",
                "https://example.com/ufs_hera.gnu.lua"
            ],
            "common_module_url": "https://example.com/ufs_common.lua",
            "install_path_regex": r'setenv\("UFS_WEATHER_MODEL_ROOT",\s*"([^"]+)"\)'
        }
        
        app = ModelApplication("ufs_weather_model", config, "hera")
        
        assert app.name == "ufs_weather_model"
        assert app.config == config
        assert app.platform_name == "hera"
        assert len(app.module_urls) == 2
        assert app.module_url == "https://example.com/ufs_hera.intel.lua"  # First URL by default
    
    def test_get_module_url_choices(self):
        """Test getting module URL choices with user-friendly names."""
        config = {
            "module_url_templates": [
                "https://example.com/hera.intel.lua",
                "https://example.com/hera.gnu.lua"
            ]
        }
        
        app = ModelApplication("test_app", config, "hera")
        choices = app.get_module_url_choices()
        
        assert len(choices) == 2
        assert choices[0]['name'] == "hera (INTEL)"
        assert choices[0]['url'] == "https://example.com/hera.intel.lua"
        assert choices[1]['name'] == "hera (GNU)"
        assert choices[1]['url'] == "https://example.com/hera.gnu.lua"
    
    @patch('requests.get')
    def test_get_upgradable_packages_success(self, mock_get):
        """Test successful parsing of upgradable packages from common module."""
        # Mock response for common module file
        mock_response = Mock()
        mock_response.text = '''-- UFS Common Module File
local netcdf_version = "4.9.2"
local hdf5_version = "1.12.2"
setenv("NETCDF_VERSION", "4.9.2")
load("cmake/3.23.1")

-- Upgradable packages
-- numpy (1.24.3) [Scientific computing library]
-- scipy (1.10.1) [Scientific Python library]
'''
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        config = {
            "common_module_url": "https://example.com/ufs_common.lua"
        }
        
        app = ModelApplication("test_app", config, "hera")
        packages = app.get_upgradable_packages()
        
        # Should find packages from various patterns
        package_names = {pkg['name'] for pkg in packages}
        assert 'netcdf' in package_names
        assert 'hdf5' in package_names
        assert 'cmake' in package_names
        assert 'numpy' in package_names
        assert 'scipy' in package_names
        
        # Check specific package details
        netcdf_pkg = next(pkg for pkg in packages if pkg['name'] == 'netcdf')
        assert netcdf_pkg['version'] == "4.9.2"
        
        numpy_pkg = next(pkg for pkg in packages if pkg['name'] == 'numpy')
        assert numpy_pkg['version'] == "1.24.3"
        assert numpy_pkg['description'] == "Scientific computing library"
    
    def test_get_upgradable_packages_no_common_url(self):
        """Test get_upgradable_packages when no common_module_url is configured."""
        config = {}  # No common_module_url
        
        app = ModelApplication("test_app", config, "hera")
        packages = app.get_upgradable_packages()
        
        assert packages == []


class TestModelApplicationManager:
    """Test ModelApplicationManager class."""
    
    def test_manager_initialization(self):
        """Test ModelApplicationManager initialization."""
        platform_config = {
            "model_applications": {
                "ufs_weather_model": {
                    "name": "UFS Weather Model",
                    "module_url_templates": ["https://example.com/ufs.lua"]
                }
            }
        }
        
        manager = ModelApplicationManager(platform_config, "hera")
        
        assert manager.platform_config == platform_config
        assert manager.platform_name == "hera"
        assert len(manager.applications) == 1
        assert manager.applications[0].name == "ufs_weather_model"
    
    def test_get_application_by_name(self):
        """Test getting application by name."""
        platform_config = {
            "model_applications": {
                "ufs_weather_model": {
                    "name": "UFS Weather Model",
                    "module_url_templates": ["https://example.com/ufs.lua"]
                }
            }
        }
        
        manager = ModelApplicationManager(platform_config, "hera")
        
        app = manager.get_application_by_name("ufs_weather_model")
        assert app is not None
        assert app.name == "ufs_weather_model"
        
        missing_app = manager.get_application_by_name("nonexistent")
        assert missing_app is None

    @patch('requests.get')
    def test_full_workflow_with_upgradable_packages(self, mock_get):
        """Test the full workflow including module URL selection and upgradable packages."""
        # Mock responses for both module file and common module
        def mock_requests_side_effect(url, timeout=None):
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            
            if "ufs_common.lua" in url:
                mock_response.text = '''-- UFS Common Module File
-- Upgradable packages
-- netcdf (4.9.2) [Network Common Data Form]
-- hdf5 (1.12.2) [Hierarchical Data Format]
-- cmake (3.23.1) [Build system generator]
'''
            else:
                # Regular module file
                mock_response.text = '''-- UFS Weather Model Module
setenv("UFS_WEATHER_MODEL_ROOT", "/path/to/ufs")
load("netcdf/4.8.1")
load("hdf5/1.10.8")
'''
            return mock_response
        
        mock_get.side_effect = mock_requests_side_effect
        
        platform_config = {
            "model_applications": {
                "ufs_weather_model": {
                    "name": "UFS Weather Model",
                    "module_url_templates": [
                        "https://example.com/ufs_hera.intel.lua",
                        "https://example.com/ufs_hera.gnu.lua"
                    ],
                    "common_module_url": "https://example.com/ufs_common.lua",
                    "install_path_regex": r'setenv\("UFS_WEATHER_MODEL_ROOT",\s*"([^"]+)"\)'
                }
            }
        }
        
        manager = ModelApplicationManager(platform_config, "hera")
        app = manager.get_application_by_name("ufs_weather_model")
        
        # Test module URL choices
        choices = app.get_module_url_choices()
        assert len(choices) == 2
        assert choices[0]['name'] == "ufs_hera (INTEL)"
        assert choices[1]['name'] == "ufs_hera (GNU)"
        
        # Test getting upgradable packages
        upgradable_packages = app.get_upgradable_packages()
        assert len(upgradable_packages) == 3
        
        package_names = {pkg['name'] for pkg in upgradable_packages}
        assert 'netcdf' in package_names
        assert 'hdf5' in package_names
        assert 'cmake' in package_names
        
        # Test parsing dependencies from module file
        dependencies = app.parse_dependencies()
        dep_names = {dep['name'] for dep in dependencies}
        assert 'netcdf' in dep_names
        assert 'hdf5' in dep_names
        
        # Verify that upgradable packages have newer versions than dependencies
        netcdf_dep = next(dep for dep in dependencies if dep['name'] == 'netcdf')
        netcdf_upgradable = next(pkg for pkg in upgradable_packages if pkg['name'] == 'netcdf')
        
        assert netcdf_dep['version'] == "4.8.1"  # From module file
        assert netcdf_upgradable['version'] == "4.9.2"  # From common module file
