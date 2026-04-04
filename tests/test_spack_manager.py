"""Unit tests for SpackManager class."""

import os
import tempfile
import shutil
from pathlib import Path
from unittest import mock
from unittest.mock import Mock, patch, MagicMock, mock_open
import pytest
import subprocess
import requests
from subprocess import CompletedProcess
from ruamel.yaml import YAML

from emcenvchainer.spack_manager import SpackManager
from emcenvchainer.config import Config


class TestSpackManager:
    """Test cases for SpackManager class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = Mock(spec=Config)
        config.get.return_value = {
            "base_url": "https://github.com/JCSDA/spack.git",
            "branch": "develop"
        }
        return config
    
    @pytest.fixture
    def temp_spack_root(self):
        """Create a temporary spack root directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            spack_root = Path(temp_dir) / "spack"
            spack_bin = spack_root / "bin"
            spack_bin.mkdir(parents=True)
            spack_exe = spack_bin / "spack"
            spack_exe.touch()
            spack_exe.chmod(0o755)
            yield str(spack_root)
    
    @pytest.fixture
    def spack_manager(self, temp_spack_root, mock_config):
        """Create a SpackManager instance for testing."""
        return SpackManager(temp_spack_root, mock_config)
    
    def test_init_creates_manager_with_correct_paths(self, temp_spack_root, mock_config):
        """Test that SpackManager initializes with correct paths."""
        manager = SpackManager(temp_spack_root, mock_config)
        
        assert manager.spack_root == Path(temp_spack_root)
        assert manager.config == mock_config
        assert manager.spack_exe == Path(temp_spack_root) / "bin" / "spack"
        assert manager.logger is None
        assert manager.pending_recipes == {}
        assert manager.pending_checksums == []
        assert manager.pending_git_commits == []
    
    def test_init_fails_with_nonexistent_spack_exe(self, mock_config):
        """Test that SpackManager fails to initialize with nonexistent spack executable."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(AssertionError, match="Spack executable not found"):
                SpackManager(temp_dir, mock_config)
    
    def test_setup_logging_creates_log_directory_and_file(self, spack_manager):
        """Test that setup_logging creates the logs directory and log file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = temp_dir
            spack_manager.setup_logging(env_path)
            
            # Check that logs directory was created
            logs_dir = Path(env_path) / "logs"
            assert logs_dir.exists()
            
            # Check that log file was created
            log_files = list(logs_dir.glob("emcenvchainer_*.log"))
            assert len(log_files) == 1
            
            # Check that logger was set up
            assert spack_manager.logger is not None
    
    def test_log_and_print_logs_and_prints_message(self, spack_manager, capsys):
        """Test that _log_and_print logs message and prints to console."""
        with tempfile.TemporaryDirectory() as temp_dir:
            spack_manager.setup_logging(temp_dir)
            
            test_message = "Test log message"
            spack_manager._log_and_print(test_message)
            
            # Check console output
            captured = capsys.readouterr()
            assert test_message in captured.out
    
    @pytest.mark.parametrize("pkg,expected_spec", [
        ({"name": "cmake"}, "cmake"),
        ({"name": "cmake", "version": "3.20.0"}, "cmake@=3.20.0"),
        ({"name": "cmake", "variants": "+shared +ssl"}, "cmake+shared +ssl"),
        ({"name": "cmake", "variants": "shared ssl"}, "cmake shared ssl"),
        ({"name": "cmake", "version": "3.20.0", "variants": "+shared +ssl"}, "cmake@=3.20.0+shared +ssl"),
    ])
    def test_build_spec_string(self, spack_manager, pkg, expected_spec):
        """Test _build_spec_string with various package configurations."""
        result = spack_manager._build_spec_string(pkg)
        assert result == expected_spec
    
    def test_build_spec_string_with_upstream_hash(self, spack_manager):
        """Test _build_spec_string includes upstream hash when present."""
        pkg = {"name": "cmake", "version": "3.20.0", "upstream_hash": "abc1234"}
        result = spack_manager._build_spec_string(pkg)
        assert result == "cmake@=3.20.0 /abc1234"
    
    def test_build_spec_string_with_hash_and_variants(self, spack_manager):
        """Test _build_spec_string with both variants and upstream hash."""
        pkg = {
            "name": "cmake",
            "version": "3.20.0",
            "variants": "+shared +ssl",
            "upstream_hash": "xyz9876"
        }
        result = spack_manager._build_spec_string(pkg)
        assert result == "cmake@=3.20.0+shared +ssl /xyz9876"
    
    def test_add_pending_recipe_new_package(self, spack_manager):
        """Test adding a pending recipe for a new package."""
        spack_manager.add_pending_recipe("test-pkg", "1.0.0", needs_manual_edit=True)
        
        assert "test-pkg" in spack_manager.pending_recipes
        assert len(spack_manager.pending_recipes["test-pkg"]) == 1
        
        recipe = spack_manager.pending_recipes["test-pkg"][0]
        assert recipe["version"] == "1.0.0"
        assert recipe["needs_manual_edit"] is True
    
    def test_add_pending_recipe_existing_package(self, spack_manager):
        """Test adding multiple versions to existing package."""
        spack_manager.add_pending_recipe("test-pkg", "1.0.0")
        spack_manager.add_pending_recipe("test-pkg", "2.0.0")
        
        assert len(spack_manager.pending_recipes["test-pkg"]) == 2
        versions = [r["version"] for r in spack_manager.pending_recipes["test-pkg"]]
        assert "1.0.0" in versions
        assert "2.0.0" in versions
    
    def test_add_pending_checksum(self, spack_manager):
        """Test adding a pending checksum operation."""
        spack_manager.add_pending_checksum("test-pkg", "1.0.0")
        
        assert len(spack_manager.pending_checksums) == 1
        checksum = spack_manager.pending_checksums[0]
        assert checksum["package_name"] == "test-pkg"
        assert checksum["version"] == "1.0.0"
    
    def test_add_pending_git_commit(self, spack_manager):
        """Test adding a pending git commit operation."""
        spack_manager.add_pending_git_commit("test-pkg", "1.0.0", "abc123def456")
        
        assert len(spack_manager.pending_git_commits) == 1
        commit = spack_manager.pending_git_commits[0]
        assert commit["package_name"] == "test-pkg"
        assert commit["version"] == "1.0.0"
        assert commit["commit_hash"] == "abc123def456"
    
    def test_get_local_package_path(self, spack_manager):
        """Test getting local package path."""
        result = spack_manager.get_local_package_path("cmake")
        expected = str(spack_manager.spack_root / "var" / "spack" / "repos" / "builtin" / "packages" / "cmake" / "package.py")
        assert result == expected
    
    @patch('subprocess.run')
    def test_run_spack_command_success(self, mock_subprocess, spack_manager):
        """Test successful spack command execution."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success output"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result
        
        result = spack_manager._run_spack_command(['--version'])
        
        assert result.returncode == 0
        assert result.stdout == "Success output"
        mock_subprocess.assert_called_once()
    
    @patch('subprocess.run')
    def test_run_spack_command_with_logging(self, mock_subprocess, spack_manager):
        """Test spack command execution with logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            spack_manager.setup_logging(temp_dir)
            
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Success output"
            mock_result.stderr = ""
            mock_subprocess.return_value = mock_result
            
            result = spack_manager._run_spack_command(['--version'])
            
            assert result.returncode == 0
            # Verify logging captured the command
            assert spack_manager.logger is not None
    
    @patch('subprocess.run')
    def test_run_spack_command_failure(self, mock_subprocess, spack_manager):
        """Test failed spack command execution."""
        mock_subprocess.side_effect = Exception("Command failed")
        
        with pytest.raises(RuntimeError, match="Failed to run spack command"):
            spack_manager._run_spack_command(['--version'])
    
    def test_find_upstream_env_path_with_install_suffix(self, spack_manager):
        """Test finding upstream environment path when path ends with 'install'."""
        upstream_path = "/path/to/env/install"
        result = spack_manager._find_upstream_env_path(upstream_path)
        expected = Path("/path/to/env")
        assert result == expected
    
    def test_find_upstream_env_path_without_install_suffix(self, spack_manager):
        """Test finding upstream environment path when path doesn't end with 'install'."""
        upstream_path = "/path/to/env"
        result = spack_manager._find_upstream_env_path(upstream_path)
        expected = Path("/path/to/env")
        assert result == expected
    
    @pytest.mark.parametrize("status_code,response_text,exception,expected_result", [
        (200, 'version("1.0.0", sha256="abc123")', None, True),
        (200, 'version("2.0.0", sha256="def456")', None, False),
        (404, '', None, False),
        (None, None, Exception("Network error"), False),
    ])
    @patch('requests.get')
    def test_check_version_in_remote_repo(self, mock_get, spack_manager, status_code, response_text, exception, expected_result):
        """Test version checking in remote repository with various scenarios."""
        if exception:
            mock_get.side_effect = exception
        else:
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_response.text = response_text
            mock_get.return_value = mock_response
        
        result = spack_manager.check_version_in_remote_repo("test-pkg", "1.0.0")
        assert result == expected_result
    
    @patch('shutil.copytree')
    def test_copy_site_common_dirs_success(self, mock_copytree, spack_manager):
        """Test successful copying of site and common directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            spack_manager.setup_logging(temp_dir)
            
            upstream_env_path = Path(temp_dir) / "upstream"
            new_env_path = Path(temp_dir) / "new"
            
            # Create upstream site directory
            upstream_site = upstream_env_path / "site"
            upstream_site.mkdir(parents=True)
            
            new_env_path.mkdir()
            
            spack_manager._copy_site_common_dirs(upstream_env_path, new_env_path)
            
            # Should be called for site directory
            assert mock_copytree.called
    
    def test_copy_site_common_dirs_no_upstream_dirs(self, spack_manager):
        """Test copying when upstream directories don't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            spack_manager.setup_logging(temp_dir)
            
            upstream_env_path = Path(temp_dir) / "upstream"
            new_env_path = Path(temp_dir) / "new"
            
            upstream_env_path.mkdir()
            new_env_path.mkdir()
            
            # Should not raise exception
            spack_manager._copy_site_common_dirs(upstream_env_path, new_env_path)
    
    @patch('subprocess.run')
    def test_check_package_version_exists_success(self, mock_subprocess, spack_manager):
        """Test successful package version existence check."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "==> Safe versions:\n  1.0.0  2.0.0  3.0.0"
        mock_subprocess.return_value = mock_result
        
        with patch.object(spack_manager, '_run_spack_command', return_value=mock_result):
            result = spack_manager.check_package_version_exists("test-pkg", "2.0.0")
            assert result is True
    
    @patch('subprocess.run')
    def test_check_package_version_exists_not_found(self, mock_subprocess, spack_manager):
        """Test package version not found."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "==> Safe versions:\n  1.0.0  3.0.0"
        mock_subprocess.return_value = mock_result
        
        with patch.object(spack_manager, '_run_spack_command', return_value=mock_result):
            result = spack_manager.check_package_version_exists("test-pkg", "2.0.0")
            assert result is False
    
    @patch('subprocess.run')
    def test_check_package_version_exists_package_not_found(self, mock_subprocess, spack_manager):
        """Test package not found at all."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result
        
        with patch.object(spack_manager, '_run_spack_command', return_value=mock_result):
            result = spack_manager.check_package_version_exists("nonexistent-pkg", "1.0.0")
            assert result is False

    def test_check_package_exists_success(self, spack_manager):
        """Test package existence check when package exists."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "hdf5\nnetcdf-c\ncmake\n"
        upstream_install_path = "/path/to/spack-stack-1.2.3/envs/testenv/install/"

        with patch.object(spack_manager, '_run_spack_command', return_value=mock_result):
            assert spack_manager.check_package_exists("hdf5", upstream_install_path) is True

    def test_check_package_exists_not_found(self, spack_manager):
        """Test package existence check when package does not exist."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "hdf5\nnetcdf-c\ncmake\n"
        upstream_install_path = "/path/to/spack-stack-1.2.3/envs/testenv/install/"

        with patch.object(spack_manager, '_run_spack_command', return_value=mock_result):
            assert spack_manager.check_package_exists("not-a-real-package", upstream_install_path) is False

    def test_check_package_exists_uses_cached_find_results(self, spack_manager):
        """Test package existence checks use cached package list from a single find call."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "hdf5\nnetcdf-c\n"
        upstream_install_path = "/path/to/spack-stack-1.2.3/envs/testenv/install/"

        with patch.object(spack_manager, '_run_spack_command', return_value=mock_result) as mock_run:
            assert spack_manager.check_package_exists("hdf5", upstream_install_path) is True
            assert spack_manager.check_package_exists("netcdf-c", upstream_install_path) is True
            assert spack_manager.check_package_exists("esmf", upstream_install_path) is False

            mock_run.assert_called_once_with(
                ['-e', '/path/to/spack-stack-1.2.3/envs/testenv', 'find', '--format', '{name}'],
                vars={'SPACK_STACK_DIR': '/path/to/spack-stack-1.2.3'},
            )

    def test_check_package_exists_normalizes_install_path_to_env(self, spack_manager):
        """Test install path input is normalized to the parent env path for spack -e."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "hdf5\n"

        with patch.object(spack_manager, '_run_spack_command', return_value=mock_result) as mock_run:
            assert (
                spack_manager.check_package_exists(
                    "hdf5",
                    "/path/to/spack-stack-1.2.3/envs/testenv/install/",
                )
                is True
            )

            mock_run.assert_called_once_with(
                [
                    '-e',
                    '/path/to/spack-stack-1.2.3/envs/testenv',
                    'find',
                    '--format',
                    '{name}',
                ],
                vars={'SPACK_STACK_DIR': '/path/to/spack-stack-1.2.3'},
            )

    def test_check_package_exists_raises_without_upstream_path(self, spack_manager):
        """Test package existence check fails fast when upstream path is missing."""
        with pytest.raises(ValueError, match="upstream_env_path is required"):
            spack_manager.check_package_exists("hdf5", "")

    def test_check_package_exists_hyphen_underscore_normalization(self, spack_manager):
        """Test that hyphen/underscore variants are matched interchangeably."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "netcdf-c\nwrf_io\n"
        upstream_install_path = "/path/to/spack-stack-1.2.3/envs/testenv/install/"

        with patch.object(spack_manager, '_run_spack_command', return_value=mock_result):
            # Package stored with hyphen, queried with underscore
            assert spack_manager.check_package_exists("netcdf_c", upstream_install_path) is True
            # Package stored with underscore, queried with hyphen
            assert spack_manager.check_package_exists("wrf-io", upstream_install_path) is True
            # Exact match still works
            assert spack_manager.check_package_exists("netcdf-c", upstream_install_path) is True
            # Non-existent package still returns False
            assert spack_manager.check_package_exists("esmf", upstream_install_path) is False

    def test_get_canonical_package_name_alias_groups(self, spack_manager):
        """Test that known package aliases resolve to whichever form is in Spack."""
        mock_result = Mock()
        mock_result.returncode = 0
        # Spack env has gsi-ncdiag (not ncdiag) and ecmwf-atlas (not atlas)
        mock_result.stdout = "gsi-ncdiag\necmwf-atlas\nhdf5\n"
        upstream_path = "/path/to/spack-stack-1.2.3/envs/testenv/install/"

        with patch.object(spack_manager, '_run_spack_command', return_value=mock_result):
            # Module file uses short alias -> resolved to Spack canonical name
            assert spack_manager.get_canonical_package_name("ncdiag", upstream_path) == "gsi-ncdiag"
            assert spack_manager.get_canonical_package_name("atlas", upstream_path) == "ecmwf-atlas"
            # Spack canonical name still resolves to itself
            assert spack_manager.get_canonical_package_name("gsi-ncdiag", upstream_path) == "gsi-ncdiag"
            assert spack_manager.get_canonical_package_name("ecmwf-atlas", upstream_path) == "ecmwf-atlas"
            # Unrelated packages unaffected
            assert spack_manager.get_canonical_package_name("hdf5", upstream_path) == "hdf5"
            assert spack_manager.get_canonical_package_name("esmf", upstream_path) is None

    def test_check_package_exists_raises_when_find_fails(self, spack_manager):
        """Test package existence check fails fast when spack find command fails."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "spack find failed"

        with patch.object(spack_manager, '_run_spack_command', return_value=mock_result):
            with pytest.raises(RuntimeError, match="Failed to list packages"):
                spack_manager.check_package_exists("hdf5", "/path/to/spack-stack-1.2.3/envs/testenv/install/modulefiles/Core/")
    
    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_process_pending_recipes_empty(self, mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_recipes with no pending recipes."""
        # Ensure no pending recipes
        spack_manager.pending_recipes = {}
        
        result = spack_manager._process_pending_recipes("/test/env")
        
        assert result == []
        mock_mkdir.assert_not_called()
        mock_file.assert_not_called()

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch.object(SpackManager, '_fetch_recipe_content')
    @patch.object(SpackManager, '_fetch_and_write_all_remote_files')
    def test_process_pending_recipes_remote_recipe(self, mock_fetch_files, mock_fetch_content, 
                                                 mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_recipes with remote recipe."""
        # Mock remote recipe content
        mock_fetch_content.return_value = "# Remote recipe content"
        mock_fetch_files.return_value = None
        
        # Add a pending recipe that's found in remote
        spack_manager.add_pending_recipe(
            "test-pkg", "1.0.0", 
            found_in_remote=True,
            needs_manual_edit=True
        )
        
        result = spack_manager._process_pending_recipes("/test/env")
        
        # Should return one package for editing
        assert len(result) == 1
        pkg = result[0]
        assert pkg['package_name'] == "test-pkg"
        assert pkg['version'] == "1.0.0"
        assert pkg['found_in_remote'] is True
        assert "/test/env/envrepo/packages/test-pkg/package.py" in pkg['recipe_path']
        
        # Should have written the remote recipe
        mock_file.assert_called()
        mock_fetch_content.assert_called_with("test-pkg")
        mock_fetch_files.assert_called_with("test-pkg", mock.ANY)

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch.object(SpackManager, '_fetch_and_write_package_directory')
    def test_process_pending_recipes_local_copy(self, mock_fetch_local, mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_recipes with local copy."""
        mock_fetch_local.return_value = True
        
        # Add a pending recipe that needs manual edit and local copy
        spack_manager.add_pending_recipe(
            "test-pkg", "1.0.0",
            needs_manual_edit=True,
            use_local_copy=True,
            found_in_local=True
        )
        
        result = spack_manager._process_pending_recipes("/test/env")
        
        # Should return one package for editing
        assert len(result) == 1
        pkg = result[0]
        assert pkg['package_name'] == "test-pkg"
        assert pkg['version'] == "1.0.0"
        assert pkg['use_local_copy'] is True
        assert pkg['found_in_local'] is True
        assert pkg['found_in_remote'] is False
        
        # Should have fetched from local installation
        mock_fetch_local.assert_called_once()

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_process_pending_recipes_provided_content(self, mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_recipes with provided recipe content."""
        recipe_content = "# Custom recipe content"
        
        # Add a pending recipe with provided content
        spack_manager.add_pending_recipe(
            "test-pkg", "1.0.0",
            recipe_content=recipe_content,
            needs_manual_edit=True
        )
        
        result = spack_manager._process_pending_recipes("/test/env")
        
        # Should return one package for editing
        assert len(result) == 1
        pkg = result[0]
        assert pkg['package_name'] == "test-pkg"
        assert pkg['version'] == "1.0.0"
        
        # Should have written the provided content
        mock_file.assert_called()
        handle = mock_file()
        handle.write.assert_called_with(recipe_content)

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch.object(SpackManager, '_fetch_and_write_package_directory')
    def test_process_pending_recipes_fallback_local(self, mock_fetch_local, mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_recipes fallback to local installation."""
        mock_fetch_local.return_value = True
        
        # Add a pending recipe without remote/local flags (should fallback to local)
        spack_manager.add_pending_recipe("test-pkg", "1.0.0")
        
        result = spack_manager._process_pending_recipes("/test/env")
        
        # Should not return packages for editing (no manual edit requested)
        assert len(result) == 0
        
        # Should have tried to fetch from local installation
        mock_fetch_local.assert_called_once()

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch.object(SpackManager, '_fetch_recipe_content')
    def test_process_pending_recipes_remote_fetch_fails(self, mock_fetch_content, mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_recipes when remote recipe fetch fails."""
        mock_fetch_content.return_value = None  # Simulate fetch failure
        
        # Add a pending recipe that's found in remote
        spack_manager.add_pending_recipe(
            "test-pkg", "1.0.0",
            found_in_remote=True,
            needs_manual_edit=True
        )
        
        with patch.object(spack_manager, '_log_and_print') as mock_log:
            result = spack_manager._process_pending_recipes("/test/env")
        
        # Should return empty list due to fetch failure (exception caught)
        assert len(result) == 0
        
        # Should have logged error for the exception
        mock_log.assert_any_call("✗ Error adding test-pkg@1.0.0: Could not obtain recipe for test-pkg from any source", "error")

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch.object(SpackManager, '_fetch_and_write_package_directory')
    def test_process_pending_recipes_local_copy_fails(self, mock_fetch_local, mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_recipes when local copy fails."""
        mock_fetch_local.return_value = False  # Simulate copy failure
        
        # Add a pending recipe that needs manual edit and local copy (no remote allowed)
        spack_manager.add_pending_recipe(
            "test-pkg", "1.0.0",
            needs_manual_edit=True,
            use_local_copy=True
        )
        
        with patch.object(spack_manager, '_log_and_print') as mock_log:
            result = spack_manager._process_pending_recipes("/test/env")
        
        # Should return empty list due to copy failure (exception caught)
        assert len(result) == 0
        
        # Should have logged error for the exception
        mock_log.assert_any_call("✗ Error adding test-pkg@1.0.0: Could not obtain recipe for test-pkg from any source", "error")

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_process_pending_recipes_exception_handling(self, mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_recipes exception handling."""
        # Make mkdir raise an exception
        mock_mkdir.side_effect = OSError("Permission denied")
        
        # Add a pending recipe
        spack_manager.add_pending_recipe("test-pkg", "1.0.0")
        
        with patch.object(spack_manager, '_log_and_print') as mock_log:
            result = spack_manager._process_pending_recipes("/test/env")
        
        # Should return empty list due to exception
        assert len(result) == 0
        
        # Should have logged error
        mock_log.assert_any_call("✗ Error adding test-pkg@1.0.0: Permission denied", "error")

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch.object(SpackManager, '_fetch_recipe_content')
    @patch.object(SpackManager, '_fetch_and_write_all_remote_files')
    def test_process_pending_recipes_multiple_packages(self, mock_fetch_files, mock_fetch_content,
                                                      mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_recipes with multiple packages."""
        mock_fetch_content.return_value = "# Recipe content"
        mock_fetch_files.return_value = None
        
        # Add multiple pending recipes
        spack_manager.add_pending_recipe("pkg1", "1.0.0", found_in_remote=True, needs_manual_edit=True)
        spack_manager.add_pending_recipe("pkg1", "2.0.0", found_in_remote=True, needs_manual_edit=False)
        spack_manager.add_pending_recipe("pkg2", "1.0.0", found_in_remote=True, needs_manual_edit=True)
        
        result = spack_manager._process_pending_recipes("/test/env")
        
        # Should return packages that need manual editing (pkg1@1.0.0 and pkg2@1.0.0)
        assert len(result) == 2
        
        pkg_versions = {(pkg['package_name'], pkg['version']) for pkg in result}
        assert ("pkg1", "1.0.0") in pkg_versions
        assert ("pkg2", "1.0.0") in pkg_versions
        assert ("pkg1", "2.0.0") not in pkg_versions  # No manual edit requested
        
        # Should clear pending recipes after processing
        assert len(spack_manager.pending_recipes) == 0

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    def test_process_pending_checksums_empty(self, mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_checksums with no pending checksums."""
        # Ensure no pending checksums
        spack_manager.pending_checksums = []
        
        result = spack_manager._process_pending_checksums("/test/env")
        
        assert result == []
        mock_mkdir.assert_not_called()
        mock_file.assert_not_called()

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch('subprocess.run')
    @patch.object(SpackManager, '_fetch_and_write_package_directory')
    def test_process_pending_checksums_success(self, mock_fetch_local, mock_subprocess, 
                                             mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_checksums with successful checksum operation."""
        mock_fetch_local.return_value = True
        
        # Mock successful subprocess result
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result
        
        # Add a pending checksum
        spack_manager.add_pending_checksum("test-pkg", "1.0.0")
        
        result = spack_manager._process_pending_checksums("/test/env")
        
        # Should return one package for editing
        assert len(result) == 1
        pkg = result[0]
        assert pkg['package_name'] == "test-pkg"
        assert pkg['version'] == "1.0.0"
        assert pkg['operation'] == 'checksum'
        assert pkg['use_local_copy'] is True
        assert pkg['found_in_local'] is True
        assert pkg['found_in_remote'] is False
        assert "/test/env/envrepo/packages/test-pkg/package.py" in pkg['recipe_path']
        
        # Should have run spack checksum command
        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0][0]
        assert 'checksum' in args
        assert '--add-to-package' in args
        assert 'test-pkg' in args
        assert '1.0.0' in args
        
        # Should clear pending checksums
        assert len(spack_manager.pending_checksums) == 0

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch('subprocess.run')
    @patch.object(SpackManager, '_fetch_and_write_package_directory')
    @patch.object(SpackManager, '_fetch_recipe_content')
    def test_process_pending_checksums_fallback_remote(self, mock_fetch_content, mock_fetch_local, 
                                                      mock_subprocess, mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_checksums with fallback to remote recipe."""
        mock_fetch_local.return_value = False  # Local fetch fails
        mock_fetch_content.return_value = "# Remote recipe content"
        
        # Mock successful subprocess result
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result
        
        # Add a pending checksum
        spack_manager.add_pending_checksum("test-pkg", "1.0.0")
        
        result = spack_manager._process_pending_checksums("/test/env")
        
        # Should return one package for editing
        assert len(result) == 1
        pkg = result[0]
        assert pkg['package_name'] == "test-pkg"
        assert pkg['operation'] == 'checksum'
        
        # Should have tried local first, then fetched from remote
        mock_fetch_local.assert_called_once()
        mock_fetch_content.assert_called_once_with("test-pkg")
        
        # Should have written remote content
        mock_file.assert_called()
        handle = mock_file()
        handle.write.assert_called_with("# Remote recipe content")

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch('subprocess.run')
    @patch.object(SpackManager, '_fetch_and_write_package_directory')
    @patch.object(SpackManager, '_fetch_recipe_content')
    def test_process_pending_checksums_no_recipe_available(self, mock_fetch_content, mock_fetch_local,
                                                          mock_subprocess, mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_checksums when no recipe is available."""
        mock_fetch_local.return_value = False
        mock_fetch_content.return_value = None  # No remote recipe
        
        # Add a pending checksum
        spack_manager.add_pending_checksum("test-pkg", "1.0.0")
        
        with patch.object(spack_manager, '_log_and_print') as mock_log:
            result = spack_manager._process_pending_checksums("/test/env")
        
        # Should return one item in list with error info (exception caught and handled)
        assert len(result) == 1
        assert result[0]['package_name'] == 'test-pkg'
        assert result[0]['operation'] == 'checksum_error'
        assert 'Could not obtain recipe for test-pkg from any source' in result[0]['error']
        
        # Should have logged error
        mock_log.assert_any_call("✗ Error adding checksum for test-pkg@1.0.0: Could not obtain recipe for test-pkg from any source", "error")
        
        # Should not have run subprocess (because exception raised before that point)
        mock_subprocess.assert_not_called()

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch('subprocess.run')
    @patch.object(SpackManager, '_fetch_and_write_package_directory')
    def test_process_pending_checksums_timeout(self, mock_fetch_local, mock_subprocess,
                                              mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_checksums when subprocess times out."""
        mock_fetch_local.return_value = True
        
        # Mock subprocess timeout
        mock_subprocess.side_effect = subprocess.TimeoutExpired("spack", 300)
        
        # Add a pending checksum
        spack_manager.add_pending_checksum("test-pkg", "1.0.0")
        
        with patch.object(spack_manager, '_log_and_print') as mock_log:
            result = spack_manager._process_pending_checksums("/test/env")
        
        # Should return one package for editing with timeout info
        assert len(result) == 1
        pkg = result[0]
        assert pkg['package_name'] == "test-pkg"
        assert pkg['version'] == "1.0.0"
        assert pkg['operation'] == 'checksum_timeout'
        
        # Should have logged timeout error
        mock_log.assert_any_call("✗ Timeout adding checksum for test-pkg@1.0.0", "error")

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch('subprocess.run')
    @patch.object(SpackManager, '_fetch_and_write_package_directory')
    def test_process_pending_checksums_multiple_packages(self, mock_fetch_local, mock_subprocess,
                                                        mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_checksums with multiple packages."""
        mock_fetch_local.return_value = True
        
        # Mock different subprocess results
        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "pkg1" in cmd:
                result = Mock()
                result.returncode = 0
                return result
            elif "pkg2" in cmd:
                result = Mock()
                result.returncode = 1
                result.stderr = "Error for pkg2"
                return result
            else:  # pkg3
                raise subprocess.TimeoutExpired("spack", 300)
        
        mock_subprocess.side_effect = subprocess_side_effect
        
        # Add multiple pending checksums
        spack_manager.add_pending_checksum("pkg1", "1.0.0")
        spack_manager.add_pending_checksum("pkg2", "1.0.0")
        spack_manager.add_pending_checksum("pkg3", "1.0.0")
        
        with patch.object(spack_manager, '_log_and_print') as mock_log:
            result = spack_manager._process_pending_checksums("/test/env")
        
        # Should return all three packages with different operations
        assert len(result) == 3
        
        operations = {pkg['package_name']: pkg['operation'] for pkg in result}
        assert operations['pkg1'] == 'checksum'
        assert operations['pkg2'] == 'checksum_failed'
        assert operations['pkg3'] == 'checksum_timeout'
        
        # Should have made three subprocess calls
        assert mock_subprocess.call_count == 3
        
        # Should clear pending checksums
        assert len(spack_manager.pending_checksums) == 0

    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch('subprocess.run')
    @patch.object(SpackManager, '_fetch_and_write_package_directory')
    def test_process_pending_checksums_environment_variables(self, mock_fetch_local, mock_subprocess,
                                                           mock_file, mock_mkdir, spack_manager):
        """Test _process_pending_checksums sets correct environment variables."""
        mock_fetch_local.return_value = True
        
        # Mock successful subprocess result
        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result
        
        # Add a pending checksum
        spack_manager.add_pending_checksum("test-pkg", "1.0.0")
        
        result = spack_manager._process_pending_checksums("/test/env")
        
        # Should have called subprocess with modified environment
        assert mock_subprocess.call_count == 1
        call_kwargs = mock_subprocess.call_args[1]
        assert 'env' in call_kwargs
        assert call_kwargs['env']['EDITOR'] == 'echo'
        assert call_kwargs['timeout'] == 150

    @patch.object(SpackManager, '_process_pending_recipes')
    @patch.object(SpackManager, '_process_pending_checksums')
    @patch.object(SpackManager, '_process_pending_git_commits')
    @patch.object(SpackManager, '_copy_site_common_dirs')
    @patch.object(SpackManager, '_ensure_env_repository')
    @patch.object(SpackManager, '_get_upstream_package_info')
    def test_create_environment_from_base_spack_yaml(self, mock_get_pkg_info, mock_ensure_repo, mock_copy_dirs, 
                                                    mock_git_commits, mock_checksums, 
                                                    mock_recipes, spack_manager, tmp_path):
        """Test create_environment using a base spack.yaml and validate the output."""
        import shutil
        from ruamel.yaml import YAML
        
        # Mock the internal methods to return empty lists/no-ops
        mock_recipes.return_value = []
        mock_checksums.return_value = []
        mock_git_commits.return_value = []
        mock_copy_dirs.return_value = None
        mock_ensure_repo.return_value = None
        
        # Mock _get_upstream_package_info to return package configuration
        mock_get_pkg_info.return_value = {
            'hdf5': {
                'version': '1.10.7',
                'variants': '+mpi +threadsafe'
            },
            'netcdf-c': {
                'version': '4.7.4',
                'variants': '+mpi +parallel-netcdf'
            }
        }
        
        # Setup: create a fake upstream env with a base spack.yaml
        base_yaml = Path(__file__).parent / "base_spack.yaml"
        upstream_env = tmp_path / "upstream_env"
        upstream_env.mkdir()
        shutil.copy(base_yaml, upstream_env / "spack.yaml")

        # Prepare test packages and platform
        packages = [
            {"name": "hdf5", "version": "1.10.7"},
            {"name": "netcdf-c", "version": "4.7.4"}
        ]
        platform = Mock()
        platform.config = Mock()
        platform.config.get.return_value = ""  # Return empty string for cpu_target

        # Call create_environment
        env_name = "testenv"
        work_dir = str(tmp_path)
        env_path, pkgs_edit = spack_manager.create_environment(
            env_name=env_name,
            upstream_path=str(upstream_env),
            packages=packages,
            work_dir=work_dir,
            platform=platform
        )

        # Validate the resulting spack.yaml content
        result_yaml_path = Path(env_path) / "spack.yaml"
        assert result_yaml_path.exists()
        yaml = YAML()
        with open(result_yaml_path) as f:
            result_yaml = yaml.load(f)

        # The output should have the correct specs and upstream
        assert "spack" in result_yaml
        spack_section = result_yaml["spack"]
        assert set(spack_section["specs"]) == {"hdf5@=1.10.7", "netcdf-c@=4.7.4"}
        assert "upstreams" in spack_section
        # The upstream should be named emcenvchainer-upstream and point to the upstream_env/install
        assert "emcenvchainer-upstream" in spack_section["upstreams"]
        assert spack_section["upstreams"]["emcenvchainer-upstream"]["install_tree"] == str(upstream_env / "install")
        
        # Check that package-specific configuration was added based on upstream info
        assert "packages" in spack_section
        packages_config = spack_section["packages"]
        
        # Check hdf5 package configuration
        assert "hdf5:" in packages_config
        hdf5_config = packages_config["hdf5:"]
        assert hdf5_config["version"] == ["1.10.7"]
        assert hdf5_config["variants"] == "+mpi +threadsafe"
        
        # Check netcdf-c package configuration  
        assert "netcdf-c:" in packages_config
        netcdf_config = packages_config["netcdf-c:"]
        assert netcdf_config["version"] == ["4.7.4"]
        assert netcdf_config["variants"] == "+mpi +parallel-netcdf"
        
        # Check that common build deps are marked as non-buildable
        assert "cmake" in packages_config
        assert packages_config["cmake"]["buildable"] is False
        
        # Verify the mocked methods were called
        mock_recipes.assert_called_once()
        mock_checksums.assert_called_once()
        mock_git_commits.assert_called_once()
        mock_copy_dirs.assert_called_once()

    @patch.object(SpackManager, '_run_spack_command')
    def test_concretize_environment_success_with_specs(self, mock_run_spack, spack_manager):
        """Test successful concretization with specs returned."""
        # Mock bootstrap commands to succeed
        bootstrap_result = Mock()
        bootstrap_result.returncode = 0
        
        # Mock concretize command to succeed
        concretize_result = Mock()
        concretize_result.returncode = 0
        concretize_result.stdout = "Concretization successful"
        concretize_result.stderr = ""
        
        # Mock find command to return some specs
        find_result = Mock()
        find_result.returncode = 0
        find_result.stdout = "hdf5@=1.10.7\nnetcdf-c@=4.7.4\ncmake@=3.20.0"
        
        # Set up the side effect for multiple calls
        mock_run_spack.side_effect = [bootstrap_result, bootstrap_result, concretize_result, find_result]
        
        success, output = spack_manager.concretize_environment("/test/env")
        
        # Should return success with output
        assert success is True
        assert output == "Concretization successful"
        
        # Verify all expected commands were called
        assert mock_run_spack.call_count == 3  # Only bootstrap and concretize, no find command
        
        # Check bootstrap calls
        mock_run_spack.assert_any_call(['-e', '/test/env', '-C', '/test/env', 'bootstrap', 'root', '/test/env/bootstrap'])
        mock_run_spack.assert_any_call(['-e', '/test/env', '-C', '/test/env', 'bootstrap', 'now'])
        
        # Check concretize call
        mock_run_spack.assert_any_call(['-e', '/test/env', '-C', '/test/env', 'concretize'])

    @patch.object(SpackManager, '_run_spack_command')
    def test_concretize_environment_success_no_specs(self, mock_run_spack, spack_manager):
        """Test successful concretization but no specs found."""
        # Mock bootstrap commands to succeed
        bootstrap_result = Mock()
        bootstrap_result.returncode = 0
        
        # Mock concretize command to succeed
        concretize_result = Mock()
        concretize_result.returncode = 0
        concretize_result.stdout = "Concretization successful"
        concretize_result.stderr = ""
        
        # Mock find command to return empty result
        find_result = Mock()
        find_result.returncode = 0
        find_result.stdout = ""
        
        mock_run_spack.side_effect = [bootstrap_result, bootstrap_result, concretize_result]
        
        success, output = spack_manager.concretize_environment("/test/env")
        
        # Should return success with output
        assert success is True
        assert output == "Concretization successful"

    @patch.object(SpackManager, '_run_spack_command')
    def test_concretize_environment_concretization_fails(self, mock_run_spack, spack_manager):
        """Test failed concretization."""
        # Mock bootstrap commands to succeed
        bootstrap_result = Mock()
        bootstrap_result.returncode = 0
        
        # Mock concretize command to fail
        concretize_result = Mock()
        concretize_result.returncode = 1
        concretize_result.stdout = ""
        concretize_result.stderr = "Error: conflicting requirements"
        
        mock_run_spack.side_effect = [bootstrap_result, bootstrap_result, concretize_result]
        
        result = spack_manager.concretize_environment("/test/env")
        
        # Should return failure - the method actually returns 3 values on failure
        if len(result) == 3:
            success, specs, output = result
            assert success is False
            assert len(specs) == 1
            assert "Concretization failed: Error: conflicting requirements" in specs[0]
            assert output == "Error: conflicting requirements"
        else:
            success, output = result
            assert success is False
            assert "Error: conflicting requirements" in output
        
        # Should only call bootstrap and concretize
        assert mock_run_spack.call_count == 3

    @patch.object(SpackManager, '_run_spack_command')
    def test_concretize_environment_exception_handling(self, mock_run_spack, spack_manager):
        """Test exception handling during concretization."""
        # Mock first bootstrap to succeed, second to raise exception
        bootstrap_result = Mock()
        bootstrap_result.returncode = 0
        
        mock_run_spack.side_effect = [bootstrap_result, RuntimeError("Command failed")]
        
        result = spack_manager.concretize_environment("/test/env")
        
        # Should return failure with exception message - the method actually returns 3 values on exception
        if len(result) == 3:
            success, specs, output = result
            assert success is False
            assert len(specs) == 1
            assert "Command failed" in specs[0]
            assert output == ""
        else:
            success, output = result
            assert success is False
            assert "Command failed" in output

    @patch.object(SpackManager, '_run_spack_command')
    def test_concretize_environment_output_parsing(self, mock_run_spack, spack_manager):
        """Test proper parsing of stdout and stderr for output."""
        # Mock bootstrap commands to succeed
        bootstrap_result = Mock()
        bootstrap_result.returncode = 0
        
        # Mock concretize command with both stdout and stderr
        concretize_result = Mock()
        concretize_result.returncode = 0
        concretize_result.stdout = "Concretization output"
        concretize_result.stderr = "Warning messages"
        
        # Mock find command
        find_result = Mock()
        find_result.returncode = 0
        find_result.stdout = "spec1\nspec2"
        
        mock_run_spack.side_effect = [bootstrap_result, bootstrap_result, concretize_result]
        
        success, output = spack_manager.concretize_environment("/test/env")
        
        # Should combine stdout and stderr for output
        assert success is True
        assert output == "Concretization outputWarning messages"

    @patch.object(SpackManager, '_run_spack_command')
    def test_concretize_environment_empty_output(self, mock_run_spack, spack_manager):
        """Test handling of empty stdout/stderr."""
        # Mock bootstrap commands to succeed
        bootstrap_result = Mock()
        bootstrap_result.returncode = 0
        
        # Mock concretize command with no output
        concretize_result = Mock()
        concretize_result.returncode = 0
        concretize_result.stdout = None
        concretize_result.stderr = None
        
        # Mock find command
        find_result = Mock()
        find_result.returncode = 0
        find_result.stdout = "spec1"
        
        mock_run_spack.side_effect = [bootstrap_result, bootstrap_result, concretize_result]
        
        success, output = spack_manager.concretize_environment("/test/env")
        
        # Should handle None values gracefully
        assert success is True
        assert output == ""

    # Tests for install_environment_interactive method

    @patch('subprocess.Popen')
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_install_environment_interactive_success(self, mock_stdout, mock_stdin, mock_popen, spack_manager):
        """Test successful interactive installation."""
        # Mock process
        mock_process = Mock()
        mock_process.stdout.readline.side_effect = [
            "==> Installing packages\n",
            "==> Package 1 installed\n",
            "==> Package 2 installed\n",
            ""  # End of output
        ]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        result = spack_manager.install_environment_interactive("/test/env")
        
        assert result is True
        
        # Verify Popen was called correctly
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert call_args[0][0] == [str(spack_manager.spack_exe), '-e', '/test/env', 'install']
        assert call_args[1]['stdout'] == subprocess.PIPE
        assert call_args[1]['stderr'] == subprocess.STDOUT
        assert call_args[1]['stdin'] == mock_stdin
        assert call_args[1]['text'] is True
        assert call_args[1]['bufsize'] == 1
        
        # Verify wait was called
        mock_process.wait.assert_called_once()

    @patch('subprocess.Popen')
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_install_environment_interactive_failure(self, mock_stdout, mock_stdin, mock_popen, spack_manager):
        """Test installation failure with non-zero return code."""
        # Mock process with failure
        mock_process = Mock()
        mock_process.stdout.readline.side_effect = [
            "==> Installing packages\n",
            "==> Error: Installation failed\n",
            ""  # End of output
        ]
        mock_process.wait.return_value = 1
        mock_popen.return_value = mock_process
        
        result = spack_manager.install_environment_interactive("/test/env")
        
        assert result is False
        mock_process.wait.assert_called_once()

    @patch('subprocess.Popen')
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_install_environment_interactive_with_logger(self, mock_stdout, mock_stdin, mock_popen, spack_manager):
        """Test interactive installation with logging enabled."""
        # Setup logger
        spack_manager.logger = Mock()
        
        # Mock process
        mock_process = Mock()
        mock_process.stdout.readline.side_effect = [
            "==> Installing package1\n",
            "==> Installing package2\n",
            ""  # End of output
        ]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        result = spack_manager.install_environment_interactive("/test/env")
        
        assert result is True
        
        # Verify logging was called
        assert spack_manager.logger.info.called
        # Check that initial log message was made
        log_calls = [call[0][0] for call in spack_manager.logger.info.call_args_list]
        assert any("Starting interactive spack install" in call for call in log_calls)
        assert any("Spack install completed with return code: 0" in call for call in log_calls)

    @patch('subprocess.Popen')
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_install_environment_interactive_output_capture(self, mock_stdout, mock_stdin, mock_popen, spack_manager):
        """Test that output is properly captured and written to stdout."""
        # Setup logger to verify output capture
        spack_manager.logger = Mock()
        
        # Mock process with multiple output lines
        output_lines = [
            "Line 1: Starting\n",
            "Line 2: Processing\n",
            "Line 3: Complete\n",
            ""  # End of output
        ]
        mock_process = Mock()
        mock_process.stdout.readline.side_effect = output_lines
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        result = spack_manager.install_environment_interactive("/test/env")
        
        assert result is True
        
        # Verify output was written to stdout
        assert mock_stdout.write.called
        write_calls = [call[0][0] for call in mock_stdout.write.call_args_list]
        assert "Line 1: Starting\n" in write_calls
        assert "Line 2: Processing\n" in write_calls
        assert "Line 3: Complete\n" in write_calls
        
        # Verify logging captured output
        log_calls = [call[0][0] for call in spack_manager.logger.info.call_args_list]
        assert any("SPACK: Line 1: Starting" in call for call in log_calls)
        assert any("SPACK: Line 2: Processing" in call for call in log_calls)
        assert any("SPACK: Line 3: Complete" in call for call in log_calls)

    @patch('subprocess.Popen')
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_install_environment_interactive_exception(self, mock_stdout, mock_stdin, mock_popen, spack_manager):
        """Test exception handling during interactive installation."""
        # Make Popen raise an exception
        mock_popen.side_effect = Exception("Process creation failed")
        
        result = spack_manager.install_environment_interactive("/test/env")
        
        assert result is False

    @patch('subprocess.Popen')
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_install_environment_interactive_exception_with_logger(self, mock_stdout, mock_stdin, mock_popen, spack_manager):
        """Test exception handling with logging enabled."""
        # Setup logger
        spack_manager.logger = Mock()
        
        # Make Popen raise an exception
        mock_popen.side_effect = OSError("Permission denied")
        
        result = spack_manager.install_environment_interactive("/test/env")
        
        assert result is False
        
        # Verify error was logged
        spack_manager.logger.error.assert_called_once()
        error_call = spack_manager.logger.error.call_args[0][0]
        assert "Error during interactive install" in error_call
        assert "Permission denied" in error_call

    @patch('subprocess.Popen')
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_install_environment_interactive_thread_timeout(self, mock_stdout, mock_stdin, mock_popen, spack_manager):
        """Test that output reader thread properly handles completion."""
        # Setup logger
        spack_manager.logger = Mock()
        
        # Mock process
        mock_process = Mock()
        mock_process.stdout.readline.side_effect = [
            "Installing...\n",
            ""  # End of output
        ]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        result = spack_manager.install_environment_interactive("/test/env")
        
        assert result is True
        
        # Verify the process completed successfully
        mock_process.wait.assert_called_once()

    @patch('subprocess.Popen')
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_install_environment_interactive_empty_output(self, mock_stdout, mock_stdin, mock_popen, spack_manager):
        """Test installation with no output."""
        # Mock process with no output
        mock_process = Mock()
        mock_process.stdout.readline.return_value = ""  # Immediate EOF
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        result = spack_manager.install_environment_interactive("/test/env")
        
        assert result is True

    @patch('subprocess.Popen')
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_install_environment_interactive_reader_exception(self, mock_stdout, mock_stdin, mock_popen, spack_manager):
        """Test handling of exception in output reader thread."""
        # Setup logger
        spack_manager.logger = Mock()
        
        # Mock process with exception during readline
        mock_process = Mock()
        mock_process.stdout.readline.side_effect = Exception("Read error")
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        result = spack_manager.install_environment_interactive("/test/env")
        
        # Should still return True (process completed successfully)
        assert result is True
        
        # Verify error in reader thread was logged
        error_calls = [call[0][0] for call in spack_manager.logger.error.call_args_list]
        assert any("Error in output reader thread" in call for call in error_calls)

    @patch('subprocess.Popen')
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_install_environment_interactive_output_line_count(self, mock_stdout, mock_stdin, mock_popen, spack_manager):
        """Test that output line count is properly logged."""
        # Setup logger
        spack_manager.logger = Mock()
        
        # Mock process with specific number of output lines
        mock_process = Mock()
        mock_process.stdout.readline.side_effect = [
            "Line 1\n",
            "Line 2\n",
            "Line 3\n",
            "Line 4\n",
            "Line 5\n",
            ""  # End of output
        ]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        result = spack_manager.install_environment_interactive("/test/env")
        
        assert result is True
        
        # Verify line count was logged
        log_calls = [call[0][0] for call in spack_manager.logger.info.call_args_list]
        assert any("Total output lines captured: 5" in call for call in log_calls)

    # Tests for refresh_modules method

    @patch.object(SpackManager, '_run_spack_command')
    @patch.object(SpackManager, '_log_and_print')
    def test_refresh_modules_success(self, mock_log_print, mock_run_spack, spack_manager):
        """Test successful refresh_modules execution."""
        # Mock successful spack commands
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Module refresh successful"
        mock_result.stderr = ""
        mock_run_spack.return_value = mock_result
        
        env_path = "/test/env"
        
        # Call refresh_modules
        result = spack_manager.refresh_modules(env_path)
        
        # Verify the correct spack commands were called
        expected_calls = [
            mock.call(['-e', env_path, 'module', 'lmod', 'refresh', '--yes-to-all', '--upstream-modules']),
            mock.call(['-e', env_path, 'stack', 'setup-meta-modules'])
        ]
        mock_run_spack.assert_has_calls(expected_calls)
        
        # Verify logging calls
        mock_log_print.assert_any_call("Refreshing Lmod modules...")
        mock_log_print.assert_any_call("Setting up meta-modules...")
        mock_log_print.assert_any_call(f"✓ Module refresh completed. Modulefiles at: {env_path}/install/modulefiles/Core")
        
        # Verify return value
        expected_path = f"{env_path}/install/modulefiles/Core"
        assert result == expected_path

    @patch.object(SpackManager, '_run_spack_command')
    @patch.object(SpackManager, '_log_and_print')
    def test_refresh_modules_lmod_refresh_failure(self, mock_log_print, mock_run_spack, spack_manager):
        """Test refresh_modules when lmod refresh command fails."""
        # Mock config rm success (or failure), config add failure to test MAPL suffix configuration
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Module refresh failed"
        mock_run_spack.return_value = mock_result
        
        env_path = "/test/env"
        
        # Call refresh_modules and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to configure MAPL suffixes: Module refresh failed"):
            spack_manager.refresh_modules(env_path)
        
        # Verify config add was attempted (args should include config/add and contain mapl and suffixes)
        assert mock_run_spack.call_count >= 1
        called_args = mock_run_spack.call_args_list[0][0][0]
        # The command should include 'config' and 'add'
        assert 'config' in called_args and 'add' in called_args
        # The config key or payload should mention mapl and suffixes
        joined = ' '.join(called_args)
        assert 'mapl' in joined and 'suffixes' in joined

        # Verify initial logging calls
        mock_log_print.assert_any_call("Refreshing Lmod modules...")

    @patch.object(SpackManager, '_run_spack_command')
    @patch.object(SpackManager, '_log_and_print')
    def test_refresh_modules_meta_modules_failure(self, mock_log_print, mock_run_spack, spack_manager):
        """Test refresh_modules when meta-modules setup fails."""
        # Mock successful config add, successful lmod refresh, but failed meta-modules setup
        mock_results = [
            Mock(returncode=0, stderr=""),  # config add success
            Mock(returncode=0, stdout="Module refresh successful", stderr=""),  # lmod refresh success
            Mock(returncode=1, stderr="Meta-modules setup failed")  # meta-modules failure
        ]
        mock_run_spack.side_effect = mock_results

        env_path = "/test/env"

        # Call refresh_modules and expect RuntimeError (wrapped)
        with pytest.raises(RuntimeError):
            spack_manager.refresh_modules(env_path)

        # Verify commands were called in order: config add, lmod refresh, setup-meta-modules
        assert mock_run_spack.call_count >= 3
        calls = [c[0][0] for c in mock_run_spack.call_args_list]
        # first call should be config add
        assert 'config' in calls[0] and 'add' in calls[0]
        # second call should be module lmod refresh
        assert 'module' in calls[1]
        # third call should be stack setup-meta-modules
        assert 'stack' in calls[2]

        # Verify logging calls
        mock_log_print.assert_any_call("Refreshing Lmod modules...")
        mock_log_print.assert_any_call("Setting up meta-modules...")

    @patch.object(SpackManager, '_run_spack_command')
    @patch.object(SpackManager, '_log_and_print')
    def test_refresh_modules_with_logging(self, mock_log_print, mock_run_spack, spack_manager):
        """Test refresh_modules with logging enabled."""
        # Setup logging
        with tempfile.TemporaryDirectory() as temp_dir:
            spack_manager.setup_logging(temp_dir)
            
            # Mock successful spack commands
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "Module refresh successful"
            mock_result.stderr = ""
            mock_run_spack.return_value = mock_result
            
            env_path = "/test/env"
            
            # Call refresh_modules
            result = spack_manager.refresh_modules(env_path)
            
            # Verify logger is set
            assert spack_manager.logger is not None
            
            # Verify return value
            expected_path = f"{env_path}/install/modulefiles/Core"
            assert result == expected_path

    @patch.object(SpackManager, '_run_spack_command')
    @patch.object(SpackManager, '_log_and_print')
    def test_refresh_modules_exception_handling(self, mock_log_print, mock_run_spack, spack_manager):
        """Test refresh_modules when an unexpected exception occurs."""
        # Mock _run_spack_command to raise an exception immediately (config add)
        mock_run_spack.side_effect = Exception("Unexpected error")

        env_path = "/test/env"

        # Call refresh_modules and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to refresh modules: Unexpected error"):
            spack_manager.refresh_modules(env_path)

        # Verify at least one call was attempted and it was a config/add style call (if available)
        if mock_run_spack.call_args_list:
            first_call = mock_run_spack.call_args_list[0][0][0]
            assert 'config' in first_call and 'add' in first_call

    @patch.object(SpackManager, '_run_spack_command')
    @patch.object(SpackManager, '_log_and_print')
    def test_refresh_modules_exception_with_logging(self, mock_log_print, mock_run_spack, spack_manager):
        """Test refresh_modules exception handling with logging enabled."""
        # Setup logging
        with tempfile.TemporaryDirectory() as temp_dir:
            spack_manager.setup_logging(temp_dir)
            
            # Mock _run_spack_command to raise an exception
            mock_run_spack.side_effect = Exception("Unexpected error")
            
            env_path = "/test/env"
                 # Call refresh_modules and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to refresh modules: Unexpected error"):
            spack_manager.refresh_modules(env_path)
        
        # Verify logger is set
        assert spack_manager.logger is not None

    @patch.object(SpackManager, '_run_spack_command')
    @patch.object(SpackManager, '_log_and_print')
    def test_refresh_modules_path_construction(self, mock_log_print, mock_run_spack, spack_manager):
        """Test that refresh_modules constructs the correct modulefiles path."""
        # Mock successful spack commands
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Module refresh successful"
        mock_result.stderr = ""
        mock_run_spack.return_value = mock_result
        
        # Test with different env_path formats
        test_cases = [
            "/path/to/env",
            "/path/to/env/",
            "relative/env",
            "/complex/path/with-dashes_and.dots/env"
        ]
        
        for env_path in test_cases:
            result = spack_manager.refresh_modules(env_path)
            expected_path = f"{env_path.rstrip('/')}/install/modulefiles/Core"
            assert result == expected_path
            
            # Reset mock for next iteration
            mock_run_spack.reset_mock()
            mock_log_print.reset_mock()

    @patch.object(SpackManager, '_run_spack_command')
    @patch.object(SpackManager, '_log_and_print')
    def test_refresh_modules_lmod_failure_with_logging(self, mock_log_print, mock_run_spack, spack_manager):
        """Test refresh_modules lmod failure with logging enabled."""
        # Setup logging
        with tempfile.TemporaryDirectory() as temp_dir:
            spack_manager.setup_logging(temp_dir)
            
            # Mock config rm success, then config add failure
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = "Module refresh failed"
            mock_run_spack.return_value = mock_result
            
            env_path = "/test/env"
            
            # Call refresh_modules and expect RuntimeError
            with pytest.raises(RuntimeError, match="Failed to configure MAPL suffixes: Module refresh failed"):
                spack_manager.refresh_modules(env_path)
            
            # Verify logger exists and error would be logged
            assert spack_manager.logger is not None

    @patch.object(SpackManager, '_run_spack_command')
    @patch.object(SpackManager, '_log_and_print')
    def test_refresh_modules_meta_modules_failure_with_logging(self, mock_log_print, mock_run_spack, spack_manager):
        """Test refresh_modules meta-modules failure with logging enabled."""
        # Setup logging
        with tempfile.TemporaryDirectory() as temp_dir:
            spack_manager.setup_logging(temp_dir)
            
            # Mock successful config add, lmod refresh, but failed meta-modules setup
            mock_results = [
                Mock(returncode=0, stderr=""),  # config add success
                Mock(returncode=0, stdout="Module refresh successful", stderr=""),  # lmod refresh success
                Mock(returncode=1, stderr="Meta-modules setup failed")  # meta-modules failure
            ]
            mock_run_spack.side_effect = mock_results

            env_path = "/test/env"

            # Call refresh_modules and expect RuntimeError
            with pytest.raises(RuntimeError):
                spack_manager.refresh_modules(env_path)

            # Verify logger exists and error would be logged
            assert spack_manager.logger is not None

# Tests for _fetch_recipe_content method

    @patch('requests.get')
    def test_fetch_recipe_content_success(self, mock_get, spack_manager):
        """Test successful recipe content fetch."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "# Example recipe content\nclass TestPackage(Package):\n    pass"
        mock_get.return_value = mock_response
        
        # Call the method
        result = spack_manager._fetch_recipe_content("test-package")
        
        # Verify the result
        assert result == "# Example recipe content\nclass TestPackage(Package):\n    pass"
        
        # Verify the URL was constructed correctly
        expected_url = "https://raw.githubusercontent.com/JCSDA/spack/refs/heads/develop/var/spack/repos/builtin/packages/test-package/package.py"
        mock_get.assert_called_once_with(expected_url, timeout=10)

    @patch('requests.get')
    def test_fetch_recipe_content_custom_config(self, mock_get, spack_manager):
        """Test recipe content fetch with custom repository configuration."""
        # Setup custom config
        spack_manager.config.get.return_value = {
            "base_url": "https://github.com/custom-org/custom-spack.git",
            "branch": "custom-branch"
        }
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "# Custom recipe content"
        mock_get.return_value = mock_response
        
        # Call the method
        result = spack_manager._fetch_recipe_content("custom-package")
        
        # Verify the result
        assert result == "# Custom recipe content"
        
        # Verify the URL was constructed with custom config
        expected_url = "https://raw.githubusercontent.com/custom-org/custom-spack/refs/heads/custom-branch/var/spack/repos/builtin/packages/custom-package/package.py"
        mock_get.assert_called_once_with(expected_url, timeout=10)

    @patch('requests.get')
    def test_fetch_recipe_content_http_404(self, mock_get, spack_manager):
        """Test recipe content fetch when package not found (HTTP 404)."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        # Call the method
        result = spack_manager._fetch_recipe_content("nonexistent-package")
        
        # Should return None for 404
        assert result is None
        
        # Verify the URL was attempted
        expected_url = "https://raw.githubusercontent.com/JCSDA/spack/refs/heads/develop/var/spack/repos/builtin/packages/nonexistent-package/package.py"
        mock_get.assert_called_once_with(expected_url, timeout=10)

    @patch('requests.get')
    def test_fetch_recipe_content_http_500(self, mock_get, spack_manager):
        """Test recipe content fetch when server error occurs (HTTP 500)."""
        # Mock 500 response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        # Call the method
        result = spack_manager._fetch_recipe_content("test-package")
        
        # Should return None for server error
        assert result is None
        
        # Verify the URL was attempted
        expected_url = "https://raw.githubusercontent.com/JCSDA/spack/refs/heads/develop/var/spack/repos/builtin/packages/test-package/package.py"
        mock_get.assert_called_once_with(expected_url, timeout=10)

    @patch('requests.get')
    def test_fetch_recipe_content_network_exception(self, mock_get, spack_manager):
        """Test recipe content fetch when network exception occurs."""
        # Mock network exception
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")
        
        # Call the method
        result = spack_manager._fetch_recipe_content("test-package")
        
        # Should return None for network error
        assert result is None
        
        # Verify the URL was attempted
        expected_url = "https://raw.githubusercontent.com/JCSDA/spack/refs/heads/develop/var/spack/repos/builtin/packages/test-package/package.py"
        mock_get.assert_called_once_with(expected_url, timeout=10)

    @patch('requests.get')
    def test_fetch_recipe_content_timeout_exception(self, mock_get, spack_manager):
        """Test recipe content fetch when timeout occurs."""
        # Mock timeout exception
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        
        # Call the method
        result = spack_manager._fetch_recipe_content("test-package")
        
        # Should return None for timeout
        assert result is None
        
        # Verify the URL was attempted with correct timeout
        expected_url = "https://raw.githubusercontent.com/JCSDA/spack/refs/heads/develop/var/spack/repos/builtin/packages/test-package/package.py"
        mock_get.assert_called_once_with(expected_url, timeout=10)

    @patch('requests.get')
    def test_fetch_recipe_content_with_logging(self, mock_get, spack_manager):
        """Test recipe content fetch with logging enabled."""
        # Setup logging
        with tempfile.TemporaryDirectory() as temp_dir:
            spack_manager.setup_logging(temp_dir)
            
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "# Recipe with logging"
            mock_get.return_value = mock_response
            
            # Call the method
            result = spack_manager._fetch_recipe_content("logged-package")
            
            # Verify the result
            assert result == "# Recipe with logging"
            
            # Verify logger was used
            assert spack_manager.logger is not None

    @patch('requests.get')
    def test_fetch_recipe_content_with_logging_failure(self, mock_get, spack_manager):
        """Test recipe content fetch failure with logging enabled."""
        # Setup logging
        with tempfile.TemporaryDirectory() as temp_dir:
            spack_manager.setup_logging(temp_dir)
            
            # Mock 404 response
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response
            
            # Call the method
            result = spack_manager._fetch_recipe_content("missing-package")
            
            # Should return None
            assert result is None
            
            # Verify logger was used
            assert spack_manager.logger is not None

    @patch('requests.get')
    def test_fetch_recipe_content_with_logging_exception(self, mock_get, spack_manager):
        """Test recipe content fetch exception with logging enabled."""
        # Setup logging
        with tempfile.TemporaryDirectory() as temp_dir:
            spack_manager.setup_logging(temp_dir)
            
            # Mock exception
            mock_get.side_effect = Exception("General error")
            
            # Call the method
            result = spack_manager._fetch_recipe_content("error-package")
            
            # Should return None
            assert result is None
            
            # Verify logger was used
            assert spack_manager.logger is not None

    def test_fetch_recipe_content_url_construction(self, spack_manager):
        """Test URL construction for different package names."""
        with patch('requests.get') as mock_get:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "# Test recipe"
            mock_get.return_value = mock_response
            
            test_cases = [
                "simple-package",
                "package_with_underscores", 
                "package-with-many-dashes",
                "py-python-package",
                "r-r-package"
            ]
            
            for package_name in test_cases:
                # Reset mock for each test case
                mock_get.reset_mock()
                
                # Call the method
                result = spack_manager._fetch_recipe_content(package_name)
                
                # Verify the result
                assert result == "# Test recipe"
                
                # Verify the URL was constructed correctly
                expected_url = f"https://raw.githubusercontent.com/JCSDA/spack/refs/heads/develop/var/spack/repos/builtin/packages/{package_name}/package.py"
                mock_get.assert_called_once_with(expected_url, timeout=10)

    def test_fetch_recipe_content_config_fallback(self, spack_manager):
        """Test fallback to default configuration when config is missing."""
        # Setup config to return empty dict for spack_repository
        spack_manager.config.get.return_value = {}
        
        with patch('requests.get') as mock_get:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "# Fallback recipe"
            mock_get.return_value = mock_response
            
            # Call the method
            result = spack_manager._fetch_recipe_content("fallback-package")
            
            # Verify the result
            assert result == "# Fallback recipe"
            
            # Verify the URL was constructed with defaults
            expected_url = "https://raw.githubusercontent.com/JCSDA/spack/refs/heads/develop/var/spack/repos/builtin/packages/fallback-package/package.py"
            mock_get.assert_called_once_with(expected_url, timeout=10)

    def test_fetch_recipe_content_partial_config(self, spack_manager):
        """Test behavior with partial configuration (missing branch)."""
        # Setup config with base_url but missing branch
        spack_manager.config.get.return_value = {
            "base_url": "https://github.com/partial-org/partial-spack.git"
        }
        
        with patch('requests.get') as mock_get:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "# Partial config recipe"
            mock_get.return_value = mock_response
            
            # Call the method
            result = spack_manager._fetch_recipe_content("partial-package")
            
            # Verify the result
            assert result == "# Partial config recipe"
            
            # Verify the URL was constructed with default branch
            expected_url = "https://raw.githubusercontent.com/partial-org/partial-spack/refs/heads/develop/var/spack/repos/builtin/packages/partial-package/package.py"
            mock_get.assert_called_once_with(expected_url, timeout=10)

# Tests for _fetch_and_write_package_directory method

    @patch('shutil.copytree')
    @patch('shutil.rmtree')
    @patch.object(SpackManager, '_run_spack_command')
    def test_fetch_and_write_package_directory_success(self, mock_run_spack, mock_rmtree, mock_copytree, spack_manager, tmp_path):
        """Test successful package directory fetch and write."""
        # Mock successful spack command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "/path/to/spack/packages/test-package"
        mock_run_spack.return_value = mock_result
        
        # Create mock source directory
        source_dir = tmp_path / "source" / "test-package"
        source_dir.mkdir(parents=True)
        (source_dir / "package.py").write_text("# test package content")
        (source_dir / "patch1.patch").write_text("patch content")
        
        target_dir = tmp_path / "target" / "test-package"
        
        # Mock Path.exists() to return True for source directory
        with patch('pathlib.Path.exists', return_value=True):
            # Mock Path.rglob() to return some files
            with patch('pathlib.Path.rglob') as mock_rglob:
                mock_files = [
                    Mock(is_file=lambda: True),  # package.py
                    Mock(is_file=lambda: True),  # patch1.patch
                    Mock(is_file=lambda: False)  # subdirectory
                ]
                mock_rglob.return_value = mock_files
                
                result = spack_manager._fetch_and_write_package_directory("test-pkg", target_dir)
        
        # Verify result
        assert result is True
        
        # Verify spack command was called
        mock_run_spack.assert_called_once_with(['location', '--package-dir', 'test-pkg'])
        
        # Verify copytree was called with correct arguments
        mock_copytree.assert_called_once()
        call_args = mock_copytree.call_args
        assert str(call_args[0][1]) == str(target_dir)  # target path
        assert call_args[1]['ignore'] is not None  # ignore patterns specified

    @patch('shutil.copytree')
    @patch('shutil.rmtree')
    @patch.object(SpackManager, '_run_spack_command')
    def test_fetch_and_write_package_directory_spack_command_fails(self, mock_run_spack, mock_rmtree, mock_copytree, spack_manager, tmp_path):
        """Test when spack location command fails."""
        # Mock failed spack command
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Package not found"
        mock_run_spack.return_value = mock_result
        
        target_dir = tmp_path / "target" / "test-package"
        
        result = spack_manager._fetch_and_write_package_directory("nonexistent-pkg", target_dir)
        
        # Verify result
        assert result is False
        
        # Verify spack command was called
        mock_run_spack.assert_called_once_with(['location', '--package-dir', 'nonexistent-pkg'])
        
        # Verify no copying occurred
        mock_copytree.assert_not_called()

    @patch('shutil.copytree')
    @patch('shutil.rmtree')
    @patch.object(SpackManager, '_run_spack_command')
    def test_fetch_and_write_package_directory_source_not_exists(self, mock_run_spack, mock_rmtree, mock_copytree, spack_manager, tmp_path):
        """Test when source directory doesn't exist."""
        # Mock successful spack command but directory doesn't exist
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "/nonexistent/path/to/package"
        mock_run_spack.return_value = mock_result
        
        target_dir = tmp_path / "target" / "test-package"
        
        result = spack_manager._fetch_and_write_package_directory("test-pkg", target_dir)
        
        # Verify result
        assert result is False
        
        # Verify no copying occurred
        mock_copytree.assert_not_called()

    @patch('shutil.copytree')
    @patch('shutil.rmtree')
    @patch.object(SpackManager, '_run_spack_command')
    def test_fetch_and_write_package_directory_with_logger(self, mock_run_spack, mock_rmtree, mock_copytree, spack_manager, tmp_path):
        """Test successful copy with logger enabled."""
        # Setup logger
        spack_manager.logger = Mock()
        
        # Mock successful spack command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "/path/to/spack/packages/test-package"
        mock_run_spack.return_value = mock_result
        
        target_dir = tmp_path / "target" / "test-package"
        
        # Mock Path.exists() to return True for source directory check
        with patch('pathlib.Path.exists', return_value=True):
            # Use a callback to create actual files when copytree is called
            def create_test_files(*args, **kwargs):
                target_dir.mkdir(parents=True, exist_ok=True)
                (target_dir / "package.py").write_text("test")
                (target_dir / "file1.txt").write_text("test")
                (target_dir / "file2.txt").write_text("test")
                subdir = target_dir / "subdir"
                subdir.mkdir(exist_ok=True)
                (subdir / "file3.txt").write_text("test")
            
            mock_copytree.side_effect = create_test_files
            
            result = spack_manager._fetch_and_write_package_directory("test-pkg", target_dir)
        
        # Verify result
        assert result is True
        
        # Verify logging occurred
        assert spack_manager.logger.info.called
        log_calls = [call[0][0] for call in spack_manager.logger.info.call_args_list]
        assert any("Copying package directory from:" in call for call in log_calls)
        assert any("Copying to:" in call for call in log_calls)
        # Should report 4 files and 1 directory (subdir)
        assert any("Successfully copied 4 files and 1 directories" in call for call in log_calls)

    @patch('shutil.copytree')
    @patch('shutil.rmtree')
    @patch.object(SpackManager, '_run_spack_command')
    def test_fetch_and_write_package_directory_removes_existing_target(self, mock_run_spack, mock_rmtree, mock_copytree, spack_manager, tmp_path):
        """Test that existing target directory is removed before copying."""
        # Mock successful spack command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "/path/to/spack/packages/test-package"
        mock_run_spack.return_value = mock_result
        
        # Create an existing target directory
        target_dir = tmp_path / "target" / "test-package"
        target_dir.mkdir(parents=True)
        (target_dir / "old_file.py").write_text("old content")
        
        # Mock Path.exists() to return True for source directory
        with patch('pathlib.Path.exists', return_value=True):
            # Mock Path.rglob() to return some files
            with patch('pathlib.Path.rglob') as mock_rglob:
                mock_files = [Mock(is_file=lambda: True)]
                mock_rglob.return_value = mock_files
                
                result = spack_manager._fetch_and_write_package_directory("test-pkg", target_dir)
        
        # Verify result
        assert result is True
        
        # Verify rmtree was called to remove existing directory
        mock_rmtree.assert_called_once_with(target_dir)

    @patch('shutil.copytree')
    @patch('shutil.rmtree')
    @patch.object(SpackManager, '_run_spack_command')
    def test_fetch_and_write_package_directory_ignores_pycache(self, mock_run_spack, mock_rmtree, mock_copytree, spack_manager, tmp_path):
        """Test that __pycache__ and *.pyc files are ignored during copy."""
        # Mock successful spack command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "/path/to/spack/packages/test-package"
        mock_run_spack.return_value = mock_result
        
        target_dir = tmp_path / "target" / "test-package"
        
        # Mock Path.exists() to return True
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.rglob') as mock_rglob:
                mock_files = [Mock(is_file=lambda: True)]
                mock_rglob.return_value = mock_files
                
                result = spack_manager._fetch_and_write_package_directory("test-pkg", target_dir)
        
        # Verify copytree was called with ignore patterns
        mock_copytree.assert_called_once()
        call_args = mock_copytree.call_args
        ignore_func = call_args[1]['ignore']
        
        # Test the ignore function
        ignored = ignore_func('/', ['__pycache__', 'test.pyc', 'package.py'])
        assert '__pycache__' in ignored
        assert 'test.pyc' in ignored
        assert 'package.py' not in ignored

    @patch('shutil.copytree')
    @patch('shutil.rmtree')
    @patch.object(SpackManager, '_run_spack_command')
    def test_fetch_and_write_package_directory_copytree_exception(self, mock_run_spack, mock_rmtree, mock_copytree, spack_manager, tmp_path):
        """Test exception handling during copytree."""
        # Mock successful spack command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "/path/to/spack/packages/test-package"
        mock_run_spack.return_value = mock_result
        
        target_dir = tmp_path / "target" / "test-package"
        
        # Mock Path.exists() to return True
        with patch('pathlib.Path.exists', return_value=True):
            # Make copytree raise an exception
            mock_copytree.side_effect = OSError("Permission denied")
            
            result = spack_manager._fetch_and_write_package_directory("test-pkg", target_dir)
        
        # Verify result
        assert result is False

    @patch('shutil.copytree')
    @patch('shutil.rmtree')
    @patch.object(SpackManager, '_run_spack_command')
    def test_fetch_and_write_package_directory_exception_with_logger(self, mock_run_spack, mock_rmtree, mock_copytree, spack_manager, tmp_path):
        """Test exception handling with logging enabled."""
        # Setup logger
        spack_manager.logger = Mock()
        
        # Mock successful spack command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "/path/to/spack/packages/test-package"
        mock_run_spack.return_value = mock_result
        
        target_dir = tmp_path / "target" / "test-package"
        
        # Mock Path.exists() to return True
        with patch('pathlib.Path.exists', return_value=True):
            # Make copytree raise an exception
            mock_copytree.side_effect = RuntimeError("Copy failed")
            
            result = spack_manager._fetch_and_write_package_directory("test-pkg", target_dir)
        
        # Verify result
        assert result is False
        
        # Verify error was logged
        spack_manager.logger.error.assert_called_once()
        error_call = spack_manager.logger.error.call_args[0][0]
        assert "Error copying package directory" in error_call
        assert "test-pkg" in error_call
        assert "Copy failed" in error_call

    @patch('shutil.copytree')
    @patch('shutil.rmtree')
    @patch.object(SpackManager, '_run_spack_command')
    def test_fetch_and_write_package_directory_empty_directory(self, mock_run_spack, mock_rmtree, mock_copytree, spack_manager, tmp_path):
        """Test copying an empty package directory."""
        # Setup logger
        spack_manager.logger = Mock()
        
        # Mock successful spack command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "/path/to/spack/packages/empty-package"
        mock_run_spack.return_value = mock_result
        
        target_dir = tmp_path / "target" / "empty-package"
        
        # Mock Path.exists() to return True
        with patch('pathlib.Path.exists', return_value=True):
            # Mock Path.rglob() to return empty list
            with patch('pathlib.Path.rglob') as mock_rglob:
                mock_rglob.return_value = []  # No files or directories
                
                result = spack_manager._fetch_and_write_package_directory("empty-pkg", target_dir)
        
        # Verify result
        assert result is True
        
        # Verify logging shows 0 files and directories
        log_calls = [call[0][0] for call in spack_manager.logger.info.call_args_list]
        assert any("Successfully copied 0 files and 0 directories" in call for call in log_calls)

    @patch('shutil.copytree')
    @patch('shutil.rmtree')
    @patch.object(SpackManager, '_run_spack_command')
    def test_fetch_and_write_package_directory_many_files(self, mock_run_spack, mock_rmtree, mock_copytree, spack_manager, tmp_path):
        """Test copying a package directory with many files and subdirectories."""
        # Setup logger
        spack_manager.logger = Mock()
        
        # Mock successful spack command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "/path/to/spack/packages/large-package"
        mock_run_spack.return_value = mock_result
        
        target_dir = tmp_path / "target" / "large-package"
        
        # Mock Path.exists() to return True
        with patch('pathlib.Path.exists', return_value=True):
            # Use a callback to create actual files when copytree is called
            def create_many_files(*args, **kwargs):
                target_dir.mkdir(parents=True, exist_ok=True)
                # Create 10 files
                for i in range(10):
                    (target_dir / f"file{i}.txt").write_text(f"content {i}")
                # Create 3 subdirectories
                for i in range(3):
                    subdir = target_dir / f"subdir{i}"
                    subdir.mkdir(exist_ok=True)
            
            mock_copytree.side_effect = create_many_files
            
            result = spack_manager._fetch_and_write_package_directory("large-pkg", target_dir)
        
        # Verify result
        assert result is True
        
        # Verify logging shows correct counts
        log_calls = [call[0][0] for call in spack_manager.logger.info.call_args_list]
        assert any("Successfully copied 10 files and 3 directories" in call for call in log_calls)

    @patch('shutil.copytree')
    @patch('shutil.rmtree')
    @patch.object(SpackManager, '_run_spack_command')
    def test_fetch_and_write_package_directory_stdout_with_whitespace(self, mock_run_spack, mock_rmtree, mock_copytree, spack_manager, tmp_path):
        """Test handling of stdout with leading/trailing whitespace."""
        # Mock spack command with whitespace in output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "  /path/to/spack/packages/test-package\n\n"
        mock_run_spack.return_value = mock_result
        
        target_dir = tmp_path / "target" / "test-package"
        
        # Mock Path.exists() to return True
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.rglob') as mock_rglob:
                mock_files = [Mock(is_file=lambda: True)]
                mock_rglob.return_value = mock_files
                
                result = spack_manager._fetch_and_write_package_directory("test-pkg", target_dir)
        
        # Verify result - should succeed (stdout is stripped)
        assert result is True

    def test_ensure_env_repository_creates_repo_structure(self, spack_manager):
        """Test that _ensure_env_repository creates the correct repository structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = temp_dir
            
            # Execute
            repo_path = spack_manager._ensure_env_repository(env_path)
            
            # Verify return value
            expected_repo_path = Path(env_path) / "envrepo"
            assert repo_path == str(expected_repo_path)
            
            # Verify directory structure
            assert expected_repo_path.exists()
            assert expected_repo_path.is_dir()
            
            packages_dir = expected_repo_path / "packages"
            assert packages_dir.exists()
            assert packages_dir.is_dir()
            
            # Verify repo.yaml file
            repo_yaml = expected_repo_path / "repo.yaml"
            assert repo_yaml.exists()
            assert repo_yaml.is_file()
            
            # Verify repo.yaml content
            with open(repo_yaml, 'r') as f:
                content = f.read()
            expected_content = """repo:
  namespace: envrepo
"""
            assert content == expected_content

    def test_ensure_env_repository_with_existing_repo_yaml(self, spack_manager):
        """Test that _ensure_env_repository doesn't overwrite existing repo.yaml."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = temp_dir
            
            # Pre-create repository structure with existing repo.yaml
            repo_path = Path(env_path) / "envrepo"
            repo_path.mkdir(parents=True)
            
            repo_yaml = repo_path / "repo.yaml"
            existing_content = """repo:
  namespace: custom
  description: "Custom repository"
"""
            with open(repo_yaml, 'w') as f:
                f.write(existing_content)
            
            # Execute
            result_path = spack_manager._ensure_env_repository(env_path)
            
            # Verify return value
            assert result_path == str(repo_path)
            
            # Verify existing repo.yaml is not overwritten
            with open(repo_yaml, 'r') as f:
                content = f.read()
            assert content == existing_content
            
            # Verify packages directory is still created
            packages_dir = repo_path / "packages"
            assert packages_dir.exists()

    def test_ensure_env_repository_with_existing_packages_dir(self, spack_manager):
        """Test that _ensure_env_repository handles existing packages directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = temp_dir
            
            # Pre-create repository structure with existing packages directory
            repo_path = Path(env_path) / "envrepo"
            packages_dir = repo_path / "packages"
            packages_dir.mkdir(parents=True)
            
            # Create a test file in packages directory
            test_file = packages_dir / "test_package" / "package.py"
            test_file.parent.mkdir()
            test_file.write_text("# test content")
            
            # Execute
            result_path = spack_manager._ensure_env_repository(env_path)
            
            # Verify return value
            assert result_path == str(repo_path)
            
            # Verify existing packages directory and files are preserved
            assert packages_dir.exists()
            assert test_file.exists()
            assert test_file.read_text() == "# test content"
            
            # Verify repo.yaml is created
            repo_yaml = repo_path / "repo.yaml"
            assert repo_yaml.exists()

    def test_ensure_env_repository_creates_nested_directories(self, spack_manager):
        """Test that _ensure_env_repository creates nested directories correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with nested environment path
            env_path = Path(temp_dir) / "nested" / "env" / "path"
            
            # Execute
            repo_path = spack_manager._ensure_env_repository(str(env_path))
            
            # Verify return value
            expected_repo_path = env_path / "envrepo"
            assert repo_path == str(expected_repo_path)
            
            # Verify all directories were created
            assert env_path.exists()
            assert expected_repo_path.exists()
            assert (expected_repo_path / "packages").exists()
            assert (expected_repo_path / "repo.yaml").exists()
    
    @patch('subprocess.run')
    def test_offer_package_edit_success(self, mock_run, spack_manager, tmp_path, capsys, monkeypatch):
        """Test that offer_package_edit launches editor commands and returns True on success."""
        # Prepare a dummy recipe file
        recipe_file = tmp_path / "dummy_package.py"
        recipe_file.write_text("dummy content")
        packages_to_edit = [{
            'package_name': 'dummy_package',
            'version': '1.2.3',
            'recipe_path': str(recipe_file)
        }]

        # Mock subprocess.run to simulate successful editor exit
        mock_run.return_value = CompletedProcess(args=['editor', str(recipe_file)], returncode=0)

        # Force a known EDITOR
        monkeypatch.setenv('EDITOR', 'editor')

        # Execute
        result = spack_manager.offer_package_edit(packages_to_edit)

        # Verify return value
        assert result is True

        # Verify printed output
        out = capsys.readouterr().out
        assert "Launching editors for 1 package(s)" in out
        assert "Opening editor..." in out
        assert f"Recipe path: {recipe_file}" in out
        assert "✓ Finished editing dummy_package@1.2.3" in out

        # Verify subprocess.run was called with the correct command
        mock_run.assert_called_once_with(['editor', str(recipe_file)], check=True)

    @patch.object(SpackManager, '_fetch_and_write_package_directory', return_value=True)
    @patch.object(SpackManager, '_add_git_commit_version_to_recipe', return_value=True)
    def test_process_pending_git_commits_success(self, mock_add_git, mock_fetch_local, spack_manager, tmp_path):
        """Test successful processing of pending Git commit operations."""
        pkg = "my-package"
        ver = "0.1.0"
        commit = "abcdef1234567890"
        # queue one git‐commit operation
        spack_manager.add_pending_git_commit(pkg, ver, commit)

        # run the processor
        result = spack_manager._process_pending_git_commits(str(tmp_path))

        # one entry should be returned
        assert len(result) == 1
        entry = result[0]

        expected_path = tmp_path / "envrepo" / "packages" / pkg / "package.py"
        assert entry['package_name'] == pkg
        assert entry['version'] == ver
        assert entry['commit_hash'] == commit
        assert entry['operation'] == 'git_commit'
        assert entry['use_local_copy'] is True
        assert entry['found_in_local'] is True
        assert entry['found_in_remote'] is False
        assert entry['recipe_path'] == str(expected_path)

        # pending list is cleared
        assert spack_manager.pending_git_commits == []

    def test_add_git_commit_version_to_recipe_inserts_after_first_version(self, spack_manager, tmp_path):
        """Test insertion after the first version() declaration."""
        version = "3.0.0"
        commit = "nonexist"
        pkg_file = tmp_path / "package.py"
        content = """\
class Foo(Package):
    version("1.0.0", commit="abc123")
    do_something()
    version("2.0.0", commit="abc123")
"""
        pkg_file.write_text(content)

        success = spack_manager._add_git_commit_version_to_recipe(pkg_file, version, commit)
        assert success is True

        lines = pkg_file.read_text().splitlines()
        # inserted immediately after the first version line
        idx = next(i for i, line in enumerate(lines) if 'version("1.0.0"' in line)
        assert lines[idx+1].strip() == f'version("{version}", commit="{commit}")'
        # only one new version line
        assert sum(f'version("{version}"' in l for l in lines) == 1

    def test_add_git_commit_version_to_recipe_inserts_after_class_if_no_version(self, spack_manager, tmp_path):
        """Test insertion after class definition when no version() exists."""
        version = "4.0.0"
        commit = "cafebabe"
        pkg_file = tmp_path / "package.py"
        content = """\
class Bar(Package):
    # no versions here
    def build(self): pass
"""
        pkg_file.write_text(content)

        success = spack_manager._add_git_commit_version_to_recipe(pkg_file, version, commit)
        assert success is True

        lines = pkg_file.read_text().splitlines()
        idx = next(i for i, line in enumerate(lines) if 'class Bar(Package)' in line)
        # blank line then inserted version line
        assert lines[idx+1] == ""
        assert lines[idx+2].strip() == f'version("{version}", commit="{commit}")'

    def test_add_git_commit_version_to_recipe_returns_false_when_no_target(self, spack_manager, tmp_path):
        """Test that method returns False if neither version() nor class() found."""
        version = "5.0.0"
        commit = "00112233"
        pkg_file = tmp_path / "package.py"
        content = """\
# random file without class or version
def func(): pass
"""
        pkg_file.write_text(content)

        success = spack_manager._add_git_commit_version_to_recipe(pkg_file, version, commit)
        assert success is False
        # file unchanged
        assert pkg_file.read_text() == content

    def test_add_git_commit_version_to_recipe_handles_exceptions(self, spack_manager):
        """Test that IO errors are caught and False is returned."""
        missing = "/nonexistent/path/package.py"
        success = spack_manager._add_git_commit_version_to_recipe(missing, "1.2.3", "nonexist")
        assert success is False

    @patch('requests.get')
    def test_fetch_and_write_all_remote_files_success(self, mock_get, spack_manager, tmp_path):
        """Fetch and write all remote supporting files (HTTP 200 path)."""
        pkg = "foo"
        # Override config to use a known org/repo/branch
        spack_manager.config.get = lambda k, default=None: {
            "base_url": "https://github.com/testorg/testrepo.git",
            "branch":   "testbranch"
        } if k == "spack_repository" else default

        # Prepare the package directory
        package_dir = tmp_path / "packages" / pkg
        package_dir.mkdir(parents=True, exist_ok=True)

        # Simulate GitHub API listing
        file_info = {
            "type":         "file",
            "name":         "patch.diff",
            "download_url": "https://raw.githubusercontent.com/testorg/testrepo/refs/heads/testbranch/"
                            "var/spack/repos/builtin/packages/foo/patch.diff"
        }
        listing = [file_info]

        def fake_get(url, params=None, timeout=None):
            # first call: listing
            if "api.github.com" in url:
                resp = MagicMock(status_code=200)
                resp.json.return_value = listing
                return resp
            # second call: download
            elif url == file_info["download_url"]:
                resp = MagicMock(status_code=200)
                resp.content = b"PATCHEMBED"
                return resp
            # any other URL
            return MagicMock(status_code=404)

        mock_get.side_effect = fake_get

        # Execute
        spack_manager._fetch_and_write_all_remote_files(pkg, package_dir)

        # Verify that patch.diff was written with the correct content
        out_file = package_dir / "patch.diff"
        assert out_file.exists()
        assert out_file.read_bytes() == b"PATCHEMBED"


    @patch.object(SpackManager, '_run_spack_command')
    def test__get_upstream_package_info_parses_variants_and_excludes_patches(
        self, mock_run, spack_manager, tmp_path
    ):
        """Should parse format with :FLAGS: and :EXTERNAL: fields and strip out `patches=`."""
        pkg_name = 'foo'
        packages = [{'name': pkg_name}]
        # simulate spack find output with patches= to be removed
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0,
            stdout='foo:VERSION:1.2.3:VARIANTS:+mpi patches=abc,def:FLAGS::EXTERNAL:False\n'
        )

        info = spack_manager._get_upstream_package_info(tmp_path, packages)

        assert pkg_name in info
        assert info[pkg_name]['variants'] == '+mpi'
        assert info[pkg_name]['version'] == '1.2.3'

    @patch.object(SpackManager, '_run_spack_command')
    def test__get_upstream_package_info_uses_current_version_if_provided(
        self, mock_run, spack_manager, tmp_path
    ):
        """Should use pkg['current_version'] instead of parsed version."""
        pkg_name = 'bar'
        current_version = '9.9.9'
        packages = [{'name': pkg_name, 'current_version': current_version}]
        mock_run.return_value = CompletedProcess(
            args=[], returncode=0,
            stdout='bar:VERSION:8.8.8:VARIANTS:+openmp:FLAGS::EXTERNAL:False\n'
        )

        info = spack_manager._get_upstream_package_info(tmp_path, packages)

        assert pkg_name in info
        assert info[pkg_name]['variants'] == '+openmp'
        # version key must come from current_version, not parsed "8.8.8"
        assert info[pkg_name]['version'] == current_version

    @patch.object(SpackManager, '_run_spack_command')
    def test__get_upstream_package_info_handles_no_output_and_errors(
        self, mock_run, spack_manager, tmp_path
    ):
        """Should return empty dict on non-zero return, empty stdout, or exceptions."""
        # non-zero return code
        mock_run.return_value = CompletedProcess(args=[], returncode=1, stdout='')
        assert spack_manager._get_upstream_package_info(tmp_path, [{'name':'pkg'}]) == {}

        # zero return but no content
        mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout='\n')
        assert spack_manager._get_upstream_package_info(tmp_path, [{'name':'pkg'}]) == {}

        # exception during command
        mock_run.side_effect = RuntimeError("boom")
        assert spack_manager._get_upstream_package_info(tmp_path, [{'name':'pkg'}]) == {}

    @patch.object(SpackManager, '_run_spack_command')
    def test__get_upstream_package_info_metapackage_tie_breaker(
        self, mock_run, spack_manager, tmp_path
    ):
        """Should prefer duplicate package spec matching metapackage dependency output."""
        packages = [{
            'name': 'hdf5',
            'application_metapackage': 'global-workflow-env',
        }]

        all_packages_result = CompletedProcess(
            args=[], returncode=0,
            stdout=(
                'hdf5:VERSION:1.14.0:VARIANTS:+mpi:FLAGS::EXTERNAL:False\n'
                'hdf5:VERSION:1.12.2:VARIANTS:~mpi:FLAGS::EXTERNAL:False\n'
            )
        )
        deps_result = CompletedProcess(
            args=[], returncode=0,
            stdout='hdf5:VERSION:1.14.0:VARIANTS:+mpi:FLAGS::EXTERNAL:False\n'
        )

        # First call is metapackage deps query, second call is full env package query.
        mock_run.side_effect = [deps_result, all_packages_result]

        info = spack_manager._get_upstream_package_info(tmp_path, packages)

        assert info['hdf5']['version'] == '1.14.0'
        assert info['hdf5']['variants'] == '+mpi'

    @patch.object(SpackManager, '_run_spack_command')
    def test__get_upstream_package_info_current_version_overrides_metapackage_tie_breaker(
        self, mock_run, spack_manager, tmp_path
    ):
        """current_version should still override version even when tie-breaker data exists."""
        packages = [{
            'name': 'hdf5',
            'current_version': '1.12.2',
            'application_metapackage': 'global-workflow-env',
        }]

        all_packages_result = CompletedProcess(
            args=[], returncode=0,
            stdout=(
                'hdf5:VERSION:1.14.0:VARIANTS:+mpi:FLAGS::EXTERNAL:False\n'
                'hdf5:VERSION:1.12.2:VARIANTS:~mpi:FLAGS::EXTERNAL:False\n'
            )
        )
        deps_result = CompletedProcess(
            args=[], returncode=0,
            stdout='hdf5:VERSION:1.14.0:VARIANTS:+mpi:FLAGS::EXTERNAL:False\n'
        )

        mock_run.side_effect = [deps_result, all_packages_result]

        info = spack_manager._get_upstream_package_info(tmp_path, packages)

        assert info['hdf5']['version'] == '1.12.2'

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_definitions_branch(self, mock_upstream, spack_manager, tmp_path):
        """When 'definitions' exist, packages go into definitions->packages."""
        # Prepare upstream env dir + spack.yaml
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
  definitions:
  - compilers: ['%gcc']
  - packages: [existingA,existingB]
""")

        # Create dummy target env path (unused in this test)
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define package foo
        packages = [
            {"name": "foo",    "version": "2.0.0", "variants": "opt"},
        ]

        # Dummy platform with no cpu_target
        class DummyPlatform:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], DummyPlatform()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # Find the 'packages' entry inside definitions
        defs = sp["definitions"]
        # definitions is a list: ('compilers', 'packages')
        pkgs_def = next(d for d in defs if "packages" in d)["packages"]
        # Should only contain foo, not scotch or existing*
        assert pkgs_def == ["foo@=2.0.0 opt"]

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_with_packages_needing_edit(self, mock_upstream, spack_manager, tmp_path):
        """Test that custom repository is added when packages_needing_edit is provided."""
        # Prepare upstream env dir + spack.yaml
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "test-pkg", "version": "1.0.0", "variants": ""},
        ]

        # Define packages needing custom recipes
        packages_needing_edit = [
            {
                'package_name': 'test-pkg',
                'version': '1.0.0',
                'recipe_path': '/some/path/package.py'
            }
        ]

        # Dummy platform with no cpu_target
        class DummyPlatform:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, packages_needing_edit, DummyPlatform()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # Should have custom repo added at beginning
        assert "repos" in sp
        assert "$env/envrepo" in sp["repos"]
        assert sp["repos"][0] == "$env/envrepo"  # Should be first for priority

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_without_packages_needing_edit(self, mock_upstream, spack_manager, tmp_path):
        """Test that custom repository is not added when packages_needing_edit is empty."""
        # Prepare upstream env dir + spack.yaml
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "regular-pkg", "version": "2.0.0", "variants": ""},
        ]

        # Empty packages_needing_edit
        packages_needing_edit = []

        # Dummy platform with no cpu_target
        class DummyPlatform:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, packages_needing_edit, DummyPlatform()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # Should NOT have custom repo added
        assert "repos" not in sp or "$env/envrepo" not in sp.get("repos", [])

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_with_existing_repos(self, mock_upstream, spack_manager, tmp_path):
        """Test that custom repository is prepended to existing repos list."""
        # Prepare upstream env dir + spack.yaml with existing repos
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
  repos:
  - /existing/repo1
  - /existing/repo2
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "custom-pkg", "version": "1.0.0", "variants": ""},
        ]

        # Define packages needing custom recipes
        packages_needing_edit = [
            {
                'package_name': 'custom-pkg',
                'version': '1.0.0',
                'recipe_path': '/some/path/package.py'
            }
        ]

        # Dummy platform with no cpu_target
        class DummyPlatform:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, packages_needing_edit, DummyPlatform()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # Should have custom repo at the beginning
        assert "repos" in sp
        assert sp["repos"][0] == "$env/envrepo"
        assert "/existing/repo1" in sp["repos"]
        assert "/existing/repo2" in sp["repos"]

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_with_cpu_target(self, mock_upstream, spack_manager, tmp_path):
        """Test that cpu_target is properly set when provided in platform config."""
        # Prepare upstream env dir + spack.yaml
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "test-pkg", "version": "1.0.0", "variants": ""},
        ]

        # Platform with cpu_target
        class PlatformWithTarget:
            config = {'cpu_target': 'x86_64_v3'}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], PlatformWithTarget()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # Should have cpu target set for all packages
        assert "packages" in sp
        assert "all" in sp["packages"]
        assert "target" in sp["packages"]["all"]
        assert sp["packages"]["all"]["target"] == ["x86_64_v3"]

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_without_cpu_target(self, mock_upstream, spack_manager, tmp_path):
        """Test that cpu_target is not set when not provided in platform config."""
        # Prepare upstream env dir + spack.yaml
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "test-pkg", "version": "1.0.0", "variants": ""},
        ]

        # Platform without cpu_target (empty config or empty string)
        class PlatformWithoutTarget:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], PlatformWithoutTarget()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # Should NOT have target set for all packages
        # (Note: 'all' may exist for other reasons, but shouldn't have 'target')
        if "packages" in sp and "all" in sp["packages"]:
            assert "target" not in sp["packages"]["all"]

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_with_empty_cpu_target(self, mock_upstream, spack_manager, tmp_path):
        """Test that cpu_target is not set when it's an empty string."""
        # Prepare upstream env dir + spack.yaml
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "test-pkg", "version": "1.0.0", "variants": ""},
        ]

        # Platform with empty cpu_target
        class PlatformWithEmptyTarget:
            config = {'cpu_target': ''}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], PlatformWithEmptyTarget()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # Should NOT have target set (empty string is falsy)
        if "packages" in sp and "all" in sp["packages"]:
            assert "target" not in sp["packages"]["all"]

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_cpu_target_with_logger(self, mock_upstream, spack_manager, tmp_path):
        """Test that cpu_target setting is logged when logger is available."""
        # Setup logger
        spack_manager.logger = Mock()
        
        # Prepare upstream env dir + spack.yaml
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "test-pkg", "version": "1.0.0", "variants": ""},
        ]

        # Platform with cpu_target
        class PlatformWithTarget:
            config = {'cpu_target': 'haswell'}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], PlatformWithTarget()
        )

        # Verify logging
        spack_manager.logger.info.assert_called()
        log_calls = [call[0][0] for call in spack_manager.logger.info.call_args_list]
        assert any("Setting CPU target for all packages: haswell" in call for call in log_calls)

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_combined_repos_and_cpu_target(self, mock_upstream, spack_manager, tmp_path):
        """Test that both custom repos and cpu_target work together correctly."""
        # Setup logger
        spack_manager.logger = Mock()
        
        # Prepare upstream env dir + spack.yaml
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "custom-pkg", "version": "1.0.0", "variants": "+feature"},
        ]

        # Define packages needing custom recipes
        packages_needing_edit = [
            {
                'package_name': 'custom-pkg',
                'version': '1.0.0',
                'recipe_path': '/some/path/package.py'
            }
        ]

        # Platform with cpu_target
        class PlatformWithTarget:
            config = {'cpu_target': 'zen2'}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, packages_needing_edit, PlatformWithTarget()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # Should have both custom repo and cpu target set
        assert "repos" in sp
        assert sp["repos"][0] == "$env/envrepo"
        
        assert "packages" in sp
        assert "all" in sp["packages"]
        assert "target" in sp["packages"]["all"]
        assert sp["packages"]["all"]["target"] == ["zen2"]
        
        # Verify logging
        log_calls = [call[0][0] for call in spack_manager.logger.info.call_args_list]
        assert any("Setting CPU target for all packages: zen2" in call for call in log_calls)

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_missing_spack_section(self, mock_upstream, spack_manager, tmp_path):
        """Test that 'spack' section is created if missing from upstream yaml."""
        # Prepare upstream env dir + spack.yaml WITHOUT 'spack' key
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
# Empty or malformed spack.yaml
some_other_key: value
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "test-pkg", "version": "1.0.0", "variants": ""},
        ]

        # Dummy platform
        class DummyPlatform:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], DummyPlatform()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        
        # Should have created 'spack' section
        assert "spack" in cfg
        assert "specs" in cfg["spack"]
        assert cfg["spack"]["specs"] == ["test-pkg@=1.0.0"]

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_definitions_else_branch(self, mock_upstream, spack_manager, tmp_path):
        """Test else branch that deletes definitions when they don't match expected structure."""
        # Prepare upstream env dir + spack.yaml with non-standard definitions
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
  definitions:
  - custom_def: [item1, item2]
  - another_def: [item3]
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "pkg1", "version": "1.0.0", "variants": ""},
            {"name": "pkg2", "version": "2.0.0", "variants": "+opt"},
        ]

        # Dummy platform
        class DummyPlatform:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], DummyPlatform()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # Definitions should be deleted (else branch)
        assert "definitions" not in sp
        
        # Specs should be set directly
        assert "specs" in sp
        assert "pkg1@=1.0.0" in sp["specs"]
        assert "pkg2@=2.0.0+opt" in sp["specs"]  # No space before variants in actual output

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_definitions_wrong_length(self, mock_upstream, spack_manager, tmp_path):
        """Test else branch when definitions has wrong length (not 2 items)."""
        # Prepare upstream env dir + spack.yaml with single definition
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
  definitions:
  - packages: [existing1, existing2]
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "newpkg", "version": "1.0.0", "variants": ""},
        ]

        # Dummy platform
        class DummyPlatform:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], DummyPlatform()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # Definitions should be deleted
        assert "definitions" not in sp
        assert sp["specs"] == ["newpkg@=1.0.0"]

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={
        'test-pkg': {'version': '1.0.0', 'variants': '+feature -debug'}
    })
    def test__create_spack_yaml_variant_overrides_nested_if(self, mock_upstream, spack_manager, tmp_path):
        """Test nested if statement after 'Add variant overrides if available' comment."""
        # Prepare upstream env dir + spack.yaml
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages with variants
        packages = [
            {"name": "test-pkg", "version": "1.0.0", "variants": "+feature"},
        ]

        # Dummy platform
        class DummyPlatform:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], DummyPlatform()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # Should have package with variants
        assert "packages" in sp
        assert "test-pkg:" in sp["packages"]
        assert "variants" in sp["packages"]["test-pkg:"]
        assert sp["packages"]["test-pkg:"]["variants"] == "+feature -debug"
        assert "version" in sp["packages"]["test-pkg:"]
        assert sp["packages"]["test-pkg:"]["version"] == ["1.0.0"]

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={
        'pkg-with-version': {'version': '2.0.0', 'variants': ''}
    })
    def test__create_spack_yaml_version_only_creates_package_key(self, mock_upstream, spack_manager, tmp_path):
        """Test that package key is created when only version is available (nested if)."""
        # Prepare upstream env dir + spack.yaml
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "pkg-with-version", "version": "2.0.0", "variants": ""},
        ]

        # Dummy platform
        class DummyPlatform:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], DummyPlatform()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # Should have package with version
        assert "packages" in sp
        assert "pkg-with-version:" in sp["packages"]
        assert "version" in sp["packages"]["pkg-with-version:"]
        assert sp["packages"]["pkg-with-version:"]["version"] == ["2.0.0"]
        # Should not have variants (empty string)
        assert "variants" not in sp["packages"]["pkg-with-version:"]

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={
        'pkg-with-variants': {'version': '', 'variants': '+option'}
    })
    def test__create_spack_yaml_variants_only_creates_package_key(self, mock_upstream, spack_manager, tmp_path):
        """Test that package key is created when only variants are available (nested if after variants)."""
        # Prepare upstream env dir + spack.yaml
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "pkg-with-variants", "version": "1.0.0", "variants": ""},
        ]

        # Dummy platform
        class DummyPlatform:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], DummyPlatform()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # Should have package with variants
        assert "packages" in sp
        assert "pkg-with-variants:" in sp["packages"]
        assert "variants" in sp["packages"]["pkg-with-variants:"]
        assert sp["packages"]["pkg-with-variants:"]["variants"] == "+option"
        # Should not have version (empty string)
        assert "version" not in sp["packages"]["pkg-with-variants:"]

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_coloned_name_exists(self, mock_upstream, spack_manager, tmp_path):
        """Test the 'if coloned_name in spack_section[packages]' branch."""
        # Prepare upstream env dir + spack.yaml with cmake: already defined
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
  packages:
    cmake::
      version: [3.20.0]
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "test-pkg", "version": "1.0.0", "variants": ""},
        ]

        # Dummy platform
        class DummyPlatform:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], DummyPlatform()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # cmake: should exist and have buildable set to False
        # The code checks for "cmake:" (coloned_name), and if it exists in packages,
        # sets pkg_name to "cmake:" which is then used to set buildable
        assert "packages" in sp
        assert "cmake:" in sp["packages"]
        assert sp["packages"]["cmake:"]["buildable"] is False

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_coloned_name_not_exists(self, mock_upstream, spack_manager, tmp_path):
        """Test the elif branch when coloned_name not in packages."""
        # Prepare upstream env dir + spack.yaml without cmake
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "test-pkg", "version": "1.0.0", "variants": ""},
        ]

        # Dummy platform
        class DummyPlatform:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], DummyPlatform()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # All always_upstream_packages should be set as non-buildable
        assert "packages" in sp
        for pkg_name in ['cmake', 'gmake', 'ecbuild', 'bison', 'diffutils']:
            assert pkg_name in sp["packages"]
            assert sp["packages"][pkg_name]["buildable"] is False

    @patch.object(SpackManager, '_get_upstream_package_info', return_value={})
    def test__create_spack_yaml_existing_package_without_colon(self, mock_upstream, spack_manager, tmp_path):
        """Test when package exists without colon (neither branch of coloned_name check)."""
        # Prepare upstream env dir + spack.yaml with cmake (no colon)
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text(r"""
spack:
  specs: []
  packages:
    cmake:
      version: [3.20.0]
""")

        # Create dummy target env path
        new_env = tmp_path / "env"
        new_env.mkdir()

        # Define packages
        packages = [
            {"name": "test-pkg", "version": "1.0.0", "variants": ""},
        ]

        # Dummy platform
        class DummyPlatform:
            config = {}

        # Call the method
        out = spack_manager._create_spack_yaml(
            str(upstream), packages, new_env, [], DummyPlatform()
        )

        # Load back to verify
        yaml = YAML(typ="safe")
        cfg = yaml.load(out)
        sp = cfg["spack"]

        # cmake already exists (without colon), so neither condition is true
        # pkg_name stays as 'cmake' and buildable is set on it
        assert "packages" in sp
        assert "cmake" in sp["packages"]
        assert sp["packages"]["cmake"]["buildable"] is False

    @pytest.mark.parametrize("package_name,should_filter", [
        ("scotch", True),
        ("hdf5", False),
    ])
    def test_filter_package_content(self, spack_manager, package_name, should_filter):
        """Test filtering of package content.
        
        For scotch: comments out conflicts("%oneapi") and depends_on("bison.*")
        For other packages: leaves content unchanged
        """
        content = '''# Package
class Package(Package):
    version("1.0", sha256="abc123")
    conflicts("%oneapi")
    conflicts("%intel")
    depends_on("bison@3.4:")
    depends_on("mpi")
    depends_on("flex@2.6:")
    
    def install(self):
        # Indented lines
        conflicts("%oneapi")
        depends_on("bison@3.8:")
'''
        
        filtered = spack_manager._filter_package_content(package_name, content)
        
        if should_filter:
            # For scotch: verify patterns are commented
            lines = filtered.split('\n')
            for line in lines:
                # All conflicts("%oneapi") should be commented
                if 'conflicts("%oneapi")' in line:
                    assert line.strip().startswith('#'), f"Line should be commented: {line}"
                # All bison dependencies should be commented
                if 'bison' in line.lower() and 'depends_on' in line.lower():
                    assert line.strip().startswith('#'), f"Line should be commented: {line}"

        else:
            # For non-scotch packages: content unchanged
            assert filtered == content

    @patch.object(SpackManager, '_run_spack_command')
    def test_get_upstream_package_info_with_compiler_flags(self, mock_run_cmd, spack_manager, tmp_path):
        """Test parsing packages with compiler flags from FLAGS field."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """zlib:VERSION:1.2.11:VARIANTS:+pic:FLAGS:cflags="-O2":EXTERNAL:False
hdf5:VERSION:1.10.7:VARIANTS:+mpi +fortran:FLAGS:cflags="-O3" fflags="-fdefault-real-8":EXTERNAL:False
netcdf-c:VERSION:4.8.1:VARIANTS:+mpi:FLAGS::EXTERNAL:False
cmake:VERSION:3.20.0:VARIANTS:+shared:FLAGS::EXTERNAL:True
"""
        mock_result.stderr = ""
        mock_run_cmd.return_value = mock_result
        
        upstream_path = tmp_path / "upstream"
        upstream_path.mkdir()
        
        result = spack_manager._get_upstream_package_info(upstream_path, [])
        
        # Verify zlib has compiler flags
        assert "zlib" in result
        assert result["zlib"]["compiler_flags"] == 'cflags="-O2"'
        assert result["zlib"]["variants"] == "+pic"
        assert result["zlib"]["version"] == "1.2.11"
        
        # Verify hdf5 has multiple compiler flags
        assert "hdf5" in result
        assert result["hdf5"]["compiler_flags"] == 'cflags="-O3" fflags="-fdefault-real-8"'
        assert result["hdf5"]["variants"] == "+mpi +fortran"
        
        # Verify netcdf-c has no compiler flags
        assert "netcdf-c" in result
        assert "compiler_flags" not in result["netcdf-c"]
        assert result["netcdf-c"]["variants"] == "+mpi"
        
        # Verify cmake is filtered out (external)
        assert "cmake" not in result

    @patch.object(SpackManager, '_run_spack_command')
    @patch.object(SpackManager, '_get_upstream_package_info')
    def test_create_spack_yaml_compiler_flags_in_require(self, mock_get_info, mock_run_cmd, spack_manager, tmp_path):
        """Test compiler flags are added to packages:<pkg>:require field."""
        mock_get_info.return_value = {
            "zlib": {
                "version": "1.2.11",
                "variants": "+pic",
                "compiler_flags": 'cflags="-O2"'
            }
        }
        
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        yaml_path.write_text("spack:\n  specs: []\n  packages: {}\n")
        
        new_env = tmp_path / "env"
        new_env.mkdir()
        
        class DummyPlatform:
            config = {}
        
        result_yaml = spack_manager._create_spack_yaml(str(upstream), [], new_env, [], DummyPlatform())
        
        yaml = YAML(typ="safe")
        cfg = yaml.load(result_yaml)
        
        # Verify compiler flags are in require field
        assert "zlib:" in cfg["spack"]["packages"]
        assert "require" in cfg["spack"]["packages"]["zlib:"]
        require_spec = cfg["spack"]["packages"]["zlib:"]["require"][0]
        assert require_spec == 'cflags="-O2"'
        
        # Verify variants are separate
        assert "variants" in cfg["spack"]["packages"]["zlib:"]
        assert cfg["spack"]["packages"]["zlib:"]["variants"] == "+pic"

    @patch.object(SpackManager, '_run_spack_command')
    @patch.object(SpackManager, '_get_upstream_package_info')
    def test_create_spack_yaml_no_duplicate_package_entries(self, mock_get_info, mock_run_cmd, spack_manager, tmp_path):
        """Test that packages don't get duplicate entries (with and without colon)."""
        mock_get_info.return_value = {
            "gcc-runtime": {
                "version": "11.2.0",
                "variants": "+shared",
                "compiler_flags": 'cflags="-O2"'
            }
        }
        
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        # Upstream has gcc-runtime without colon
        yaml_path.write_text("""spack:
  specs: []
  packages:
    gcc-runtime:
      buildable: false
""")
        
        new_env = tmp_path / "env"
        new_env.mkdir()
        
        class DummyPlatform:
            config = {}
        
        result_yaml = spack_manager._create_spack_yaml(str(upstream), [], new_env, [], DummyPlatform())
        
        yaml = YAML(typ="safe")
        cfg = yaml.load(result_yaml)
        
        # Should only have gcc-runtime: (with colon), not both versions
        assert "gcc-runtime:" in cfg["spack"]["packages"]
        assert "gcc-runtime" not in cfg["spack"]["packages"]  # No entry without colon
        
        # Verify original buildable setting is preserved
        assert cfg["spack"]["packages"]["gcc-runtime:"]["buildable"] is False
        
        # Verify new settings were added
        assert "require" in cfg["spack"]["packages"]["gcc-runtime:"]
        assert cfg["spack"]["packages"]["gcc-runtime:"]["require"][0] == 'cflags="-O2"'

    @patch.object(SpackManager, '_run_spack_command')
    @patch.object(SpackManager, '_get_upstream_package_info')
    def test_create_spack_yaml_skips_external_packages(self, mock_get_info, mock_run_cmd, spack_manager, tmp_path):
        """Test that external packages are filtered by _get_upstream_package_info."""
        # _get_upstream_package_info already filters out externals
        mock_get_info.return_value = {
            "hdf5": {
                "version": "1.10.7",
                "variants": "+mpi",
                "compiler_flags": 'cflags="-O3"'
            }
            # cmake not returned because it's external
        }
        
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        # cmake is configured as external in upstream
        yaml_path.write_text("""spack:
  specs: []
  packages:
    cmake:
      externals:
      - spec: cmake@3.20.0
        prefix: /usr
      buildable: false
""")
        
        new_env = tmp_path / "env"
        new_env.mkdir()
        
        class DummyPlatform:
            config = {}
        
        result_yaml = spack_manager._create_spack_yaml(str(upstream), [], new_env, [], DummyPlatform())
        
        yaml = YAML(typ="safe")
        cfg = yaml.load(result_yaml)
        
        # cmake should still exist with original external config (untouched)
        assert "cmake" in cfg["spack"]["packages"]
        assert "externals" in cfg["spack"]["packages"]["cmake"]
        assert cfg["spack"]["packages"]["cmake"]["buildable"] is False
        
        # hdf5 should have been added
        assert "hdf5:" in cfg["spack"]["packages"]
        assert "require" in cfg["spack"]["packages"]["hdf5:"]

    @patch.object(SpackManager, '_run_spack_command')
    @patch.object(SpackManager, '_get_upstream_package_info')
    def test_create_spack_yaml_skips_external_packages_with_colon(self, mock_get_info, mock_run_cmd, spack_manager, tmp_path):
        """Test that external packages (with colon keys) are filtered by _get_upstream_package_info."""
        # _get_upstream_package_info filters out externals before returning
        mock_get_info.return_value = {
            "hdf5": {
                "version": "1.10.7",
                "variants": "+mpi"
            }
            # openmpi not returned because it's external
        }
        
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        yaml_path = upstream / "spack.yaml"
        # openmpi configured as external
        yaml_path.write_text("""spack:
  specs: []
  packages:
    openmpi:
      externals:
      - spec: openmpi@4.1.1
        prefix: /opt/openmpi
      buildable: false
""")
        
        new_env = tmp_path / "env"
        new_env.mkdir()
        
        class DummyPlatform:
            config = {}
        
        result_yaml = spack_manager._create_spack_yaml(str(upstream), [], new_env, [], DummyPlatform())
        
        yaml = YAML(typ="safe")
        cfg = yaml.load(result_yaml)
        
        # openmpi should still exist untouched with original external config
        assert "openmpi" in cfg["spack"]["packages"]
        assert "externals" in cfg["spack"]["packages"]["openmpi"]
        
        # hdf5 should have been added
        assert "hdf5:" in cfg["spack"]["packages"]

    @patch.object(SpackManager, '_run_spack_command')
    def test_get_upstream_package_hashes(self, mock_run_cmd, spack_manager, tmp_path):
        """Test get_upstream_package_hashes retrieves hashes and specs correctly."""
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        
        # Mock spack find output - spack find filters by package name, so only hdf5 results
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """abc1234:SPEC:hdf5@1.10.7+mpi
xyz9876:SPEC:hdf5@1.10.6~mpi"""
        mock_run_cmd.return_value = mock_result
        
        result = spack_manager.get_upstream_package_hashes("hdf5", str(upstream))
        
        # Should return list of dicts with hash and spec
        assert len(result) == 2
        assert result[0] == {"hash": "abc1234", "spec": "hdf5@1.10.7+mpi"}
        assert result[1] == {"hash": "xyz9876", "spec": "hdf5@1.10.6~mpi"}
        
        # Verify correct spack command was called
        mock_run_cmd.assert_called_once()
        call_args = mock_run_cmd.call_args[0][0]
        assert "find" in call_args
        assert "{hash:7}:SPEC:{name}{@version}{variants}" in call_args
        assert "hdf5" in call_args
    
    @patch.object(SpackManager, '_run_spack_command')
    def test_get_upstream_package_hashes_no_matches(self, mock_run_cmd, spack_manager, tmp_path):
        """Test get_upstream_package_hashes returns empty list when no matches found."""
        upstream = tmp_path / "upstream"
        upstream.mkdir()
        
        # Mock empty output
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run_cmd.return_value = mock_result
        
        result = spack_manager.get_upstream_package_hashes("nonexistent-pkg", str(upstream))
        
        assert result == []
    
    @patch.object(SpackManager, '_run_spack_command')
    def test_get_upstream_package_hashes_uses_provided_upstream_path(self, mock_run_cmd, spack_manager, tmp_path):
        """Test get_upstream_package_hashes uses provided upstream path instead of config."""
        custom_upstream = tmp_path / "custom_upstream"
        custom_upstream.mkdir()
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "abc1234:SPEC:pkg@1.0.0"
        mock_run_cmd.return_value = mock_result
        
        spack_manager.get_upstream_package_hashes("pkg", str(custom_upstream))
        
        # Verify the custom path was passed to spack find
        call_args = mock_run_cmd.call_args[0][0]
        assert str(custom_upstream) in " ".join(call_args)
