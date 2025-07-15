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
local numpy_ver = "1.24.3"
local scipy_ver = "1.10.1"
setenv("NETCDF_VERSION", "4.9.2")
load("cmake/3.23.1")
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
    
    def test_get_upgradable_packages_no_common_url(self):
        """Test get_upgradable_packages when no common_module_url is configured."""
        config = {}  # No common_module_url
        
        app = ModelApplication("test_app", config, "hera")
        packages = app.get_upgradable_packages()
        
        assert packages == []

    @patch('requests.get')
    def test_extract_install_path_success(self, mock_get):
        """Test successful extraction of install path from module file."""
        # Mock response for module file with install path
        mock_response = Mock()
        mock_response.text = '''-- UFS Weather Model Module File
setenv("UFS_WEATHER_MODEL_ROOT", "/opt/apps/ufs/1.0")
load("intel/19.1.0")
load("netcdf/4.9.2")
'''
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        config = {
            "module_url_templates": ["https://example.com/ufs_hera.lua"],
            "install_path_regex": r'setenv\("UFS_WEATHER_MODEL_ROOT",\s*"([^"]+)"\)'
        }
        
        app = ModelApplication("ufs_weather_model", config, "hera")
        install_path = app.extract_install_path()
        
        assert install_path == "/opt/apps/ufs/1.0"

    def test_extract_install_path_no_regex(self):
        """Test extract_install_path when no regex is configured."""
        config = {
            "module_url_templates": ["https://example.com/test.lua"]
        }
        
        app = ModelApplication("test_app", config, "hera")
        install_path = app.extract_install_path()
        
        assert install_path is None

    @patch('requests.get')
    def test_extract_install_path_no_match(self, mock_get):
        """Test extract_install_path when regex doesn't match module content."""
        mock_response = Mock()
        mock_response.text = '''-- Module file without install path
load("intel/19.1.0")
load("netcdf/4.9.2")
'''
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        config = {
            "module_url_templates": ["https://example.com/test.lua"],
            "install_path_regex": r'setenv\("INSTALL_ROOT",\s*"([^"]+)"\)'
        }
        
        app = ModelApplication("test_app", config, "hera")
        install_path = app.extract_install_path()
        
        assert install_path is None

    def test_handle_unified_load_pattern_pathjoin_success(self):
        """Test _handle_unified_load_pattern with valid pathJoin package and version."""
        config = {"module_url_templates": ["https://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "hera")
        
        # Create a mock match object for pathJoin pattern
        mock_match = Mock()
        mock_match.group.side_effect = lambda x: {1: "netcdf", 2: "netcdf_ver", 3: None}[x]
        
        module_content = '''
local netcdf_ver = "4.9.2"
load(pathJoin("netcdf", netcdf_ver))
'''
        
        result = app._handle_unified_load_pattern(mock_match, module_content)
        
        assert result == ("netcdf", "4.9.2")

    def test_handle_unified_load_pattern_pathjoin_stack_package(self):
        """Test _handle_unified_load_pattern with stack package (should be skipped)."""
        config = {"module_url_templates": ["https://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "hera")
        
        mock_match = Mock()
        mock_match.group.side_effect = lambda x: {1: "stack-intel", 2: "stack_intel_ver", 3: None}[x]
        
        module_content = '''
local stack_intel_ver = "2021.1"
load(pathJoin("stack-intel", stack_intel_ver))
'''
        
        result = app._handle_unified_load_pattern(mock_match, module_content)
        
        assert result is None

    def test_handle_unified_load_pattern_pathjoin_ufs_common(self):
        """Test _handle_unified_load_pattern with ufs_common (should be skipped)."""
        config = {"module_url_templates": ["https://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "hera")
        
        mock_match = Mock()
        mock_match.group.side_effect = lambda x: {1: "ufs_common", 2: "ufs_common_ver", 3: None}[x]
        
        module_content = '''
local ufs_common_ver = "1.0"
load(pathJoin("ufs_common", ufs_common_ver))
'''
        
        result = app._handle_unified_load_pattern(mock_match, module_content)
        
        assert result is None

    def test_handle_unified_load_pattern_pathjoin_version_not_found(self):
        """Test _handle_unified_load_pattern when version variable is not found."""
        config = {"module_url_templates": ["https://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "hera")
        
        mock_match = Mock()
        mock_match.group.side_effect = lambda x: {1: "netcdf", 2: "netcdf_ver", 3: None}[x]
        
        module_content = '''
-- No version definition for netcdf_ver
load(pathJoin("netcdf", netcdf_ver))
'''
        
        result = app._handle_unified_load_pattern(mock_match, module_content)
        
        assert result is None

    def test_handle_version_variable_pattern_success(self):
        """Test _handle_version_variable_pattern with valid package and version."""
        config = {"module_url_templates": ["https://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "hera")
        
        mock_match = Mock()
        mock_match.group.side_effect = ["netcdf_ver", "4.9.2"]
        
        module_content = '''netcdf_ver = os.getenv("NETCDF_VER") or "4.9.2"'''
        
        result = app._handle_version_variable_pattern(mock_match, module_content)
        
        assert result == ("netcdf", "4.9.2")

    def test_handle_version_variable_pattern_stack_package(self):
        """Test _handle_version_variable_pattern with stack package (should be skipped)."""
        config = {"module_url_templates": ["https://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "hera")
        
        mock_match = Mock()
        mock_match.group.side_effect = ["stack_intel_ver", "2021.1"]
        
        module_content = '''stack_intel_ver = os.getenv("STACK_INTEL_VER") or "2021.1"'''
        
        result = app._handle_version_variable_pattern(mock_match, module_content)
        
        assert result is None

    def test_handle_version_variable_pattern_ufs_common(self):
        """Test _handle_version_variable_pattern with ufs_common (should be skipped)."""
        config = {"module_url_templates": ["https://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "hera")
        
        mock_match = Mock()
        mock_match.group.side_effect = ["ufs_common_ver", "1.0"]
        
        module_content = '''ufs_common_ver = os.getenv("UFS_COMMON_VER") or "1.0"'''
        
        result = app._handle_version_variable_pattern(mock_match, module_content)
        
        assert result is None

    def test_handle_pathjoin_upgradable_pattern_success(self):
        """Test _handle_pathjoin_upgradable_pattern with valid package and version."""
        config = {"module_url_templates": ["https://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "hera")
        
        mock_match = Mock()
        mock_match.group.side_effect = ["netcdf", "netcdf_ver"]
        
        module_content = '''
local netcdf_ver = "4.9.2"
load(pathJoin("netcdf", netcdf_ver))
'''
        
        result = app._handle_pathjoin_upgradable_pattern(mock_match, module_content)
        
        assert result == ("netcdf", "4.9.2")

    def test_handle_pathjoin_upgradable_pattern_version_not_found(self):
        """Test _handle_pathjoin_upgradable_pattern when version variable is not defined."""
        config = {"module_url_templates": ["https://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "hera")
        
        mock_match = Mock()
        mock_match.group.side_effect = ["netcdf", "missing_ver"]
        
        module_content = '''
local netcdf_ver = "4.9.2"
load(pathJoin("netcdf", missing_ver))
'''
        
        result = app._handle_pathjoin_upgradable_pattern(mock_match, module_content)
        
        assert result is None

    def test_handle_pathjoin_upgradable_pattern_complex_variable(self):
        """Test _handle_pathjoin_upgradable_pattern with complex version variable name."""
        config = {"module_url_templates": ["https://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "hera")
        
        mock_match = Mock()
        mock_match.group.side_effect = ["hdf5", "hdf5_fortran_ver"]
        
        module_content = '''
local hdf5_fortran_ver = "1.12.2"
load(pathJoin("hdf5", hdf5_fortran_ver))
'''
        
        result = app._handle_pathjoin_upgradable_pattern(mock_match, module_content)
        
        assert result == ("hdf5", "1.12.2")

    @patch('requests.get')
    def test_unified_load_pattern_handles_all_cases(self, mock_get):
        """Test that the unified load pattern can handle pathJoin, simple, and versioned load patterns."""
        config = {
            "module_url_templates": ["http://example.com/ufs_test.intel.lua"],
            "install_path_regex": r'setenv\("UFS_MODEL", "([^"]+)"\)'
        }
        model_app = ModelApplication("test_app", config, "test_platform")
        
        # Mock module file content with all three load pattern types
        module_content = '''
-- UFS module file for test site
local mypkg_ver = os.getenv("mypkg_ver") or "1.2.3"
local otherpkg_ver = os.getenv("otherpkg_ver") or "2.0.0"

-- pathJoin pattern
load(pathJoin("mypkg", mypkg_ver))
load(pathJoin("otherpkg", otherpkg_ver))

-- Simple load pattern without version (should be ignored)
load("ufs_common")
load("stack-intel")

-- Versioned load pattern
load("versioned_pkg/4.5.6")
load("another_pkg/7.8.9")

-- Mixed cases to ensure robust parsing
load(pathJoin("complex_pkg", complex_pkg_ver))
local complex_pkg_ver = os.getenv("complex_pkg_ver") or "3.1.4"
'''
        
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.text = module_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Parse dependencies
        dependencies = model_app.parse_dependencies()
        
        # Convert to a dict for easier testing
        dep_dict = {dep['name']: dep['version'] for dep in dependencies}
        
        # Verify pathJoin patterns were processed
        assert 'mypkg' in dep_dict
        assert dep_dict['mypkg'] == '1.2.3'
        assert 'otherpkg' in dep_dict
        assert dep_dict['otherpkg'] == '2.0.0'
        
        # Verify versioned load patterns were processed
        assert 'versioned_pkg' in dep_dict
        assert dep_dict['versioned_pkg'] == '4.5.6'
        assert 'another_pkg' in dep_dict
        assert dep_dict['another_pkg'] == '7.8.9'
        
        # Verify complex_pkg was processed (even though var defined after load)
        assert 'complex_pkg' in dep_dict
        assert dep_dict['complex_pkg'] == '3.1.4'
        
        # Verify excluded patterns were not included
        excluded_names = [dep['name'] for dep in dependencies]
        assert 'ufs_common' not in excluded_names
        assert 'stack-intel' not in excluded_names
        
        # Verify all dependencies have the expected structure
        for dep in dependencies:
            assert 'name' in dep
            assert 'version' in dep
            assert 'variants' in dep
            assert 'raw_match' in dep
            assert dep['variants'] == ""  # Should be empty string by default

    @patch('requests.get')
    def test_unified_load_pattern_group_matching(self, mock_get):
        """Test that the regex groups are correctly matched for different pattern types."""
        config = {"module_url_templates": ["http://example.com/test.lua"]}
        model_app = ModelApplication("test_app", config, "test_platform")
        
        module_content = '''
-- Test specific group matching
local testpkg_ver = "1.0.0"
load(pathJoin("testpkg", testpkg_ver))
load("simple/2.0.0")
'''
        
        mock_response = Mock()
        mock_response.text = module_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        dependencies = model_app.parse_dependencies()
        
        # Should find both packages
        assert len(dependencies) == 2
        
        dep_names = [dep['name'] for dep in dependencies]
        assert 'testpkg' in dep_names
        assert 'simple' in dep_names
        
        # Check versions
        dep_dict = {dep['name']: dep['version'] for dep in dependencies}
        assert dep_dict['testpkg'] == '1.0.0'
        assert dep_dict['simple'] == '2.0.0'

    @patch('requests.get')
    def test_unified_load_pattern_filtering(self, mock_get):
        """Test that stack and ufs_common packages are properly filtered."""
        config = {"module_url_templates": ["http://example.com/test.lua"]}
        model_app = ModelApplication("test_app", config, "test_platform")
        
        module_content = '''
-- Test filtering
local good_pkg_ver = "1.0.0"
load(pathJoin("good_pkg", good_pkg_ver))
load(pathJoin("stack-intel", stack_intel_ver))
load(pathJoin("ufs_common", ufs_common_ver))
load("good_simple/2.0.0")
load("stack-gcc/system")
load("ufs_common/latest")
'''
        
        mock_response = Mock()
        mock_response.text = module_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        dependencies = model_app.parse_dependencies()
        
        # Should only find the good packages
        dep_names = [dep['name'] for dep in dependencies]
        assert 'good_pkg' in dep_names
        assert 'good_simple' in dep_names
        assert 'stack-intel' not in dep_names
        assert 'stack-gcc' not in dep_names
        assert 'ufs_common' not in dep_names
        
        assert len(dependencies) == 2

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
local netcdf_version = "4.9.2"
local hdf5_version = "1.12.2"
load("cmake/3.23.1")
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

    @patch('requests.get')
    @patch('os.path.exists')
    def test_get_applications_with_install_paths_success(self, mock_exists, mock_get):
        """Test get_applications_with_install_paths with valid applications."""
        # Mock file system existence check
        def mock_exists_side_effect(path):
            return path in ["/path/to/ufs", "/path/to/fms"]
        mock_exists.side_effect = mock_exists_side_effect
        
        # Mock HTTP responses for module files
        def mock_requests_side_effect(url, timeout=None):
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            
            if "ufs" in url:
                mock_response.text = '''setenv("UFS_WEATHER_MODEL_ROOT", "/path/to/ufs")'''
            elif "fms" in url:
                mock_response.text = '''setenv("FMS_ROOT", "/path/to/fms")'''
            else:
                mock_response.text = '''-- No install path'''
            return mock_response
        mock_get.side_effect = mock_requests_side_effect
        
        platform_config = {
            "model_applications": {
                "ufs_weather_model": {
                    "module_url_templates": ["https://example.com/ufs.lua"],
                    "install_path_regex": r'setenv\("UFS_WEATHER_MODEL_ROOT",\s*"([^"]+)"\)'
                },
                "fms": {
                    "module_url_templates": ["https://example.com/fms.lua"],
                    "install_path_regex": r'setenv\("FMS_ROOT",\s*"([^"]+)"\)'
                },
                "missing_app": {
                    "module_url_templates": ["https://example.com/missing.lua"],
                    "install_path_regex": r'setenv\("MISSING_ROOT",\s*"([^"]+)"\)'
                }
            }
        }
        
        manager = ModelApplicationManager(platform_config, "hera")
        results = manager.get_applications_with_install_paths()
        
        # Should return only apps with existing install paths
        assert len(results) == 2
        
        app_names = {app.name for app, path in results}
        install_paths = {path for app, path in results}
        
        assert "ufs_weather_model" in app_names
        assert "fms" in app_names
        assert "missing_app" not in app_names  # Path doesn't exist
        
        assert "/path/to/ufs" in install_paths
        assert "/path/to/fms" in install_paths

    @patch('requests.get')
    @patch('os.path.exists')
    def test_get_applications_with_install_paths_no_regex(self, mock_exists, mock_get):
        """Test get_applications_with_install_paths with apps that have no install_path_regex."""
        mock_exists.return_value = True
        mock_get.return_value = Mock()
        
        platform_config = {
            "model_applications": {
                "app_without_regex": {
                    "module_url_templates": ["https://example.com/app.lua"]
                    # No install_path_regex
                }
            }
        }
        
        manager = ModelApplicationManager(platform_config, "hera")
        results = manager.get_applications_with_install_paths()
        
        # Should return empty list since no install path can be extracted
        assert len(results) == 0

    @patch('requests.get')
    @patch('os.path.exists')
    def test_get_applications_with_install_paths_nonexistent_paths(self, mock_exists, mock_get):
        """Test get_applications_with_install_paths when install paths don't exist."""
        # Mock that paths don't exist
        mock_exists.return_value = False
        
        # Mock HTTP response with valid install path
        mock_response = Mock()
        mock_response.text = '''setenv("UFS_WEATHER_MODEL_ROOT", "/nonexistent/path")'''
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        platform_config = {
            "model_applications": {
                "ufs_weather_model": {
                    "module_url_templates": ["https://example.com/ufs.lua"],
                    "install_path_regex": r'setenv\("UFS_WEATHER_MODEL_ROOT",\s*"([^"]+)"\)'
                }
            }
        }
        
        manager = ModelApplicationManager(platform_config, "hera")
        results = manager.get_applications_with_install_paths()
        
        # Should return empty list since paths don't exist
        assert len(results) == 0

    @patch('os.path.exists')
    @patch('builtins.print')
    def test_get_applications_with_install_paths_with_exceptions(self, mock_print, mock_exists):
        """Test get_applications_with_install_paths when extract_install_path raises exceptions."""
        mock_exists.return_value = True
        
        platform_config = {
            "model_applications": {
                "failing_app": {
                    "module_url_templates": ["https://example.com/failing.lua"],
                    "install_path_regex": r'setenv\("FAILING_ROOT",\s*"([^"]+)"\)'
                }
            }
        }
        
        manager = ModelApplicationManager(platform_config, "hera")
        
        # Mock the extract_install_path method to raise an exception
        with patch.object(manager.applications[0], 'extract_install_path', side_effect=Exception("Test exception")):
            results = manager.get_applications_with_install_paths()
        
        # Should return empty list and print warning
        assert len(results) == 0
        mock_print.assert_called_once()
        assert "Warning: Failed to get install path for failing_app" in mock_print.call_args[0][0]

    def test_get_applications_with_install_paths_empty_config(self):
        """Test get_applications_with_install_paths with no model applications."""
        platform_config = {"model_applications": {}}
        
        manager = ModelApplicationManager(platform_config, "hera")
        results = manager.get_applications_with_install_paths()
        
        # Should return empty list
        assert len(results) == 0
