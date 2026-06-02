"""Tests for model application management."""

import re
import pytest
from unittest.mock import Mock, patch
from emcenvchainer.model_apps import ModelApplication, ModelApplicationManager


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
        assert choices[0]['name'] == "hera.intel.lua"
        assert choices[0]['url'] == "https://example.com/hera.intel.lua"
        assert choices[1]['name'] == "hera.gnu.lua"
        assert choices[1]['url'] == "https://example.com/hera.gnu.lua"

    @patch('requests.get')
    def test_get_upgradable_packages_success(self, mock_get):
        """Test successful parsing of upgradable packages from common module."""
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

        config = {"common_module_url": "https://example.com/ufs_common.lua"}
        app = ModelApplication("test_app", config, "hera")
        packages = app.get_upgradable_packages()

        package_names = {pkg['name'] for pkg in packages}
        assert 'netcdf' in package_names
        assert 'hdf5' in package_names
        assert 'cmake' in package_names
        assert 'numpy' in package_names
        assert 'scipy' in package_names

        netcdf_pkg = next(pkg for pkg in packages if pkg['name'] == 'netcdf')
        assert netcdf_pkg['version'] == "4.9.2"

        numpy_pkg = next(pkg for pkg in packages if pkg['name'] == 'numpy')
        assert numpy_pkg['version'] == "1.24.3"

    def test_get_upgradable_packages_no_common_url(self):
        """Test get_upgradable_packages when no common_module_url is configured."""
        app = ModelApplication("test_app", {}, "hera")
        assert app.get_upgradable_packages() == []

    @patch('requests.get')
    def test_get_upgradable_packages_shell_exports_success(self, mock_get):
        """Test parsing upgradable packages from shell export version files."""
        mock_response = Mock()
        mock_response.text = '''#! /usr/bin/env bash
export hdf5_ver=1.14.3
export netcdf_c_ver=4.9.2
export py_pyyaml_ver=6.0.2
export stack_python_ver=3.11.7
'''
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        config = {
            "package_versions_url": "https://example.com/spack.ver",
            "package_versions_format": "shell_exports",
        }

        app = ModelApplication("global_workflow", config, "ursa")
        packages = app.get_upgradable_packages()

        package_versions = {pkg['name']: pkg['version'] for pkg in packages}
        assert package_versions['hdf5'] == "1.14.3"
        assert package_versions['netcdf-c'] == "4.9.2"
        assert package_versions['py-pyyaml'] == "6.0.2"
        assert 'stack-python' not in package_versions

    @patch('requests.get')
    def test_get_upgradable_packages_rrfs_patterns(self, mock_get):
        """Test parsing upgradable packages from RRFS-style common module with inline os.getenv."""
        mock_response = Mock()
        mock_response.text = '''-- RRFS Common Module File
load(pathJoin("jasper", os.getenv("jasper_ver") or "2.0.32"))
load(pathJoin("libpng", os.getenv("libpng_ver") or "1.6.37"))
load(pathJoin("zlib", os.getenv("zlib_ver") or "1.2.13"))
load(pathJoin("hdf5", os.getenv("hdf5_ver") or "1.14.3"))
load(pathJoin("stack-intel", os.getenv("stack_intel_ver") or "2021.5.0"))
'''
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        config = {"common_module_url": "https://example.com/rrfs_common.lua"}
        app = ModelApplication("rrfs_app", config, "hera")
        packages = app.get_upgradable_packages()

        package_names = {pkg['name'] for pkg in packages}
        assert 'jasper' in package_names
        assert 'libpng' in package_names
        assert 'hdf5' in package_names
        assert 'zlib' not in package_names
        assert 'stack-intel' not in package_names

        jasper_pkg = next(pkg for pkg in packages if pkg['name'] == 'jasper')
        assert jasper_pkg['version'] == "2.0.32"

        hdf5_pkg = next(pkg for pkg in packages if pkg['name'] == 'hdf5')
        assert hdf5_pkg['version'] == "1.14.3"

    @patch('requests.get')
    def test_get_upgradable_packages_ufs_table_format(self, mock_get):
        """Test parsing upgradable packages from UFS table format in common module,
        including entries with varying amounts of trailing whitespace."""
        mock_response = Mock()
        mock_response.text = (
            '{["jasper"]          = "2.0.32" },\n'
            '{["zlib"]            = "1.2.13"  },\n'
            '{["crtm"]            = "2.4.0.1"},\n'
        )
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        config = {"common_module_url": "https://example.com/ufs_common.lua"}
        app = ModelApplication("test_app", config, "test_platform")
        packages = app.get_upgradable_packages()

        package_versions = {pkg['name']: pkg['version'] for pkg in packages}
        assert package_versions['jasper'] == "2.0.32"
        assert package_versions['zlib'] == "1.2.13"
        assert package_versions['crtm'] == "2.4.0.1"

    @patch('requests.get')
    def test_get_upgradable_packages_unsupported_format_raises(self, mock_get):
        """Test that get_upgradable_packages raises RuntimeError for unsupported format."""
        mock_response = Mock()
        mock_response.text = "some content"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        config = {
            "package_versions_url": "https://example.com/spack.ver",
            "package_versions_format": "toml",
        }
        app = ModelApplication("test_app", config, "hera")

        with pytest.raises(RuntimeError, match="Unsupported package_versions_format"):
            app.get_upgradable_packages()

    @patch('requests.get')
    def test_extract_install_path_success(self, mock_get):
        """Test successful extraction of install path from module file."""
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
        assert app.extract_install_path() == "/opt/apps/ufs/1.0"

    def test_extract_install_path_no_regex(self):
        """Test extract_install_path when no regex is configured."""
        config = {"module_url_templates": ["https://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "hera")
        assert app.extract_install_path() is None

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
        assert app.extract_install_path() is None

    def test_handle_version_variable_pattern(self):
        """Test _handle_version_variable_pattern extracts packages and filters stack entries."""
        config = {"module_url_templates": ["http://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "test_platform")
        pattern = r'([a-zA-Z0-9_]+)_ver\s*=\s*os\.getenv\("[^"]+"\)\s*or\s*"([^"]+)"'

        match = re.search(pattern, 'netcdf_ver = os.getenv("netcdf_ver") or "4.9.2"')
        assert app._handle_version_variable_pattern(match, "") == ('netcdf', '4.9.2')

        match = re.search(pattern, 'stack_intel_ver = os.getenv("stack_intel_ver") or "2021.5.0"')
        assert app._handle_version_variable_pattern(match, "") is None

    def test_handle_pathjoin_upgradable_pattern(self):
        """Test _handle_pathjoin_upgradable_pattern resolves version variables and handles missing ones."""
        config = {"module_url_templates": ["http://example.com/test.lua"]}
        app = ModelApplication("test_app", config, "test_platform")
        pattern = r'load\(pathJoin\("([^"]+)",\s*([^)]+)\)\)'

        match = re.search(pattern, 'load(pathJoin("netcdf", netcdf_ver))')
        assert app._handle_pathjoin_upgradable_pattern(match, 'netcdf_ver = "4.9.2"') == ('netcdf', '4.9.2')
        assert app._handle_pathjoin_upgradable_pattern(match, '') is None

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
        ),
        (
            # Test RRFS-style inline os.getenv patterns
            '''
load(pathJoin("jasper", os.getenv("jasper_ver") or "2.0.32"))
load(pathJoin("zlib", os.getenv("zlib_ver") or "1.2.13"))
load(pathJoin("libpng", os.getenv("libpng_ver") or "1.6.37"))
load(pathJoin("stack-intel", os.getenv("stack_intel_ver") or "2021.5.0"))
''',
            [('jasper', '2.0.32'), ('libpng', '1.6.37')],
            ['zlib', 'stack-intel']
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

        for name, version in expected_packages:
            assert name in dep_dict, f"Expected package {name} not found"
            assert dep_dict[name] == version, f"Package {name} has wrong version"

        for name in excluded_packages:
            assert name not in dep_dict, f"Package {name} should have been filtered"

    @patch('requests.get')
    def test_spack_stack_path_overrides_multiple(self, mock_get):
        """Test that multiple path overrides are applied correctly."""
        module_content = '''-- Test Module File
prepend_path("MODULEPATH", "/old/path1/modulefiles")
setenv("PATH2", "/old/path2/bin")
load("some-package")
'''
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = module_content
        mock_get.return_value = mock_response

        path_overrides = [
            {"old": "/old/path1", "new": "/new/path1"},
            {"old": "/old/path2", "new": "/new/path2"}
        ]
        app = ModelApplication("test_app", {"module_url_templates": ["https://example.com/test.lua"]},
                               "test_platform", spack_stack_path_overrides=path_overrides)

        downloaded_content = app.download_module_file()

        assert "/old/path1" not in downloaded_content
        assert "/old/path2" not in downloaded_content
        assert "/new/path1/modulefiles" in downloaded_content
        assert "/new/path2/bin" in downloaded_content

    @patch('requests.get')
    def test_spack_stack_path_overrides_none(self, mock_get):
        """Test that module content is unchanged when no overrides are configured."""
        module_content = '''-- Test Module File
prepend_path("MODULEPATH", "/some/path/modulefiles")
'''
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.text = module_content
        mock_get.return_value = mock_response

        app = ModelApplication("test_app", {"module_url_templates": ["https://example.com/test.lua"]},
                               "test_platform")
        assert app.download_module_file() == module_content

    @patch('requests.get')
    def test_download_module_file_raises_on_request_failure(self, mock_get):
        """Test that download_module_file raises RuntimeError when the HTTP request fails."""
        from requests.exceptions import RequestException
        mock_get.side_effect = RequestException("connection refused")

        app = ModelApplication("test_app", {"module_url_templates": ["https://example.com/test.lua"]},
                               "test_platform")

        with pytest.raises(RuntimeError):
            app.download_module_file()


class TestModelApplicationManager:
    """Test ModelApplicationManager class."""

    def test_manager_initialization(self):
        """Test ModelApplicationManager initialization."""
        platform_config = {
            "model_applications": {
                "ufs_weather_model": {
                    "module_url_templates": ["https://example.com/ufs.lua"]
                }
            }
        }
        applications_config = {
            "ufs_weather_model": {
                "name": "UFS Weather Model",
                "common_module_url": "https://example.com/ufs_common.lua"
            }
        }

        manager = ModelApplicationManager(platform_config, "hera", applications_config)

        assert manager.platform_config == platform_config
        assert manager.platform_name == "hera"
        assert len(manager.applications) == 1
        assert manager.applications[0].name == "ufs_weather_model"
        assert manager.applications[0].config["common_module_url"] == "https://example.com/ufs_common.lua"

    def test_manager_passes_path_overrides_to_applications(self):
        """Test that ModelApplicationManager passes path overrides to ModelApplication instances."""
        platform_config = {
            "spack_stack_path_overrides": [
                {"old": "/old/path", "new": "/new/path"}
            ],
            "model_applications": {
                "test_app": {
                    "module_url_templates": ["https://example.com/test.lua"]
                }
            }
        }

        manager = ModelApplicationManager(platform_config, "test_platform")
        apps = manager.applications

        assert len(apps) == 1
        assert apps[0].spack_stack_path_overrides == [{"old": "/old/path", "new": "/new/path"}]

    @patch('requests.get')
    def test_full_workflow_with_upgradable_packages(self, mock_get):
        """Test the full workflow including module URL selection and upgradable packages."""
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
                    "module_url_templates": [
                        "https://example.com/ufs_hera.intel.lua",
                        "https://example.com/ufs_hera.gnu.lua"
                    ],
                    "install_path_regex": r'setenv\("UFS_WEATHER_MODEL_ROOT",\s*"([^"]+)"\)'
                }
            }
        }
        applications_config = {
            "ufs_weather_model": {
                "name": "UFS Weather Model",
                "common_module_url": "https://example.com/ufs_common.lua"
            }
        }

        manager = ModelApplicationManager(platform_config, "hera", applications_config)
        app = manager.applications[0]

        choices = app.get_module_url_choices()
        assert len(choices) == 2
        assert choices[0]['name'] == "ufs_hera.intel.lua"
        assert choices[1]['name'] == "ufs_hera.gnu.lua"

        upgradable_packages = app.get_upgradable_packages()
        assert len(upgradable_packages) == 3
        package_names = {pkg['name'] for pkg in upgradable_packages}
        assert 'netcdf' in package_names
        assert 'hdf5' in package_names
        assert 'cmake' in package_names

        dependencies = app.parse_dependencies()
        dep_names = {dep['name'] for dep in dependencies}
        assert 'netcdf' in dep_names
        assert 'hdf5' in dep_names

        netcdf_dep = next(dep for dep in dependencies if dep['name'] == 'netcdf')
        netcdf_upgradable = next(pkg for pkg in upgradable_packages if pkg['name'] == 'netcdf')
        assert netcdf_dep['version'] == "4.8.1"        # From module file
        assert netcdf_upgradable['version'] == "4.9.2"  # From common module file
