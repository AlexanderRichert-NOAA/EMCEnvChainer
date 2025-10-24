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

    def test_handle_depends_on_pattern(self):
        """Test _handle_depends_on_pattern method."""
        config = {"module_url_templates": ["http://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "test_platform")
        
        match = Mock()
        match.group.side_effect = lambda x: {0: 'depends_on("netcdf@4.9.2")', 1: 'netcdf', 2: '4.9.2'}[x]
        
        result = app._handle_depends_on_pattern(match, "")
        
        assert result == ('netcdf', '4.9.2')

    def test_handle_version_variable_pattern(self):
        """Test _handle_version_variable_pattern method."""
        config = {"module_url_templates": ["http://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "test_platform")
        
        match = Mock()
        match.group.side_effect = lambda x: {1: 'netcdf_ver', 2: '4.9.2'}[x]
        
        result = app._handle_version_variable_pattern(match, "")
        
        assert result == ('netcdf', '4.9.2')
    
    def test_handle_version_variable_pattern_filters_stack(self):
        """Test _handle_version_variable_pattern filters stack packages."""
        config = {"module_url_templates": ["http://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "test_platform")
        
        match = Mock()
        match.group.side_effect = lambda x: {1: 'stack_intel_ver', 2: '2021.5.0'}[x]
        
        result = app._handle_version_variable_pattern(match, "")
        
        assert result is None

    def test_handle_ufs_table_pattern(self):
        """Test _handle_ufs_table_pattern method."""
        config = {"module_url_templates": ["http://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "test_platform")
        
        match = Mock()
        match.group.side_effect = lambda x: {1: 'netcdf', 2: '4.9.2'}[x]
        
        result = app._handle_ufs_table_pattern(match, "")
        
        assert result == ('netcdf', '4.9.2')

    def test_handle_pathjoin_upgradable_pattern(self):
        """Test _handle_pathjoin_upgradable_pattern method."""
        config = {"module_url_templates": ["http://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "test_platform")
        
        module_content = 'netcdf_ver = "4.9.2"'
        match = Mock()
        match.group.side_effect = lambda x: {1: 'netcdf', 2: 'netcdf_ver'}[x]
        
        result = app._handle_pathjoin_upgradable_pattern(match, module_content)
        
        assert result == ('netcdf', '4.9.2')

    def test_handle_pathjoin_upgradable_pattern_no_version_found(self):
        """Test _handle_pathjoin_upgradable_pattern when version variable not found."""
        config = {"module_url_templates": ["http://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "test_platform")
        
        module_content = ''
        match = Mock()
        match.group.side_effect = lambda x: {1: 'netcdf', 2: 'netcdf_ver'}[x]
        
        result = app._handle_pathjoin_upgradable_pattern(match, module_content)
        
        assert result is None

    @patch('requests.get')
    @pytest.mark.parametrize("module_content,expected_packages,excluded_packages", [
        (
            # Test pathJoin, simple load, and versioned load patterns
            '''
local mypkg_ver = "1.2.3"
load(pathJoin("mypkg", mypkg_ver))
load("simple_pkg/4.5.6")
''',
            [('mypkg', '1.2.3'), ('simple_pkg', '4.5.6')],
            []
        ),
        (
            # Test filtering of stack and ufs_common packages
            '''
local good_pkg_ver = "1.0.0"
load(pathJoin("good_pkg", good_pkg_ver))
load(pathJoin("stack-intel", stack_intel_ver))
load(pathJoin("ufs_common", ufs_common_ver))
load("valid_pkg/2.0.0")
''',
            [('good_pkg', '1.0.0'), ('valid_pkg', '2.0.0')],
            ['stack-intel', 'ufs_common']
        ),
        (
            # Test variable defined after load statement (complex parsing)
            '''
load(pathJoin("complex_pkg", complex_pkg_ver))
local complex_pkg_ver = "3.1.4"
load("another_pkg/5.0.0")
''',
            [('complex_pkg', '3.1.4'), ('another_pkg', '5.0.0')],
            []
        )
    ])
    def test_parse_dependencies_pattern_handling(self, mock_get, module_content, expected_packages, excluded_packages):
        """Test parse_dependencies handles various load patterns and filters correctly."""
        config = {"module_url_templates": ["http://example.com/test.lua"]}
        model_app = ModelApplication("test_app", config, "test_platform")
        
        mock_response = Mock()
        mock_response.text = module_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        dependencies = model_app.parse_dependencies()
        dep_dict = {dep['name']: dep['version'] for dep in dependencies}
        
        # Verify expected packages are present with correct versions
        for name, version in expected_packages:
            assert name in dep_dict, f"Expected package {name} not found"
            assert dep_dict[name] == version, f"Package {name} has wrong version"
        
        # Verify excluded packages are not present
        for name in excluded_packages:
            assert name not in dep_dict, f"Package {name} should have been filtered"

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
        app = manager.applications[0]
        
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
