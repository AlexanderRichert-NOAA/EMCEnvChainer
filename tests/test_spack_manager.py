"""Unit tests for SpackManager class."""

import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import subprocess

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
    
    def test_build_spec_string_with_name_only(self, spack_manager):
        """Test _build_spec_string with package name only."""
        pkg = {"name": "cmake"}
        result = spack_manager._build_spec_string(pkg)
        assert result == "cmake"
    
    def test_build_spec_string_with_version(self, spack_manager):
        """Test _build_spec_string with package name and version."""
        pkg = {"name": "cmake", "version": "3.20.0"}
        result = spack_manager._build_spec_string(pkg)
        assert result == "cmake@3.20.0"
    
    def test_build_spec_string_with_variants(self, spack_manager):
        """Test _build_spec_string with package name and variants."""
        pkg = {"name": "cmake", "variants": "+shared +ssl"}
        result = spack_manager._build_spec_string(pkg)
        assert result == "cmake+shared +ssl"
    
    def test_build_spec_string_with_variants_no_plus(self, spack_manager):
        """Test _build_spec_string with package name and variants without leading +."""
        pkg = {"name": "cmake", "variants": "shared ssl"}
        result = spack_manager._build_spec_string(pkg)
        assert result == "cmake shared ssl"
    
    def test_build_spec_string_complete(self, spack_manager):
        """Test _build_spec_string with all components."""
        pkg = {"name": "cmake", "version": "3.20.0", "variants": "+shared +ssl"}
        result = spack_manager._build_spec_string(pkg)
        assert result == "cmake@3.20.0+shared +ssl"
    
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
    
    def test_queue_checksum_operation(self, spack_manager):
        """Test queuing a checksum operation."""
        spack_manager.queue_checksum_operation("test-pkg", "1.0.0")
        
        assert len(spack_manager.pending_checksums) == 1
        operation = spack_manager.pending_checksums[0]
        assert operation["package_name"] == "test-pkg"
        assert operation["version"] == "1.0.0"
        assert operation["operation"] == "checksum"
    
    def test_get_local_package_path(self, spack_manager):
        """Test getting local package path."""
        result = spack_manager.get_local_package_path("cmake")
        expected = str(spack_manager.spack_root / "var" / "spack" / "repos" / "builtin" / "packages" / "cmake" / "package.py")
        assert result == expected
    
    def test_test_spack_installation_success(self, spack_manager):
        """Test successful spack installation check."""
        with patch.object(spack_manager, '_run_spack_command') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            result = spack_manager.test_spack_installation()
            assert result is True
            mock_run.assert_called_once_with(['--version'])
    
    def test_test_spack_installation_failure(self, spack_manager):
        """Test failed spack installation check."""
        with patch.object(spack_manager, '_run_spack_command') as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_run.return_value = mock_result
            
            result = spack_manager.test_spack_installation()
            assert result is False
    
    def test_test_spack_installation_exception(self, spack_manager):
        """Test spack installation check with exception."""
        with patch.object(spack_manager, '_run_spack_command') as mock_run:
            mock_run.side_effect = Exception("Command failed")
            
            result = spack_manager.test_spack_installation()
            assert result is False
    
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
    
    @patch('requests.get')
    def test_check_version_in_remote_repo_success(self, mock_get, spack_manager):
        """Test successful version check in remote repository."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'version("1.0.0", sha256="abc123")'
        mock_get.return_value = mock_response
        
        result = spack_manager.check_version_in_remote_repo("test-pkg", "1.0.0")
        assert result is True
    
    @patch('requests.get')
    def test_check_version_in_remote_repo_not_found(self, mock_get, spack_manager):
        """Test version not found in remote repository."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'version("2.0.0", sha256="def456")'
        mock_get.return_value = mock_response
        
        result = spack_manager.check_version_in_remote_repo("test-pkg", "1.0.0")
        assert result is False
    
    @patch('requests.get')
    def test_check_version_in_remote_repo_http_error(self, mock_get, spack_manager):
        """Test HTTP error when checking version in remote repository."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = spack_manager.check_version_in_remote_repo("test-pkg", "1.0.0")
        assert result is False
    
    @patch('requests.get')
    def test_check_version_in_remote_repo_exception(self, mock_get, spack_manager):
        """Test exception when checking version in remote repository."""
        mock_get.side_effect = Exception("Network error")
        
        result = spack_manager.check_version_in_remote_repo("test-pkg", "1.0.0")
        assert result is False
    
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
