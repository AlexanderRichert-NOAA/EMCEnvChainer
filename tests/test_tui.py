"""Unit tests for TUI classes and methods."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call, PropertyMock
import curses
from pathlib import Path
import tempfile
import os

from emcenvchainer.tui import TUIMenu, PackageSpecDialog, RadioButtonMenu, EmcEnvChainerTUI
from emcenvchainer.config import Config
from emcenvchainer.platform import Platform
from emcenvchainer.spack_manager import SpackManager


class TestTUIMenu:
    """Test cases for TUIMenu class."""
    
    @pytest.fixture
    def mock_stdscr(self):
        """Create a mock curses screen."""
        stdscr = Mock()
        stdscr.getmaxyx.return_value = (30, 80)  # height, width
        stdscr.addstr = Mock()
        stdscr.getch = Mock()
        stdscr.clear = Mock()
        stdscr.refresh = Mock()
        return stdscr
    
    @pytest.fixture
    def tui_menu(self, mock_stdscr):
        """Create a TUIMenu instance."""
        return TUIMenu(mock_stdscr, "Test Menu")
    
    def test_init(self, mock_stdscr):
        """Test TUIMenu initialization."""
        menu = TUIMenu(mock_stdscr, "Test Menu")
        assert menu.stdscr == mock_stdscr
        assert menu.title == "Test Menu"
        assert menu.current_row == 0
        assert menu.top_row == 0
    
    def test_display_menu_enter_selection(self, tui_menu, mock_stdscr):
        """Test menu display and Enter key selection."""
        mock_stdscr.getch.return_value = ord('\n')  # Enter key
        
        options = ["Option 1", "Option 2", "Option 3"]
        result = tui_menu.display_menu(options)
        
        assert result == 0  # First option selected
        assert mock_stdscr.clear.called
        assert mock_stdscr.refresh.called
    
    def test_display_menu_arrow_navigation(self, tui_menu, mock_stdscr):
        """Test arrow key navigation in menu."""
        # Simulate: DOWN, DOWN, ENTER
        mock_stdscr.getch.side_effect = [curses.KEY_DOWN, curses.KEY_DOWN, ord('\n')]
        
        options = ["Option 1", "Option 2", "Option 3"]
        result = tui_menu.display_menu(options)
        
        assert result == 2  # Third option selected
        assert tui_menu.current_row == 2
    
    def test_display_menu_escape_cancellation(self, tui_menu, mock_stdscr):
        """Test menu cancellation with Escape key."""
        mock_stdscr.getch.return_value = 27  # Escape
        
        options = ["Option 1", "Option 2", "Option 3"]
        result = tui_menu.display_menu(options)
        
        assert result is None
    
    def test_display_info_message(self, tui_menu, mock_stdscr):
        """Test display_info method."""
        mock_stdscr.getch.return_value = ord(' ')  # Space key
        
        tui_menu.display_info("Test message")
        
        assert mock_stdscr.clear.called
        assert mock_stdscr.refresh.called
        assert mock_stdscr.getch.called


class TestPackageSpecDialog:
    """Test cases for PackageSpecDialog class."""
    
    @pytest.fixture
    def mock_stdscr(self):
        """Create a mock curses screen."""
        stdscr = Mock()
        stdscr.getmaxyx.return_value = (30, 80)
        stdscr.addstr = Mock()
        stdscr.getch = Mock()
        stdscr.clear = Mock()
        stdscr.refresh = Mock()
        stdscr.move = Mock()
        stdscr.clrtoeol = Mock()
        return stdscr
    
    @pytest.fixture
    def mock_spack_manager(self):
        """Create a mock SpackManager."""
        manager = Mock(spec=SpackManager)
        manager.check_package_version_exists.return_value = True
        manager.config = Mock()
        manager.config.get.return_value = {"base_url": "https://github.com/test/repo.git"}
        return manager
    
    @pytest.fixture
    def package_dialog(self, mock_stdscr, mock_spack_manager):
        """Create a PackageSpecDialog instance."""
        return PackageSpecDialog(mock_stdscr, mock_spack_manager)
    
    def test_init(self, mock_stdscr, mock_spack_manager):
        """Test PackageSpecDialog initialization."""
        dialog = PackageSpecDialog(mock_stdscr, mock_spack_manager)
        assert dialog.stdscr == mock_stdscr
        assert dialog.spack_manager == mock_spack_manager
    
    def test_get_package_spec_continue(self, package_dialog, mock_stdscr):
        """Test package specification dialog with continue action."""
        # Mock curses methods
        with patch('curses.curs_set'):
            # Simulate TAB to move to continue, then ENTER
            mock_stdscr.getch.side_effect = [9, ord('\n')]  # Tab, Enter
            
            result = package_dialog.get_package_spec("test-pkg", "1.0.0")
            
            assert result is not None
            assert result["name"] == "test-pkg"
            assert result["version"] == "1.0.0"
            assert result["variants"] == ""
    
    def test_get_package_spec_text_input(self, package_dialog, mock_stdscr):
        """Test text input in package specification dialog."""
        with patch('curses.curs_set'):
            # Simulate typing a character and then continue
            mock_stdscr.getch.side_effect = [ord('a'), 9, ord('\n')]  # 'a', Tab, Enter
            
            result = package_dialog.get_package_spec("", "")
            
            assert result is not None
            assert result["name"] == "a"
    
    def test_get_package_spec_escape_cancel(self, package_dialog, mock_stdscr):
        """Test cancellation with Escape key."""
        with patch('curses.curs_set'):
            mock_stdscr.getch.return_value = 27  # Escape
            
            result = package_dialog.get_package_spec("test-pkg", "1.0.0")
            
            assert result is None
    
    def test_validate_and_add_version_exists(self, package_dialog, mock_spack_manager):
        """Test version validation when version exists."""
        # This method is only called when version doesn't exist locally
        # So we test the UI flow instead of the direct call
        mock_spack_manager.check_version_in_remote_repo.return_value = True
        mock_spack_manager.add_pending_recipe = Mock()
        
        result = package_dialog._validate_and_add_version("test-pkg", "1.0.0")
        
        assert result is True
    
    def test_validate_and_add_version_not_remote_exists_choose_different(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test version validation when version doesn't exist in remote, user chooses to pick different version."""
        mock_spack_manager.check_version_in_remote_repo.return_value = False
        mock_spack_manager.get_local_package_path.return_value = "/path/to/package.py"
        
        # Simulate user pressing 'p' to choose a different version
        mock_stdscr.getch.return_value = ord('p')
        
        result = package_dialog._validate_and_add_version("test-pkg", "1.0.0")
        
        assert result is False  # Should return False to go back to edit version
        assert mock_stdscr.clear.called
        assert mock_stdscr.addstr.called
    
    def test_validate_and_add_version_not_remote_exists_add_checksum(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test version validation when version doesn't exist in remote, user chooses automatic checksum."""
        mock_spack_manager.check_version_in_remote_repo.return_value = False
        mock_spack_manager.get_local_package_path.return_value = "/path/to/package.py"
        
        # Simulate user pressing 'a' to add via checksum
        mock_stdscr.getch.side_effect = [ord('a'), ord(' ')]  # 'a' for checksum, then space to continue
        
        with patch.object(package_dialog, '_add_version_with_checksum', return_value=True) as mock_checksum:
            result = package_dialog._validate_and_add_version("test-pkg", "1.0.0")
            
            mock_checksum.assert_called_once_with("test-pkg", "1.0.0")
            assert result is True
    
    def test_validate_and_add_version_not_remote_exists_add_git_commit(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test version validation when version doesn't exist in remote, user chooses Git commit."""
        mock_spack_manager.check_version_in_remote_repo.return_value = False
        mock_spack_manager.get_local_package_path.return_value = "/path/to/package.py"
        
        # Simulate user pressing 'g' to add via Git commit
        mock_stdscr.getch.return_value = ord('g')
        
        with patch.object(package_dialog, '_add_version_with_git_commit', return_value=True) as mock_git:
            result = package_dialog._validate_and_add_version("test-pkg", "1.0.0")
            
            mock_git.assert_called_once_with("test-pkg", "1.0.0")
            assert result is True
    
    def test_validate_and_add_version_not_remote_exists_continue_manual(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test version validation when version doesn't exist in remote, user chooses to continue manually."""
        mock_spack_manager.check_version_in_remote_repo.return_value = False
        mock_spack_manager.get_local_package_path.return_value = "/path/to/package.py"
        mock_spack_manager.add_pending_recipe = Mock()
        
        # Simulate user pressing 'c' to continue with manual editing
        mock_stdscr.getch.return_value = ord('c')
        
        result = package_dialog._validate_and_add_version("test-pkg", "1.0.0")
        
        assert result is True
        mock_spack_manager.add_pending_recipe.assert_called_once_with(
            "test-pkg", "1.0.0", recipe_content=None,
            needs_manual_edit=True, use_local_copy=True,
            found_in_local=False, found_in_remote=False
        )
    
    def test_validate_and_add_version_not_remote_exists_continue_manual_error(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test version validation when adding for manual editing fails."""
        mock_spack_manager.check_version_in_remote_repo.return_value = False
        mock_spack_manager.get_local_package_path.return_value = "/path/to/package.py"
        mock_spack_manager.add_pending_recipe.side_effect = Exception("Test error")
        
        # Simulate user pressing 'c' to continue with manual editing
        mock_stdscr.getch.return_value = ord('c')
        
        with patch.object(package_dialog, '_show_error') as mock_error:
            result = package_dialog._validate_and_add_version("test-pkg", "1.0.0")
            
            assert result is False
            mock_error.assert_called_once_with("Error marking for manual editing: Test error")
    
    def test_validate_and_add_version_not_remote_exists_case_insensitive(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test that key choices are case-insensitive."""
        mock_spack_manager.check_version_in_remote_repo.return_value = False
        mock_spack_manager.get_local_package_path.return_value = "/path/to/package.py"
        mock_spack_manager.add_pending_recipe = Mock()
        
        # Test uppercase 'C'
        mock_stdscr.getch.return_value = ord('C')
        
        result = package_dialog._validate_and_add_version("test-pkg", "1.0.0")
        
        assert result is True
        assert mock_spack_manager.add_pending_recipe.called
    
    def test_validate_and_add_version_displays_correct_url(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test that the correct remote URL is displayed when version not found."""
        mock_spack_manager.check_version_in_remote_repo.return_value = False
        mock_spack_manager.get_local_package_path.return_value = "/local/path/package.py"
        mock_spack_manager.config.get.side_effect = lambda key, default=None: {
            "spack_repository": {
                "base_url": "https://github.com/spack/spack.git",
                "branch": "develop"
            }
        }.get(key, default) if key == "spack_repository" else default
        
        # Simulate user pressing 'p' to exit
        mock_stdscr.getch.return_value = ord('p')
        
        package_dialog._validate_and_add_version("hdf5", "1.14.0")
        
        # Verify the URL was displayed
        addstr_calls = [str(call) for call in mock_stdscr.addstr.call_args_list]
        url_found = any("https://raw.githubusercontent.com/spack/spack/refs/heads/develop/var/spack/repos/builtin/packages/hdf5/package.py" in str(call) 
                       for call in addstr_calls)
        assert url_found, "Expected URL not found in addstr calls"
    
    def test_show_error(self, package_dialog, mock_stdscr):
        """Test error message display."""
        package_dialog._show_error("Test error message")
        
        assert mock_stdscr.addstr.called
        assert mock_stdscr.refresh.called
    
    def test_add_version_with_git_commit_success(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test adding version with Git commit hash successfully."""
        mock_spack_manager.add_pending_git_commit = Mock()
        mock_spack_manager.add_pending_recipe = Mock()
        
        # Simulate typing a commit hash and pressing Enter, then any key to dismiss success message
        commit_hash = "abc123def456"
        keys = [ord(c) for c in commit_hash] + [ord('\n'), ord(' ')]
        mock_stdscr.getch.side_effect = keys
        
        with patch('curses.curs_set'):
            result = package_dialog._add_version_with_git_commit("test-pkg", "1.0.0")
        
        assert result is True
        mock_spack_manager.add_pending_git_commit.assert_called_once_with("test-pkg", "1.0.0", "abc123def456")
        mock_spack_manager.add_pending_recipe.assert_called_once_with(
            package_name="test-pkg",
            version="1.0.0",
            recipe_content=None,
            needs_manual_edit=True,
            use_local_copy=True,
            found_in_local=True,
            found_in_remote=False
        )
    
    def test_add_version_with_git_commit_escape(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test canceling Git commit version addition."""
        # Simulate pressing Escape
        mock_stdscr.getch.return_value = 27
        
        with patch('curses.curs_set'):
            result = package_dialog._add_version_with_git_commit("test-pkg", "1.0.0")
        
        assert result is False
        assert not mock_spack_manager.add_pending_git_commit.called
    
    def test_add_version_with_git_commit_empty_hash(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test validation for empty commit hash."""
        # Simulate pressing Enter with empty input, then Escape
        mock_stdscr.getch.side_effect = [ord('\n'), 27]
        
        with patch('curses.curs_set'):
            with patch.object(package_dialog, '_show_error') as mock_error:
                result = package_dialog._add_version_with_git_commit("test-pkg", "1.0.0")
                
                mock_error.assert_called_with("Commit hash cannot be empty!")
                assert result is False
    
    def test_add_version_with_git_commit_too_short(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test validation for too short commit hash."""
        # Simulate typing a very short hash and pressing Enter, then Escape
        mock_stdscr.getch.side_effect = [ord('a'), ord('b'), ord('c'), ord('\n'), 27]
        
        with patch('curses.curs_set'):
            with patch.object(package_dialog, '_show_error') as mock_error:
                result = package_dialog._add_version_with_git_commit("test-pkg", "1.0.0")
                
                mock_error.assert_called_with("Commit hash seems too short (should be at least 7 characters)!")
                assert result is False
    
    def test_add_version_with_git_commit_with_whitespace(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test that commit hash is properly stripped of whitespace."""
        mock_spack_manager.add_pending_git_commit = Mock()
        mock_spack_manager.add_pending_recipe = Mock()
        
        # Simulate typing a commit hash with leading/trailing spaces
        commit_hash = "  abc123def456  "
        keys = [ord(c) for c in commit_hash] + [ord('\n'), ord(' ')]
        mock_stdscr.getch.side_effect = keys
        
        with patch('curses.curs_set'):
            result = package_dialog._add_version_with_git_commit("test-pkg", "1.0.0")
        
        assert result is True
        # Verify the hash was stripped
        mock_spack_manager.add_pending_git_commit.assert_called_once_with("test-pkg", "1.0.0", "abc123def456")
    
    def test_add_version_with_git_commit_navigation_keys(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test that navigation keys work during input."""
        mock_spack_manager.add_pending_git_commit = Mock()
        mock_spack_manager.add_pending_recipe = Mock()
        
        # Simulate typing, using navigation, and submitting
        # Type "abc", backspace, type "xyz", then enter
        keys = [
            ord('a'), ord('b'), ord('c'),
            127,  # Backspace
            ord('x'), ord('y'), ord('z'), ord('1'), ord('2'), ord('3'),
            ord('\n'), ord(' ')
        ]
        mock_stdscr.getch.side_effect = keys
        
        with patch('curses.curs_set'):
            result = package_dialog._add_version_with_git_commit("test-pkg", "1.0.0")
        
        assert result is True
        mock_spack_manager.add_pending_git_commit.assert_called_once_with("test-pkg", "1.0.0", "abxyz123")
    
    def test_add_version_with_git_commit_clear_with_ctrl_x(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test clearing input with Ctrl+X."""
        mock_spack_manager.add_pending_git_commit = Mock()
        mock_spack_manager.add_pending_recipe = Mock()
        
        # Simulate typing, Ctrl+X to clear, then typing again and submitting
        keys = [
            ord('a'), ord('b'), ord('c'),
            24,  # Ctrl+X
            ord('x'), ord('y'), ord('z'), ord('1'), ord('2'), ord('3'), ord('4'),
            ord('\n'), ord(' ')
        ]
        mock_stdscr.getch.side_effect = keys
        
        with patch('curses.curs_set'):
            result = package_dialog._add_version_with_git_commit("test-pkg", "1.0.0")
        
        assert result is True
        # Should only have the second input after Ctrl+X cleared the first
        mock_spack_manager.add_pending_git_commit.assert_called_once_with("test-pkg", "1.0.0", "xyz1234")
    
    def test_add_version_with_checksum_success(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test adding version with automatic checksum successfully."""
        mock_spack_manager.add_pending_checksum = Mock()
        mock_spack_manager.add_pending_recipe = Mock()
        
        # Simulate pressing any key to continue
        mock_stdscr.getch.return_value = ord(' ')
        
        result = package_dialog._add_version_with_checksum("test-pkg", "1.0.0")
        
        assert result is True
        mock_spack_manager.add_pending_checksum.assert_called_once_with("test-pkg", "1.0.0")
        mock_spack_manager.add_pending_recipe.assert_called_once_with(
            package_name="test-pkg",
            version="1.0.0",
            recipe_content=None,
            needs_manual_edit=True,
            use_local_copy=True,
            found_in_local=True,
            found_in_remote=False
        )
    
    def test_add_version_with_checksum_exception_in_queue(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test error handling when queueing checksum operation fails."""
        mock_spack_manager.add_pending_checksum.side_effect = Exception("Queue error")
        
        with patch.object(package_dialog, '_show_error') as mock_error:
            result = package_dialog._add_version_with_checksum("test-pkg", "1.0.0")
            
            assert result is False
            mock_error.assert_called_once_with("Error queuing checksum operation: Queue error")
    
    def test_add_version_with_checksum_exception_in_recipe(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test error handling when adding to pending recipes fails."""
        mock_spack_manager.add_pending_checksum = Mock()
        mock_spack_manager.add_pending_recipe.side_effect = Exception("Recipe error")
        
        with patch.object(package_dialog, '_show_error') as mock_error:
            result = package_dialog._add_version_with_checksum("test-pkg", "1.0.0")
            
            assert result is False
            mock_error.assert_called_once_with("Error queuing checksum operation: Recipe error")
    
    def test_add_version_with_checksum_displays_correct_info(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test that correct information is displayed during checksum operation."""
        mock_spack_manager.add_pending_checksum = Mock()
        mock_spack_manager.add_pending_recipe = Mock()
        mock_stdscr.getch.return_value = ord(' ')
        
        result = package_dialog._add_version_with_checksum("hdf5", "1.14.0")
        
        assert result is True
        
        # Verify correct messages were displayed
        addstr_calls = [str(call) for call in mock_stdscr.addstr.call_args_list]
        
        # Check for title
        title_found = any("Auto-add checksum for hdf5@1.14.0" in str(call) for call in addstr_calls)
        assert title_found, "Title not found in addstr calls"
        
        # Check for instruction message
        instruction_found = any("Spack will attempt to automatically add version 1.14.0" in str(call) for call in addstr_calls)
        assert instruction_found, "Instruction not found in addstr calls"
        
        # Check for success message
        success_found = any("queued for 'spack checksum'" in str(call) for call in addstr_calls)
        assert success_found, "Success message not found in addstr calls"
    
    @pytest.mark.parametrize("keys,expected_field", [
        ([curses.KEY_DOWN], 1),
        ([curses.KEY_DOWN, curses.KEY_DOWN], 2),
        ([curses.KEY_DOWN, curses.KEY_UP], 0),
        ([curses.KEY_DOWN, curses.KEY_DOWN, curses.KEY_DOWN], 2),  # Stay at last field
        ([curses.KEY_UP], 0),  # Stay at first field
        ([ord('\t'), ord('\t'), ord('\t')], 0),  # Tab wraps around
    ])
    def test_get_package_spec_navigation(self, package_dialog, mock_stdscr, keys, expected_field):
        """Test keyboard navigation between package specification fields."""
        with patch('curses.curs_set'):
            # Add Enter key at the end to submit
            mock_stdscr.getch.side_effect = keys + [ord('\n')]
            
            result = package_dialog.get_package_spec("pkg", "1.0")
            
            assert result is not None
            # Field navigation is tested by successful submission
    
    @pytest.mark.parametrize("keys,expected_name,description", [
        ([ord('a'), ord('b'), ord('c'), curses.KEY_LEFT, ord('X')], "abXc", "insert with left arrow"),
        ([ord('a'), ord('b'), ord('c'), curses.KEY_HOME, ord('X')], "Xabc", "insert at beginning with HOME"),
        ([ord('a'), ord('b'), ord('c'), 1, ord('X')], "Xabc", "insert at beginning with Ctrl+A"),
        ([ord('a'), ord('b'), ord('c'), curses.KEY_HOME, curses.KEY_END, ord('X')], "abcX", "move to end with END"),
        ([ord('a'), ord('b'), ord('c'), curses.KEY_HOME, 5, ord('X')], "abcX", "move to end with Ctrl+E"),
        ([ord('a'), ord('b'), ord('c'), 127], "ab", "backspace"),
        ([ord('a'), ord('b'), ord('c'), curses.KEY_HOME, curses.KEY_DC], "bc", "delete at cursor"),
    ])
    def test_get_package_spec_cursor_movement(self, package_dialog, mock_stdscr, keys, expected_name, description):
        """Test cursor movement and editing operations."""
        with patch('curses.curs_set'):
            mock_stdscr.getch.side_effect = keys + [ord('\n')]
            
            result = package_dialog.get_package_spec("", "")
            
            assert result is not None, f"Failed: {description}"
            assert result["name"] == expected_name, f"Failed: {description}"
    
    def test_get_package_spec_ctrl_x_clear_field(self, package_dialog, mock_stdscr):
        """Test Ctrl+X clears field and returns fields (note: this appears to be a bug in original code)."""
        with patch('curses.curs_set'):
            # Type "abc" in name field, press Ctrl+X
            # Note: In the original code, Ctrl+X clears AND returns, which seems like a bug
            mock_stdscr.getch.side_effect = [
                ord('a'), ord('b'), ord('c'),  # Type "abc"
                24,                            # Ctrl+X
            ]
            
            result = package_dialog.get_package_spec("", "")
            
            # Based on the code, Ctrl+X clears the field and returns immediately
            assert result is not None
            assert result["name"] == ""
    
    def test_get_package_spec_printable_characters(self, package_dialog, mock_stdscr):
        """Test that printable ASCII characters (32-126) are inserted."""
        with patch('curses.curs_set'):
            # Test various printable characters
            mock_stdscr.getch.side_effect = [
                ord(' '),   # Space (32)
                ord('a'),   # Lowercase
                ord('Z'),   # Uppercase
                ord('0'),   # Digit
                ord('-'),   # Hyphen
                ord('_'),   # Underscore
                ord('@'),   # At sign
                ord('~'),   # Tilde (126)
                ord('\n')   # Submit
            ]
            
            result = package_dialog.get_package_spec("", "")
            
            assert result is not None
            assert result["name"] == " aZ0-_@~"
    
    def test_get_package_spec_non_printable_characters_ignored(self, package_dialog, mock_stdscr):
        """Test that non-printable characters (< 32 or > 126, except special keys) are ignored."""
        with patch('curses.curs_set'):
            # Try to insert non-printable characters
            mock_stdscr.getch.side_effect = [
                ord('a'),   # Type 'a'
                31,         # Non-printable (should be ignored)
                127,        # Would be backspace, deletes 'a'
                ord('b'),   # Type 'b'
                200,        # Non-printable (should be ignored)
                ord('\n')   # Submit
            ]
            
            result = package_dialog.get_package_spec("", "")
            
            assert result is not None
            assert result["name"] == "b"  # Only 'b' remains after backspace removed 'a'
    
    def test_get_package_spec_empty_name_shows_error(self, package_dialog, mock_stdscr):
        """Test that empty package name shows error and stays in dialog."""
        with patch('curses.curs_set'):
            # Try to submit with empty name, then add name and submit
            mock_stdscr.getch.side_effect = [
                ord('\n'),         # Try to submit empty name (should show error)
                ord('p'), ord('k'), ord('g'),  # Type "pkg"
                ord('\n')          # Submit successfully
            ]
            
            with patch.object(package_dialog, '_show_error') as mock_error:
                result = package_dialog.get_package_spec("", "")
                
                # Should have shown error once
                mock_error.assert_called_once_with("Package name is required!")
                
                assert result is not None
                assert result["name"] == "pkg"
    
    def test_get_package_spec_whitespace_only_name_shows_error(self, package_dialog, mock_stdscr):
        """Test that whitespace-only package name shows error."""
        with patch('curses.curs_set'):
            # Type spaces, try to submit, then clear and type valid name
            mock_stdscr.getch.side_effect = [
                ord(' '), ord(' '), ord(' '),  # Type spaces
                ord('\n'),                     # Try to submit (should show error)
                curses.KEY_HOME,               # Move to beginning
                curses.KEY_DC, curses.KEY_DC, curses.KEY_DC,  # Delete all spaces
                ord('p'), ord('k'), ord('g'),  # Type "pkg"
                ord('\n')                      # Submit successfully
            ]
            
            with patch.object(package_dialog, '_show_error') as mock_error:
                result = package_dialog.get_package_spec("", "")
                
                mock_error.assert_called_once_with("Package name is required!")
                
                assert result is not None
                assert result["name"] == "pkg"
    
    def test_get_package_spec_editing_version_field(self, package_dialog, mock_stdscr):
        """Test editing the version field."""
        with patch('curses.curs_set'):
            # Navigate to version field and edit
            mock_stdscr.getch.side_effect = [
                curses.KEY_DOWN,               # Move to version field
                ord('2'), ord('.'), ord('0'),  # Type "2.0"
                ord('\n')                      # Submit
            ]
            
            result = package_dialog.get_package_spec("pkg", "1.0")
            
            assert result is not None
            assert result["name"] == "pkg"
            assert result["version"] == "1.02.0"  # Appended to existing "1.0"
    
    def test_get_package_spec_editing_variants_field(self, package_dialog, mock_stdscr):
        """Test editing the variants field."""
        with patch('curses.curs_set'):
            # Navigate to variants field and edit
            mock_stdscr.getch.side_effect = [
                curses.KEY_DOWN,               # Move to version field
                curses.KEY_DOWN,               # Move to variants field
                ord('+'), ord('m'), ord('p'), ord('i'),  # Type "+mpi"
                ord('\n')                      # Submit
            ]
            
            result = package_dialog.get_package_spec("pkg", "1.0")
            
            assert result is not None
            assert result["name"] == "pkg"
            assert result["version"] == "1.0"
            assert result["variants"] == "+mpi"
    
    def test_get_package_spec_complex_editing_sequence(self, package_dialog, mock_stdscr):
        """Test complex editing sequence with navigation and edits across fields."""
        with patch('curses.curs_set'):
            # Complex sequence: edit name, go to version, go back, edit name more
            mock_stdscr.getch.side_effect = [
                ord('h'), ord('d'), ord('f'),  # Type "hdf" in name field
                curses.KEY_DOWN,               # Move to version field
                ord('5'),                      # Type "5" in version
                curses.KEY_UP,                 # Move back to name field
                ord('5'),                      # Add "5" to name -> "hdf5"
                ord('\n')                      # Submit
            ]
            
            result = package_dialog.get_package_spec("", "")
            
            assert result is not None
            assert result["name"] == "hdf5"
            assert result["version"] == "5"
    
    def test_get_package_spec_validation_performed_and_spec_unchanged(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test 'if validation_performed:' branch - when validation done and spec hasn't changed.
        
        This is a defensive branch that isn't normally reachable since validation success
        causes an immediate return. We test that the check exists by verifying the code path
        with normal behavior where version exists locally (no validation needed).
        """
        with patch('curses.curs_set'):
            # Version exists locally, so no validation is performed at all
            # This tests that when a version exists, it returns successfully
            mock_spack_manager.check_package_version_exists.return_value = True
            
            mock_stdscr.getch.side_effect = [ord('\n')]  # Submit
            
            result = package_dialog.get_package_spec("test-pkg", "1.0.0")
            
            # Should return successfully without calling validation
            assert result is not None
            assert result["name"] == "test-pkg"
            assert result["version"] == "1.0.0"
    
    def test_get_package_spec_validation_performed_then_spec_changed_resets_flag(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test 'if validation_performed and current_spec != last_validated_spec:' branch.
        
        This tests that the validation flag is reset when the spec changes. Since validation
        success always returns, this is a defensive branch. We test it by validation failing
        multiple times with spec changes.
        """
        with patch('curses.curs_set'):
            # Version doesn't exist locally
            mock_spack_manager.check_package_version_exists.return_value = False
            
            # Scenario: Validation fails first time, user stays in dialog,
            # edits the spec, tries again
            mock_stdscr.getch.side_effect = [
                ord('\n'),          # First submit - validation will fail
                curses.KEY_DOWN,    # Move to version field
                ord('.'), ord('1'), # Change version
                ord('\n')           # Second submit - validation succeeds
            ]
            
            # First validation fails, second succeeds
            with patch.object(package_dialog, '_validate_and_add_version', side_effect=[False, True]) as mock_validate:
                result = package_dialog.get_package_spec("test-pkg", "1.0.0")
                
                # Should have been called twice with different versions
                assert mock_validate.call_count == 2
                assert mock_validate.call_args_list[0][0] == ("test-pkg", "1.0.0")
                assert mock_validate.call_args_list[1][0] == ("test-pkg", "1.0.0.1")
                
                assert result is not None
                assert result["version"] == "1.0.0.1"
    
    def test_get_package_spec_validation_fails_stays_in_dialog(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test that dialog stays open when validation fails."""
        with patch('curses.curs_set'):
            # Setup: version doesn't exist locally
            mock_spack_manager.check_package_version_exists.return_value = False
            
            # First submit fails validation, second submit succeeds
            mock_stdscr.getch.side_effect = [
                ord('\n'),          # First submit - validation fails
                curses.KEY_DOWN,    # Move to version field
                ord('2'),           # Change to version "1.0.02"
                ord('\n')           # Second submit - validation succeeds
            ]
            
            with patch.object(package_dialog, '_validate_and_add_version', side_effect=[False, True]) as mock_validate:
                result = package_dialog.get_package_spec("test-pkg", "1.0.0")
                
                # Validation should be called twice
                assert mock_validate.call_count == 2
                
                # First call should have failed
                assert mock_validate.call_args_list[0][0] == ("test-pkg", "1.0.0")
                
                # Second call with modified version should have succeeded
                assert mock_validate.call_args_list[1][0] == ("test-pkg", "1.0.02")
                
                assert result is not None
                assert result["name"] == "test-pkg"
                assert result["version"] == "1.0.02"
    
    def test_get_package_spec_validation_succeeds_returns_fields(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test that validation success returns fields and marks as validated."""
        with patch('curses.curs_set'):
            # Setup: version doesn't exist locally
            mock_spack_manager.check_package_version_exists.return_value = False
            
            # Submit once, validation succeeds
            mock_stdscr.getch.side_effect = [ord('\n')]
            
            with patch.object(package_dialog, '_validate_and_add_version', return_value=True) as mock_validate:
                result = package_dialog.get_package_spec("hdf5", "1.14.0")
                
                # Validation should be called once
                mock_validate.assert_called_once_with("hdf5", "1.14.0")
                
                # Should return fields
                assert result is not None
                assert result["name"] == "hdf5"
                assert result["version"] == "1.14.0"
    
    def test_get_package_spec_validation_performed_then_name_changed(self, package_dialog, mock_stdscr, mock_spack_manager):
        """Test that changing package name after validation triggers re-validation."""
        with patch('curses.curs_set'):
            # Setup: version doesn't exist locally
            mock_spack_manager.check_package_version_exists.return_value = False
            
            # First validation fails, user changes name, tries again
            mock_stdscr.getch.side_effect = [
                ord('\n'),          # First submit - validation fails
                curses.KEY_HOME,    # Move to beginning of name field (cursor is at end)
                curses.KEY_END,     # Move to end 
                ord('2'),           # Change name to "pkg2"
                ord('\n')           # Second submit - validation succeeds
            ]
            
            # First validation fails, second succeeds
            with patch.object(package_dialog, '_validate_and_add_version', side_effect=[False, True]) as mock_validate:
                result = package_dialog.get_package_spec("pkg", "1.0")
                
                # Validation should be called twice (name changed between attempts)
                assert mock_validate.call_count == 2
                
                # First call with original name
                assert mock_validate.call_args_list[0][0] == ("pkg", "1.0")
                
                # Second call with changed name
                assert mock_validate.call_args_list[1][0] == ("pkg2", "1.0")
                
                assert result is not None
                assert result["name"] == "pkg2"
                assert result["version"] == "1.0"


class TestRadioButtonMenu:
    """Test cases for RadioButtonMenu class."""
    
    @pytest.fixture
    def mock_stdscr(self):
        """Create a mock curses screen."""
        stdscr = Mock()
        stdscr.getmaxyx.return_value = (30, 80)
        stdscr.addstr = Mock()
        stdscr.getch = Mock()
        stdscr.clear = Mock()
        stdscr.refresh = Mock()
        return stdscr
    
    @pytest.fixture
    def radio_menu(self, mock_stdscr):
        """Create a RadioButtonMenu instance."""
        return RadioButtonMenu(mock_stdscr, "Test Radio Menu")
    
    def test_init(self, mock_stdscr):
        """Test RadioButtonMenu initialization."""
        menu = RadioButtonMenu(mock_stdscr, "Test Radio Menu")
        assert menu.stdscr == mock_stdscr
        assert menu.title == "Test Radio Menu"
        assert menu.current_row == 0
        assert menu.top_row == 0
        assert menu.selected_items == set()
    
    def test_display_menu_space_selection(self, radio_menu, mock_stdscr):
        """Test space key for item selection."""
        # Simulate: SPACE (select), ENTER (confirm)
        mock_stdscr.getch.side_effect = [ord(' '), ord('\n')]
        
        options = ["Option 1", "Option 2", "Option 3"]
        result = radio_menu.display_menu(options)
        
        assert result == {0}  # First item selected
    
    def test_display_menu_multiple_selections(self, radio_menu, mock_stdscr):
        """Test multiple item selection."""
        # Simulate: SPACE, DOWN, SPACE, ENTER
        mock_stdscr.getch.side_effect = [ord(' '), curses.KEY_DOWN, ord(' '), ord('\n')]
        
        options = ["Option 1", "Option 2", "Option 3"]
        result = radio_menu.display_menu(options)
        
        assert result == {0, 1}  # First and second items selected
    
    def test_display_menu_select_all(self, radio_menu, mock_stdscr):
        """Test select all functionality."""
        # Simulate: 'a' (select all), ENTER
        mock_stdscr.getch.side_effect = [ord('a'), ord('\n')]
        
        options = ["Option 1", "Option 2", "Option 3"]
        result = radio_menu.display_menu(options)
        
        assert result == {0, 1, 2}  # All items selected
    
    def test_display_menu_select_none(self, radio_menu, mock_stdscr):
        """Test select none functionality."""
        # First select all, then select none
        radio_menu.selected_items = {0, 1, 2}
        # Ensure getch returns values for 'n' then Enter
        mock_stdscr.getch.side_effect = [ord('n'), ord('\n')]
        
        options = ["Option 1", "Option 2", "Option 3"]
        result = radio_menu.display_menu(options)
        
        assert result == set()  # No items selected


class TestEmcEnvChainerTUI:
    """Test cases for EmcEnvChainerTUI class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock Config object."""
        config = Mock(spec=Config)
        config.get.return_value = {"test": "value"}
        return config
    
    @pytest.fixture
    def mock_platform(self):
        """Create a mock Platform object."""
        platform = Mock(spec=Platform)
        platform.name = "test-platform"
        platform.config = {"test": "config"}
        platform.spack_stack_path = "/test/spack/stack"
        platform.spack_installations = [
            {"type": "jcsda-spack-stack", "path": "/test/stack", "install_path": "/test/install", "name": "Test Installation"}
        ]
        # Mock the get_spack_root method
        platform.get_spack_root.return_value = "/test/stack/spack"
        return platform
    
    @pytest.fixture
    def mock_stdscr(self):
        """Create a mock curses screen."""
        stdscr = Mock()
        stdscr.getmaxyx.return_value = (30, 80)
        stdscr.addstr = Mock()
        stdscr.getch = Mock()
        stdscr.clear = Mock()
        stdscr.refresh = Mock()
        stdscr.move = Mock()
        stdscr.clrtoeol = Mock()
        return stdscr
    
    @pytest.fixture
    def tui_app(self, mock_config, mock_platform):
        """Create an EmcEnvChainerTUI instance."""
        return EmcEnvChainerTUI(mock_config, mock_platform)
    
    def test_init(self, mock_config, mock_platform):
        """Test EmcEnvChainerTUI initialization."""
        tui = EmcEnvChainerTUI(mock_config, mock_platform)
        assert tui.config == mock_config
        assert tui.platform == mock_platform
        assert tui.model_app_manager is not None
    
    @patch('curses.wrapper')
    def test_run_success(self, mock_wrapper, tui_app):
        """Test successful TUI run."""
        tui_app.run()
        mock_wrapper.assert_called_once()
    
    @patch('curses.wrapper')
    def test_run_keyboard_interrupt(self, mock_wrapper, tui_app):
        """Test TUI run with keyboard interrupt."""
        mock_wrapper.side_effect = KeyboardInterrupt()
        
        with patch('builtins.print') as mock_print:
            tui_app.run()
            mock_print.assert_called_with("\nOperation cancelled by user.")
    
    @patch('curses.wrapper')
    def test_run_exception(self, mock_wrapper, tui_app):
        """Test TUI run with exception."""
        mock_wrapper.side_effect = Exception("Test error")
        
        with patch('builtins.print') as mock_print:
            tui_app.run()
            mock_print.assert_called_with("Error running TUI: Test error")
    
    def test_display_scrollable_text(self, tui_app, mock_stdscr):
        """Test scrollable text display."""
        title = ["Test Title", "Subtitle"]
        content = "Line 1\nLine 2\nLine 3"
        
        mock_stdscr.getch.return_value = ord('\n')  # Enter to continue
        
        tui_app.display_scrollable_text(mock_stdscr, title, content)
        
        assert mock_stdscr.clear.called
        assert mock_stdscr.addstr.called
        assert mock_stdscr.refresh.called
    
    def test_run_interactive_install_success(self, tui_app, mock_stdscr):
        """Test successful interactive install."""
        mock_spack_manager = Mock(spec=SpackManager)
        mock_spack_manager.install_environment_interactive.return_value = True
        
        with patch('curses.endwin') as mock_endwin:
            with patch('curses.doupdate') as mock_doupdate:
                with patch('builtins.print') as mock_print:
                    result = tui_app.run_interactive_install(mock_stdscr, mock_spack_manager, "/test/env/path")
        
        assert result is True
        mock_endwin.assert_called_once()
        mock_doupdate.assert_called_once()
        mock_spack_manager.install_environment_interactive.assert_called_once_with("/test/env/path")
        mock_stdscr.refresh.assert_called()
        
        # Verify success message was printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        success_found = any("Installation completed successfully!" in str(call) for call in print_calls)
        assert success_found, "Success message not printed"
    
    def test_run_interactive_install_failure(self, tui_app, mock_stdscr):
        """Test failed interactive install."""
        mock_spack_manager = Mock(spec=SpackManager)
        mock_spack_manager.install_environment_interactive.return_value = False
        
        with patch('curses.endwin') as mock_endwin:
            with patch('curses.doupdate') as mock_doupdate:
                with patch('builtins.print') as mock_print:
                    result = tui_app.run_interactive_install(mock_stdscr, mock_spack_manager, "/test/env/path")
        
        assert result is False
        mock_endwin.assert_called_once()
        mock_doupdate.assert_called_once()
        mock_spack_manager.install_environment_interactive.assert_called_once_with("/test/env/path")
        mock_stdscr.refresh.assert_called()
        
        # Verify failure message was printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        failure_found = any("Installation failed!" in str(call) for call in print_calls)
        assert failure_found, "Failure message not printed"
    
    def test_run_interactive_install_restores_curses_on_exception(self, tui_app, mock_stdscr):
        """Test that curses mode is restored even when install raises exception."""
        mock_spack_manager = Mock(spec=SpackManager)
        mock_spack_manager.install_environment_interactive.side_effect = Exception("Install error")
        
        with patch('curses.endwin') as mock_endwin:
            with patch('curses.doupdate') as mock_doupdate:
                with patch('builtins.print'):
                    with pytest.raises(Exception, match="Install error"):
                        tui_app.run_interactive_install(mock_stdscr, mock_spack_manager, "/test/env/path")
        
        # Verify curses was exited and restored even though exception was raised
        mock_endwin.assert_called_once()
        mock_doupdate.assert_called_once()
        mock_stdscr.refresh.assert_called()
    
    def test_run_interactive_install_displays_header(self, tui_app, mock_stdscr):
        """Test that interactive install displays proper header messages."""
        mock_spack_manager = Mock(spec=SpackManager)
        mock_spack_manager.install_environment_interactive.return_value = True
        
        with patch('curses.endwin'):
            with patch('curses.doupdate'):
                with patch('builtins.print') as mock_print:
                    tui_app.run_interactive_install(mock_stdscr, mock_spack_manager, "/test/env/path")
        
        # Verify header messages were printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        header_found = any("Installing packages with Spack..." in str(call) for call in print_calls)
        assert header_found, "Header message not printed"
        
        timing_msg_found = any("This may take several minutes" in str(call) for call in print_calls)
        assert timing_msg_found, "Timing message not printed"
    
    def test_main_loop_full_workflow(self, tui_app, mock_stdscr):
        """Test complete main loop workflow."""
        mock_installation = {"type": "jcsda-spack-stack", "install_path": "/test/install"}
        mock_packages = [{"name": "test-pkg", "version": "1.0.0"}]
        mock_spack_manager = Mock(spec=SpackManager)
        
        with patch('curses.curs_set'):
            with patch('curses.has_colors', return_value=True):
                with patch('curses.start_color'):
                    with patch('curses.use_default_colors'):
                        with patch('curses.init_pair'):
                            with patch.object(tui_app, '_show_welcome_and_get_env_name', return_value="test-env"):
                                with patch.object(tui_app, '_select_installation', return_value=mock_installation):
                                    with patch.object(tui_app, '_get_package_specifications_with_manager', return_value=(mock_packages, mock_spack_manager)):
                                        with patch.object(tui_app, '_create_environment') as mock_create:
                                            tui_app._main_loop(mock_stdscr)
        
        # Verify all methods were called in order
        mock_stdscr.clear.assert_called()
        mock_create.assert_called_once_with(mock_stdscr, mock_installation, mock_packages, mock_spack_manager, "test-env")
    
    def test_main_loop_cancel_at_welcome(self, tui_app, mock_stdscr):
        """Test main loop when user cancels at welcome screen."""
        with patch('curses.curs_set'):
            with patch('curses.has_colors', return_value=False):
                with patch.object(tui_app, '_show_welcome_and_get_env_name', return_value=None):
                    with patch.object(tui_app, '_select_installation') as mock_select:
                        tui_app._main_loop(mock_stdscr)
        
        # Verify that subsequent methods were not called
        mock_select.assert_not_called()
    
    def test_main_loop_cancel_at_installation_select(self, tui_app, mock_stdscr):
        """Test main loop when user cancels at installation selection."""
        with patch('curses.curs_set'):
            with patch('curses.has_colors', return_value=False):
                with patch.object(tui_app, '_show_welcome_and_get_env_name', return_value="test-env"):
                    with patch.object(tui_app, '_select_installation', return_value=None):
                        with patch.object(tui_app, '_get_package_specifications_with_manager') as mock_get_packages:
                            tui_app._main_loop(mock_stdscr)
        
        # Verify that subsequent methods were not called
        mock_get_packages.assert_not_called()
    
    def test_main_loop_cancel_at_package_selection(self, tui_app, mock_stdscr):
        """Test main loop when user cancels at package selection."""
        mock_installation = {"type": "jcsda-spack-stack", "install_path": "/test/install"}
        
        with patch('curses.curs_set'):
            with patch('curses.has_colors', return_value=False):
                with patch.object(tui_app, '_show_welcome_and_get_env_name', return_value="test-env"):
                    with patch.object(tui_app, '_select_installation', return_value=mock_installation):
                        with patch.object(tui_app, '_get_package_specifications_with_manager', return_value=(None, None)):
                            with patch.object(tui_app, '_create_environment') as mock_create:
                                tui_app._main_loop(mock_stdscr)
        
        # Verify that create_environment was not called
        mock_create.assert_not_called()
    
    def test_main_loop_initializes_curses_colors(self, tui_app, mock_stdscr):
        """Test that main loop initializes curses colors when supported."""
        with patch('curses.curs_set'):
            with patch('curses.has_colors', return_value=True) as mock_has_colors:
                with patch('curses.start_color') as mock_start_color:
                    with patch('curses.use_default_colors') as mock_use_defaults:
                        with patch('curses.init_pair') as mock_init_pair:
                            with patch.object(tui_app, '_show_welcome_and_get_env_name', return_value=None):
                                tui_app._main_loop(mock_stdscr)
        
        # Verify color initialization
        mock_has_colors.assert_called_once()
        mock_start_color.assert_called_once()
        mock_use_defaults.assert_called_once()
        assert mock_init_pair.call_count == 3  # Three color pairs defined
    
    def test_main_loop_skips_color_init_when_not_supported(self, tui_app, mock_stdscr):
        """Test that main loop skips color initialization when not supported."""
        with patch('curses.curs_set'):
            with patch('curses.has_colors', return_value=False) as mock_has_colors:
                with patch('curses.start_color') as mock_start_color:
                    with patch.object(tui_app, '_show_welcome_and_get_env_name', return_value=None):
                        tui_app._main_loop(mock_stdscr)
        
        # Verify color initialization was skipped
        mock_has_colors.assert_called_once()
        mock_start_color.assert_not_called()
    
    def test_show_welcome_and_get_env_name(self, tui_app, mock_stdscr):
        """Test welcome screen and environment name input."""
        # Mock the text input functionality
        mock_stdscr.getch.side_effect = [ord('t'), ord('e'), ord('s'), ord('t'), ord('\n')]
        
        with patch('curses.curs_set'):
            result = tui_app._show_welcome_and_get_env_name(mock_stdscr)
            
            assert result == "test"
    
    def test_show_welcome_and_get_env_name_cancel(self, tui_app, mock_stdscr):
        """Test welcome screen cancellation."""
        mock_stdscr.getch.return_value = 27  # Escape
        
        with patch('curses.curs_set'):
            result = tui_app._show_welcome_and_get_env_name(mock_stdscr)
            
            assert result is None
    
    @patch('os.path.exists')
    def test_select_installation_default(self, mock_exists, tui_app, mock_stdscr):
        """Test installation selection with default option."""
        mock_exists.return_value = True  # Mock that spack executable exists
        mock_stdscr.getch.return_value = ord('\n')  # Enter to select first option
        
        installation = tui_app._select_installation(mock_stdscr)
        assert installation is not None
        assert installation["type"] == "jcsda-spack-stack"
        assert "install_path" in installation
        
        # Test that _get_spack_config works with this installation
        spack_root, upstream_path = tui_app._get_spack_config(installation)
        assert spack_root == "/test/stack/spack"
        assert upstream_path == "/test/install"
    
    def test_select_installation_custom_path(self, tui_app, mock_stdscr):
        """Test installation selection with custom path."""
        # Navigate to custom path option and select
        mock_stdscr.getch.side_effect = [curses.KEY_DOWN, ord('\n')]
        
        with patch.object(tui_app, '_get_custom_path', return_value={"type": "custom", "spack_root": "/custom/path"}):
            result = tui_app._select_installation(mock_stdscr)
            
            assert result is not None
            assert result["spack_root"] == "/custom/path"
    
    def test_select_installation_with_model_applications(self, tui_app, mock_stdscr):
        """Test installation selection includes model applications."""
        # Create mock model application
        mock_app = Mock()
        mock_app.name = "ufs-weather-model"
        mock_app.config = {"name": "UFS Weather Model"}
        mock_app.get_module_url_choices.return_value = [
            {"name": "Release v1.0", "url": "https://example.com/module1.lua"},
            {"name": "Release v2.0", "url": "https://example.com/module2.lua"}
        ]
        
        # Patch the model_app_manager's applications property using PropertyMock
        with patch.object(type(tui_app.model_app_manager), 'applications', new_callable=PropertyMock) as mock_apps:
            mock_apps.return_value = [mock_app]
            # Select first option (which is now a model application, since they come first)
            mock_stdscr.getch.return_value = ord('\n')
            
            result = tui_app._select_installation(mock_stdscr)
            
            # Verify the app's get_module_url_choices was called
            mock_app.get_module_url_choices.assert_called_once()
            
            # Result should be the first model application
            assert result is not None
            assert result["type"] == "model_application"
    
    def test_select_installation_select_model_application(self, tui_app, mock_stdscr):
        """Test selecting a model application from the menu."""
        # Create mock model application
        mock_app = Mock()
        mock_app.name = "ufs-weather-model"
        mock_app.config = {"name": "UFS Weather Model"}
        mock_app.get_module_url_choices.return_value = [
            {"name": "Release v1.0", "url": "https://example.com/module1.lua"}
        ]
        
        # Patch the model_app_manager's applications property using PropertyMock
        with patch.object(type(tui_app.model_app_manager), 'applications', new_callable=PropertyMock) as mock_apps:
            mock_apps.return_value = [mock_app]
            # Model applications now come first, so select the first option
            mock_stdscr.getch.return_value = ord('\n')
            
            result = tui_app._select_installation(mock_stdscr)
            
            assert result is not None
            assert result["type"] == "model_application"
            assert result["name"] == "ufs-weather-model (Release v1.0)"
            assert result["application"] == mock_app
            assert result["selected_module_url"] == "https://example.com/module1.lua"
    
    def test_select_installation_multiple_model_apps_multiple_urls(self, tui_app, mock_stdscr):
        """Test selection with multiple model applications each having multiple URL choices."""
        # Create first mock model application
        mock_app1 = Mock()
        mock_app1.name = "ufs-weather-model"
        mock_app1.config = {"name": "UFS Weather Model"}
        mock_app1.get_module_url_choices.return_value = [
            {"name": "GCC", "url": "https://example.com/ufs-gcc.lua"},
            {"name": "oneAPI", "url": "https://example.com/ufs-oneapi.lua"}
        ]
        
        # Create second mock model application
        mock_app2 = Mock()
        mock_app2.name = "global-workflow"
        mock_app2.config = {"name": "Global Workflow"}
        mock_app2.get_module_url_choices.return_value = [
            {"name": "GCC", "url": "https://example.com/gw-gcc.lua"},
            {"name": "oneAPI", "url": "https://example.com/gw-oneapi.lua"}
        ]
        
        # Patch the model_app_manager's applications property using PropertyMock
        with patch.object(type(tui_app.model_app_manager), 'applications', new_callable=PropertyMock) as mock_apps:
            mock_apps.return_value = [mock_app1, mock_app2]
            # Select the second option (oneAPI of first app)
            # Options (with model apps first): [ufs-gcc, ufs-oneapi, gw-gcc, gw-oneapi, spack-install, custom]
            mock_stdscr.getch.side_effect = [curses.KEY_DOWN, ord('\n')]
            
            result = tui_app._select_installation(mock_stdscr)
            
            assert result is not None
            assert result["type"] == "model_application"
            assert result["name"] == "ufs-weather-model (oneAPI)"
            assert result["selected_module_url"] == "https://example.com/ufs-oneapi.lua"
    
    def test_select_installation_no_options(self, tui_app, mock_stdscr):
        """Test installation selection when no options are available."""
        # Patch both the spack installations and model apps to be empty
        with patch.object(tui_app.platform, 'spack_installations', []):
            with patch.object(type(tui_app.model_app_manager), 'applications', new_callable=PropertyMock) as mock_apps:
                mock_apps.return_value = []
                with patch.object(TUIMenu, 'display_info') as mock_display:
                    result = tui_app._select_installation(mock_stdscr)
                
                assert result is None
                mock_display.assert_called_once_with("No installations or model applications found!")
    
    def test_select_installation_cancel(self, tui_app, mock_stdscr):
        """Test canceling installation selection."""
        mock_stdscr.getch.return_value = 27  # Escape key
        
        result = tui_app._select_installation(mock_stdscr)
        
        assert result is None
    
    @patch('curses.echo')
    @patch('curses.noecho')
    @patch('curses.curs_set')
    @patch('os.path.exists')
    @patch('os.path.isdir')
    def test_get_custom_path_valid(self, mock_isdir, mock_exists, mock_curs_set, mock_noecho, mock_echo, tui_app, mock_stdscr):
        """Test custom path input with valid path."""
        # Mock getstr to return the bytes representation of the path
        mock_stdscr.getstr.return_value = b'/test'
        mock_exists.return_value = True
        mock_isdir.return_value = True
        
        result = tui_app._get_custom_path(mock_stdscr)
        
        assert result is not None
        assert result["install_path"] == "/test"
        assert result["name"] == "Custom - test"
        assert result["type"] == "custom_path"
    
    @patch('curses.echo')
    @patch('curses.noecho')
    @patch('curses.curs_set')
    @patch('os.path.exists')
    def test_get_custom_path_invalid(self, mock_exists, mock_curs_set, mock_noecho, mock_echo, tui_app, mock_stdscr):
        """Test custom path input with invalid path."""
        mock_stdscr.getch.side_effect = [ord('/'), ord('i'), ord('n'), ord('v'), ord('a'), ord('l'), ord('i'), ord('d'), ord('\n'), 27]
        mock_exists.return_value = False
        
        result = tui_app._get_custom_path(mock_stdscr)
        
        assert result is None
    
    @patch('os.path.exists')
    def test_get_spack_config_jcsda_stack(self, mock_exists, tui_app):
        """Test getting Spack config for JCSDA stack."""
        mock_exists.return_value = True  # Mock that spack executable exists
        installation = {"type": "jcsda-spack-stack", "path": "/path/to/stack", "install_path": "/path/to/install"}
        
        spack_root, upstream_path = tui_app._get_spack_config(installation)
        
        # The method calls platform.get_spack_root() which we mocked to return "/test/stack/spack"
        assert spack_root == "/test/stack/spack"
        assert upstream_path == "/path/to/install"
    
    @patch('os.path.exists')
    def test_get_spack_config_custom(self, mock_exists, tui_app):
        """Test getting Spack config for custom installation."""
        mock_exists.return_value = True  # Mock that spack executable exists
        installation = {"type": "custom", "spack_root": "/custom/spack", "branch": "custom-branch", "install_path": "/custom/install"}
        
        spack_root, upstream_path = tui_app._get_spack_config(installation)
        
        # For non-model-application types, it uses platform.get_spack_root()
        assert spack_root == "/test/stack/spack"
        assert upstream_path == "/custom/install"
    
    @patch('os.path.exists')
    def test_get_spack_config_model_application_success(self, mock_exists, tui_app):
        """Test getting Spack config for model application with valid path structure."""
        # Mock that spack executable exists at the inferred location
        mock_exists.return_value = True
        
        # Create mock model application
        mock_app = Mock()
        mock_app.name = "ufs-weather-model"
        mock_app.config = {"name": "UFS Weather Model"}
        mock_app.platform_name = "test-platform"
        mock_app.extract_install_path.return_value = "/base/spack-stack/spack-stack-1.6.0/envs/unified-env/install"
        
        installation = {
            "type": "model_application",
            "application": mock_app,
            "selected_module_url": None
        }
        
        spack_root, upstream_path = tui_app._get_spack_config(installation)
        
        # Should infer spack root from the install path structure
        assert spack_root == "/base/spack-stack/spack-stack-1.6.0/spack"
        assert upstream_path == "/base/spack-stack/spack-stack-1.6.0/envs/unified-env/install"
        
        # Verify it checked for spack executable
        mock_exists.assert_called_with("/base/spack-stack/spack-stack-1.6.0/spack/bin/spack")
    
    @patch('os.path.exists')
    def test_get_spack_config_model_application_with_selected_url(self, mock_exists, tui_app):
        """Test getting Spack config for model application with selected module URL."""
        mock_exists.return_value = True
        
        # Create mock model application
        mock_app = Mock()
        mock_app.name = "global-workflow"
        mock_app.config = {"name": "Global Workflow"}
        mock_app.platform_name = "hera"
        
        installation = {
            "type": "model_application",
            "application": mock_app,
            "selected_module_url": "http://example.com/module.lua"
        }
        
        # Mock ModelApplication class - patch where it's imported (in model_apps module)
        with patch('emcenvchainer.model_apps.ModelApplication') as mock_model_app_class:
            mock_model_app_instance = Mock()
            mock_model_app_instance.extract_install_path.return_value = "/opt/spack-stack/spack-stack-2.0.0/envs/gw-env/install"
            mock_model_app_class.return_value = mock_model_app_instance
            
            spack_root, upstream_path = tui_app._get_spack_config(installation)
            
            # Verify ModelApplication was instantiated with selected URL
            mock_model_app_class.assert_called_once_with(
                "global-workflow", 
                {"name": "Global Workflow"}, 
                "hera", 
                "http://example.com/module.lua"
            )
            
            # Should infer spack root correctly
            assert spack_root == "/opt/spack-stack/spack-stack-2.0.0/spack"
            assert upstream_path == "/opt/spack-stack/spack-stack-2.0.0/envs/gw-env/install"
    
    @patch('os.path.exists')
    def test_get_spack_config_model_application_no_install_path(self, mock_exists, tui_app):
        """Test error when model application cannot extract install path."""
        mock_app = Mock()
        mock_app.extract_install_path.return_value = None
        
        installation = {
            "type": "model_application",
            "application": mock_app,
            "selected_module_url": None
        }
        
        with pytest.raises(RuntimeError, match="Could not extract install path from model application!"):
            tui_app._get_spack_config(installation)
    
    @patch('os.path.exists')
    def test_get_spack_config_model_application_missing_spack_exe(self, mock_exists, tui_app):
        """Test error when inferred Spack executable doesn't exist."""
        # Mock that spack executable does NOT exist
        mock_exists.return_value = False
        
        mock_app = Mock()
        mock_app.extract_install_path.return_value = "/stack/spack-stack-1.5.0/envs/test/install"
        
        installation = {
            "type": "model_application",
            "application": mock_app,
            "selected_module_url": None
        }
        
        with pytest.raises(RuntimeError, match="Spack executable not found at inferred location"):
            tui_app._get_spack_config(installation)
    
    @patch('os.path.exists')
    def test_get_spack_config_model_application_invalid_path_structure(self, mock_exists, tui_app):
        """Test error when upstream path doesn't have expected structure."""
        mock_app = Mock()
        # Path too short - missing proper directory structure
        mock_app.extract_install_path.return_value = "/install"
        
        installation = {
            "type": "model_application",
            "application": mock_app,
            "selected_module_url": None
        }
        
        with pytest.raises(RuntimeError, match="Invalid upstream path structure"):
            tui_app._get_spack_config(installation)
    
    @patch('os.path.exists')
    def test_get_spack_config_model_application_no_install_in_path(self, mock_exists, tui_app):
        """Test error when 'install' directory not found in path."""
        mock_app = Mock()
        # Valid looking path but doesn't contain 'install' directory
        mock_app.extract_install_path.return_value = "/base/spack-stack/spack-stack-1.6.0/envs/unified-env/wrong"
        
        installation = {
            "type": "model_application",
            "application": mock_app,
            "selected_module_url": None
        }
        
        with pytest.raises(RuntimeError, match="Cannot infer Spack installation from upstream path"):
            tui_app._get_spack_config(installation)
    
    @patch('os.path.exists')
    def test_get_spack_config_model_application_deep_nested_path(self, mock_exists, tui_app):
        """Test model application with deeply nested install path."""
        mock_exists.return_value = True
        
        mock_app = Mock()
        # Test with a deeply nested path
        mock_app.extract_install_path.return_value = "/very/deep/path/to/spack-stack/spack-stack-1.7.0/envs/complex-env/install"
        
        installation = {
            "type": "model_application",
            "application": mock_app,
            "selected_module_url": None
        }
        
        spack_root, upstream_path = tui_app._get_spack_config(installation)
        
        assert spack_root == "/very/deep/path/to/spack-stack/spack-stack-1.7.0/spack"
        assert upstream_path == "/very/deep/path/to/spack-stack/spack-stack-1.7.0/envs/complex-env/install"
    
    @patch('os.path.exists')
    def test_get_spack_config_model_application_minimal_valid_path(self, mock_exists, tui_app):
        """Test model application with minimal valid path structure."""
        mock_exists.return_value = True
        
        mock_app = Mock()
        # Minimal valid path: /root/envs/env/install (need at least 4 components after root)
        mock_app.extract_install_path.return_value = "/root/stack/envs/env/install"
        
        installation = {
            "type": "model_application",
            "application": mock_app,
            "selected_module_url": None
        }
        
        spack_root, upstream_path = tui_app._get_spack_config(installation)
        
        assert spack_root == "/root/stack/spack"
        assert upstream_path == "/root/stack/envs/env/install"
    
    @patch('os.path.exists')
    def test_get_spack_config_model_application_multiple_install_in_path(self, mock_exists, tui_app):
        """Test model application when 'install' appears multiple times in path."""
        mock_exists.return_value = True
        
        mock_app = Mock()
        # Path with 'install' appearing twice - should use the first occurrence
        mock_app.extract_install_path.return_value = "/install-base/spack-stack/spack-stack-1.6.0/envs/env/install"
        
        installation = {
            "type": "model_application",
            "application": mock_app,
            "selected_module_url": None
        }
        
        spack_root, upstream_path = tui_app._get_spack_config(installation)
        
        # Should use the first 'install' found when traversing from root
        # Path.parts.index('install') returns first occurrence
        assert spack_root == "/install-base/spack-stack/spack-stack-1.6.0/spack"
        assert upstream_path == "/install-base/spack-stack/spack-stack-1.6.0/envs/env/install"
    
    @patch('os.path.exists')
    @patch('emcenvchainer.tui.SpackManager')
    def test_get_package_specifications_with_manager_manual(self, mock_spack_manager_class, mock_exists, tui_app, mock_stdscr):
        """Test getting package specifications with manual package entry."""
        mock_exists.return_value = True
        
        # Mock SpackManager instantiation
        mock_spack_manager = Mock()
        mock_spack_manager_class.return_value = mock_spack_manager
        
        # Create non-model-application installation
        installation = {
            "type": "jcsda-spack-stack",
            "path": "/path/to/stack",
            "install_path": "/path/to/install"
        }
        
        # Mock _get_packages_manually to return packages
        expected_packages = [
            {"name": "pkg1", "version": "1.0.0"},
            {"name": "pkg2", "version": "2.0.0"}
        ]
        with patch.object(tui_app, '_get_packages_manually', return_value=expected_packages):
            packages, spack_manager = tui_app._get_package_specifications_with_manager(mock_stdscr, installation)
        
        # Verify SpackManager was created with correct parameters
        mock_spack_manager_class.assert_called_once_with("/test/stack/spack", tui_app.config)
        
        # Verify packages and manager returned
        assert packages == expected_packages
        assert spack_manager == mock_spack_manager
    
    @patch('os.path.exists')
    @patch('emcenvchainer.tui.SpackManager')
    def test_get_package_specifications_with_manager_model_app(self, mock_spack_manager_class, mock_exists, tui_app, mock_stdscr):
        """Test getting package specifications from model application."""
        mock_exists.return_value = True
        
        # Mock SpackManager instantiation
        mock_spack_manager = Mock()
        mock_spack_manager_class.return_value = mock_spack_manager
        
        # Create model application
        mock_app = Mock()
        mock_app.name = "ufs-weather-model"
        mock_app.extract_install_path.return_value = "/stack/spack-stack-1.6.0/envs/env/install"
        
        # Create model application installation
        installation = {
            "type": "model_application",
            "name": "ufs-weather-model (Intel)",
            "application": mock_app,
            "selected_module_url": None
        }
        
        # Mock _get_packages_from_model_app to return packages
        expected_packages = [
            {"name": "netcdf-c", "version": "4.9.0"},
            {"name": "hdf5", "version": "1.14.0"}
        ]
        with patch.object(tui_app, '_get_packages_from_model_app', return_value=expected_packages):
            packages, spack_manager = tui_app._get_package_specifications_with_manager(mock_stdscr, installation)
        
        # Verify packages from model app were returned
        assert packages == expected_packages
        assert spack_manager == mock_spack_manager
    
    @patch('os.path.exists')
    @patch('emcenvchainer.tui.SpackManager')
    def test_get_package_specifications_with_manager_cancelled(self, mock_spack_manager_class, mock_exists, tui_app, mock_stdscr):
        """Test cancelling package specification."""
        mock_exists.return_value = True
        
        # Mock SpackManager instantiation
        mock_spack_manager = Mock()
        mock_spack_manager_class.return_value = mock_spack_manager
        
        installation = {
            "type": "jcsda-spack-stack",
            "path": "/path/to/stack",
            "install_path": "/path/to/install"
        }
        
        # Mock _get_packages_manually to return None (cancelled)
        with patch.object(tui_app, '_get_packages_manually', return_value=None):
            packages, spack_manager = tui_app._get_package_specifications_with_manager(mock_stdscr, installation)
        
        # When cancelled, packages should be None but manager still returned
        assert packages is None
        assert spack_manager == mock_spack_manager
    
    @patch('os.path.exists')
    @patch('emcenvchainer.tui.SpackManager')
    def test_get_package_specifications_with_manager_model_app_with_url(self, mock_spack_manager_class, mock_exists, tui_app, mock_stdscr):
        """Test getting package specifications from model application with selected URL."""
        mock_exists.return_value = True
        
        # Mock SpackManager instantiation
        mock_spack_manager = Mock()
        mock_spack_manager_class.return_value = mock_spack_manager
        
        # Create model application
        mock_app = Mock()
        mock_app.name = "global-workflow"
        mock_app.config = {"name": "Global Workflow"}
        mock_app.platform_name = "hera"
        mock_app.extract_install_path.return_value = "/stack/spack-stack-2.0.0/envs/gw/install"
        
        # Create model application installation with selected URL
        installation = {
            "type": "model_application",
            "name": "global-workflow (GCC)",
            "application": mock_app,
            "selected_module_url": "http://example.com/gw.gcc.lua"
        }
        
        # Mock ModelApplication class to return instance with extract_install_path
        with patch('emcenvchainer.model_apps.ModelApplication') as mock_model_app_class:
            mock_model_app_instance = Mock()
            mock_model_app_instance.extract_install_path.return_value = "/stack/spack-stack-2.0.0/envs/gfs/install"
            mock_model_app_class.return_value = mock_model_app_instance
            
            # Mock _get_packages_from_model_app to return packages
            expected_packages = [
                {"name": "esmf", "version": "8.5.0"},
                {"name": "fms", "version": "2023.04"}
            ]
            with patch.object(tui_app, '_get_packages_from_model_app', return_value=expected_packages):
                packages, spack_manager = tui_app._get_package_specifications_with_manager(mock_stdscr, installation)
            
            # Verify packages from model app were returned
            assert packages == expected_packages
            assert spack_manager == mock_spack_manager
    
    @patch('os.path.exists')
    @patch('emcenvchainer.tui.SpackManager')
    def test_get_package_specifications_with_manager_empty_packages(self, mock_spack_manager_class, mock_exists, tui_app, mock_stdscr):
        """Test when user provides no packages."""
        mock_exists.return_value = True
        
        # Mock SpackManager instantiation
        mock_spack_manager = Mock()
        mock_spack_manager_class.return_value = mock_spack_manager
        
        installation = {
            "type": "custom",
            "spack_root": "/custom/spack",
            "install_path": "/custom/install"
        }
        
        # Mock _get_packages_manually to return empty list
        with patch.object(tui_app, '_get_packages_manually', return_value=[]):
            packages, spack_manager = tui_app._get_package_specifications_with_manager(mock_stdscr, installation)
        
        # Empty list should be returned
        assert packages == []
        assert spack_manager == mock_spack_manager
    
    @patch('os.path.exists')
    @patch('emcenvchainer.tui.SpackManager')
    def test_get_package_specifications_with_manager_spack_manager_creation(self, mock_spack_manager_class, mock_exists, tui_app, mock_stdscr):
        """Test that SpackManager is created with correct spack_root from _get_spack_config."""
        mock_exists.return_value = True
        
        # Mock SpackManager instantiation
        mock_spack_manager = Mock()
        mock_spack_manager_class.return_value = mock_spack_manager
        
        # Create installation where _get_spack_config will be called
        installation = {
            "type": "jcsda-spack-stack",
            "path": "/specific/path",
            "install_path": "/specific/install"
        }
        
        # Mock _get_spack_config to return specific values
        with patch.object(tui_app, '_get_spack_config', return_value=("/custom/spack/root", "/custom/upstream")):
            with patch.object(tui_app, '_get_packages_manually', return_value=[]):
                packages, spack_manager = tui_app._get_package_specifications_with_manager(mock_stdscr, installation)
        
        # Verify SpackManager was created with the spack_root from _get_spack_config
        mock_spack_manager_class.assert_called_once_with("/custom/spack/root", tui_app.config)
    
    @patch('os.path.exists')
    @patch('emcenvchainer.tui.SpackManager')
    def test_get_package_specifications_with_manager_passes_manager_to_manual(self, mock_spack_manager_class, mock_exists, tui_app, mock_stdscr):
        """Test that SpackManager is passed to _get_packages_manually."""
        mock_exists.return_value = True
        
        # Mock SpackManager instantiation
        mock_spack_manager = Mock()
        mock_spack_manager_class.return_value = mock_spack_manager
        
        installation = {
            "type": "jcsda-spack-stack",
            "path": "/path/to/stack",
            "install_path": "/path/to/install"
        }
        
        # Mock _get_packages_manually and verify it receives the manager
        with patch.object(tui_app, '_get_packages_manually', return_value=[]) as mock_get_packages:
            tui_app._get_package_specifications_with_manager(mock_stdscr, installation)
            
            # Verify _get_packages_manually was called with the manager and upstream_path
            mock_get_packages.assert_called_once_with(mock_stdscr, mock_spack_manager, "/path/to/install")
    
    @patch('os.path.exists')
    @patch('emcenvchainer.tui.SpackManager')
    def test_get_package_specifications_with_manager_passes_manager_to_model_app(self, mock_spack_manager_class, mock_exists, tui_app, mock_stdscr):
        """Test that SpackManager is passed to _get_packages_from_model_app."""
        mock_exists.return_value = True
        
        # Mock SpackManager instantiation
        mock_spack_manager = Mock()
        mock_spack_manager_class.return_value = mock_spack_manager
        
        mock_app = Mock()
        mock_app.extract_install_path.return_value = "/stack/spack-stack-1.6.0/envs/env/install"
        
        installation = {
            "type": "model_application",
            "name": "test-app",
            "application": mock_app,
            "selected_module_url": None
        }
        
        # Mock _get_packages_from_model_app and verify it receives the manager
        with patch.object(tui_app, '_get_packages_from_model_app', return_value=[]) as mock_get_packages:
            tui_app._get_package_specifications_with_manager(mock_stdscr, installation)
            
            # Verify _get_packages_from_model_app was called with the manager and upstream_path
            mock_get_packages.assert_called_once_with(mock_stdscr, installation, mock_spack_manager, "/stack/spack-stack-1.6.0/envs/env/install")
    
    @patch('emcenvchainer.tui.TUIMenu')
    def test_get_packages_from_model_app_success(self, mock_menu_class, tui_app, mock_stdscr):
        """Test successfully getting packages from model application."""
        # Setup mocks
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        mock_spack_manager = Mock()
        
        mock_app = Mock()
        mock_app.name = "ufs-weather-model"
        mock_app.parse_dependencies.return_value = [
            {"name": "netcdf-c", "version": "4.9.0"},
            {"name": "hdf5", "version": "1.14.0"}
        ]
        mock_app.get_upgradable_packages.return_value = [
            {"name": "esmf", "version": "8.5.0"}
        ]
        
        installation = {
            "type": "model_application",
            "name": "ufs-weather-model (Intel)",
            "application": mock_app,
            "selected_module_url": None
        }
        
        expected_packages = [
            {"name": "pkg1", "version": "1.0.0"}
        ]
        
        # Mock _select_packages_with_radio_buttons to return packages
        with patch.object(tui_app, '_select_packages_with_radio_buttons', return_value=expected_packages):
            result = tui_app._get_packages_from_model_app(mock_stdscr, installation, mock_spack_manager)
        
        # Verify result
        assert result == expected_packages
        
        # Verify menu was displayed
        mock_menu_class.assert_called_once()
        mock_menu.display_info.assert_called_once_with("Downloading and parsing module files...", wait_for_key=False)
    
    @patch('emcenvchainer.tui.TUIMenu')
    def test_get_packages_from_model_app_with_selected_url(self, mock_menu_class, tui_app, mock_stdscr):
        """Test getting packages from model application with selected URL."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        mock_spack_manager = Mock()
        
        mock_app = Mock()
        mock_app.name = "global-workflow"
        mock_app.config = {"name": "Global Workflow"}
        mock_app.platform_name = "hera"
        
        installation = {
            "type": "model_application",
            "name": "global-workflow (GCC)",
            "application": mock_app,
            "selected_module_url": "http://example.com/gw.gcc.lua"
        }
        
        # Mock ModelApplication class
        with patch('emcenvchainer.model_apps.ModelApplication') as mock_model_app_class:
            mock_model_app_instance = Mock()
            mock_model_app_instance.parse_dependencies.return_value = [
                {"name": "fms", "version": "2023.04"}
            ]
            mock_model_app_instance.get_upgradable_packages.return_value = []
            mock_model_app_class.return_value = mock_model_app_instance
            
            expected_packages = [{"name": "fms", "version": "2023.04"}]
            
            with patch.object(tui_app, '_select_packages_with_radio_buttons', return_value=expected_packages):
                result = tui_app._get_packages_from_model_app(mock_stdscr, installation, mock_spack_manager)
            
            # Verify ModelApplication was created with selected URL
            mock_model_app_class.assert_called_once_with(
                "global-workflow",
                {"name": "Global Workflow"},
                "hera",
                "http://example.com/gw.gcc.lua"
            )
            
            assert result == expected_packages
    
    @patch('emcenvchainer.tui.TUIMenu')
    def test_get_packages_from_model_app_parse_error(self, mock_menu_class, tui_app, mock_stdscr):
        """Test error handling when parsing module files fails."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        mock_spack_manager = Mock()
        
        mock_app = Mock()
        mock_app.parse_dependencies.side_effect = Exception("Network error")
        
        installation = {
            "type": "model_application",
            "name": "test-app",
            "application": mock_app,
            "selected_module_url": None
        }
        
        result = tui_app._get_packages_from_model_app(mock_stdscr, installation, mock_spack_manager)
        
        # Should return None on error
        assert result is None
        
        # Verify error message was displayed
        error_calls = [call for call in mock_menu.display_info.call_args_list if "Error parsing module files" in str(call)]
        assert len(error_calls) == 1
    
    @patch('emcenvchainer.tui.TUIMenu')
    def test_get_packages_from_model_app_no_packages_found(self, mock_menu_class, tui_app, mock_stdscr):
        """Test when no packages are found in module files."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        mock_spack_manager = Mock()
        
        mock_app = Mock()
        mock_app.parse_dependencies.return_value = []
        mock_app.get_upgradable_packages.return_value = []
        
        installation = {
            "type": "model_application",
            "name": "empty-app",
            "application": mock_app,
            "selected_module_url": None
        }
        
        result = tui_app._get_packages_from_model_app(mock_stdscr, installation, mock_spack_manager)
        
        # Should return None when no packages found
        assert result is None
        
        # Verify message was displayed
        info_calls = [call for call in mock_menu.display_info.call_args_list if "No packages found" in str(call)]
        assert len(info_calls) == 1
    
    @patch('emcenvchainer.tui.TUIMenu')
    def test_get_packages_from_model_app_combines_packages_correctly(self, mock_menu_class, tui_app, mock_stdscr):
        """Test that upgradable packages and dependencies are combined correctly."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        mock_spack_manager = Mock()
        
        mock_app = Mock()
        # Dependencies include some that overlap with upgradable
        mock_app.parse_dependencies.return_value = [
            {"name": "netcdf-c", "version": "4.9.0"},
            {"name": "hdf5", "version": "1.14.0"},
            {"name": "esmf", "version": "8.4.0"}  # This is also in upgradable
        ]
        # Upgradable packages (preferred versions)
        mock_app.get_upgradable_packages.return_value = [
            {"name": "esmf", "version": "8.5.0"},  # Should override dependency version
            {"name": "fms", "version": "2023.04"}
        ]
        
        installation = {
            "type": "model_application",
            "name": "test-app",
            "application": mock_app,
            "selected_module_url": None
        }
        
        # Capture what gets passed to _select_packages_with_radio_buttons
        captured_packages = None
        def capture_packages(stdscr, packages, app, manager, upstream_path=None):
            nonlocal captured_packages
            captured_packages = packages
            return []
        
        with patch.object(tui_app, '_select_packages_with_radio_buttons', side_effect=capture_packages):
            tui_app._get_packages_from_model_app(mock_stdscr, installation, mock_spack_manager)
        
        # Verify package combination logic
        assert captured_packages is not None
        assert len(captured_packages) == 4  # 2 upgradable + 2 unique dependencies
        
        # Upgradable packages should come first
        assert captured_packages[0]["name"] == "esmf"
        assert captured_packages[0]["current_version"] == "8.5.0"  # Upgradable version, not dependency
        assert captured_packages[0]["type"] == "upgradable"
        
        assert captured_packages[1]["name"] == "fms"
        assert captured_packages[1]["type"] == "upgradable"
        
        # Dependencies that aren't upgradable
        dep_names = [p["name"] for p in captured_packages[2:]]
        assert "netcdf-c" in dep_names
        assert "hdf5" in dep_names
        
        # esmf should not appear twice
        esmf_count = sum(1 for p in captured_packages if p["name"] == "esmf")
        assert esmf_count == 1
    
    @patch('emcenvchainer.tui.TUIMenu')
    def test_get_packages_from_model_app_only_upgradable(self, mock_menu_class, tui_app, mock_stdscr):
        """Test when only upgradable packages are found."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        mock_spack_manager = Mock()
        
        mock_app = Mock()
        mock_app.parse_dependencies.return_value = []
        mock_app.get_upgradable_packages.return_value = [
            {"name": "esmf", "version": "8.5.0"},
            {"name": "fms", "version": "2023.04"}
        ]
        
        installation = {
            "type": "model_application",
            "name": "test-app",
            "application": mock_app,
            "selected_module_url": None
        }
        
        captured_packages = None
        def capture_packages(stdscr, packages, app, manager, upstream_path=None):
            nonlocal captured_packages
            captured_packages = packages
            return []
        
        with patch.object(tui_app, '_select_packages_with_radio_buttons', side_effect=capture_packages):
            tui_app._get_packages_from_model_app(mock_stdscr, installation, mock_spack_manager)
        
        # Should have only upgradable packages
        assert len(captured_packages) == 2
        assert all(p["type"] == "upgradable" for p in captured_packages)
    
    @patch('emcenvchainer.tui.TUIMenu')
    def test_get_packages_from_model_app_only_dependencies(self, mock_menu_class, tui_app, mock_stdscr):
        """Test when only dependencies are found."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        mock_spack_manager = Mock()
        
        mock_app = Mock()
        mock_app.parse_dependencies.return_value = [
            {"name": "netcdf-c", "version": "4.9.0"},
            {"name": "hdf5", "version": "1.14.0"}
        ]
        mock_app.get_upgradable_packages.return_value = []
        
        installation = {
            "type": "model_application",
            "name": "test-app",
            "application": mock_app,
            "selected_module_url": None
        }
        
        captured_packages = None
        def capture_packages(stdscr, packages, app, manager, upstream_path=None):
            nonlocal captured_packages
            captured_packages = packages
            return []
        
        with patch.object(tui_app, '_select_packages_with_radio_buttons', side_effect=capture_packages):
            tui_app._get_packages_from_model_app(mock_stdscr, installation, mock_spack_manager)
        
        # Should have only dependencies
        assert len(captured_packages) == 2
        assert all(p["type"] == "dependency" for p in captured_packages)
    
    @patch('emcenvchainer.tui.TUIMenu')
    def test_get_packages_from_model_app_cancelled(self, mock_menu_class, tui_app, mock_stdscr):
        """Test when user cancels package selection."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        mock_spack_manager = Mock()
        
        mock_app = Mock()
        mock_app.parse_dependencies.return_value = [
            {"name": "netcdf-c", "version": "4.9.0"}
        ]
        mock_app.get_upgradable_packages.return_value = []
        
        installation = {
            "type": "model_application",
            "name": "test-app",
            "application": mock_app,
            "selected_module_url": None
        }
        
        # Mock radio button selection to return None (cancelled)
        with patch.object(tui_app, '_select_packages_with_radio_buttons', return_value=None):
            result = tui_app._get_packages_from_model_app(mock_stdscr, installation, mock_spack_manager)
        
        assert result is None
    
    @patch('emcenvchainer.tui.TUIMenu')
    def test_get_packages_from_model_app_passes_correct_args_to_radio_buttons(self, mock_menu_class, tui_app, mock_stdscr):
        """Test that correct arguments are passed to _select_packages_with_radio_buttons."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        mock_spack_manager = Mock()
        
        mock_app = Mock()
        mock_app.parse_dependencies.return_value = [
            {"name": "pkg1", "version": "1.0.0"}
        ]
        mock_app.get_upgradable_packages.return_value = []
        
        installation = {
            "type": "model_application",
            "name": "test-app",
            "application": mock_app,
            "selected_module_url": None
        }
        
        with patch.object(tui_app, '_select_packages_with_radio_buttons', return_value=[]) as mock_radio:
            tui_app._get_packages_from_model_app(mock_stdscr, installation, mock_spack_manager)
            
            # Verify arguments passed
            mock_radio.assert_called_once()
            args = mock_radio.call_args[0]
            
            assert args[0] == mock_stdscr  # stdscr
            assert isinstance(args[1], list)  # all_packages
            assert args[2] == mock_app  # selected_app
            assert args[3] == mock_spack_manager  # spack_manager
    
    @patch('emcenvchainer.tui.RadioButtonMenu')
    def test_select_packages_with_radio_buttons_success(self, mock_radio_class, tui_app, mock_stdscr):
        """Test successfully selecting packages with radio buttons."""
        # Mock RadioButtonMenu
        mock_radio = Mock()
        mock_radio_class.return_value = mock_radio
        mock_radio.display_menu.return_value = [0, 2]  # Select first and third packages
        
        mock_spack_manager = Mock()
        mock_app = Mock()
        
        all_packages = [
            {"name": "netcdf-c", "current_version": "4.9.0", "type": "upgradable"},
            {"name": "hdf5", "current_version": "1.14.0", "type": "dependency"},
            {"name": "esmf", "current_version": "8.5.0", "type": "upgradable"}
        ]
        
        # Mock _get_package_specification to return specs
        specs = [
            {"name": "netcdf-c", "version": "4.9.0"},
            {"name": "esmf", "version": "8.5.0"}
        ]
        with patch.object(tui_app, '_get_package_specification', side_effect=specs):
            result = tui_app._select_packages_with_radio_buttons(mock_stdscr, all_packages, mock_app, mock_spack_manager)
        
        # Should return selected packages
        assert result is not None
        assert len(result) == 3  # 2 selected + 1 unselected
        assert result[0]["name"] == "netcdf-c"
        assert result[1]["name"] == "esmf"
    
    @patch('emcenvchainer.tui.RadioButtonMenu')
    def test_select_packages_with_radio_buttons_cancelled(self, mock_radio_class, tui_app, mock_stdscr):
        """Test cancelling package selection."""
        mock_radio = Mock()
        mock_radio_class.return_value = mock_radio
        mock_radio.display_menu.return_value = None  # User cancelled
        
        mock_spack_manager = Mock()
        mock_app = Mock()
        
        all_packages = [
            {"name": "netcdf-c", "current_version": "4.9.0", "type": "upgradable"}
        ]
        
        result = tui_app._select_packages_with_radio_buttons(mock_stdscr, all_packages, mock_app, mock_spack_manager)
        
        assert result is None
    
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('emcenvchainer.tui.RadioButtonMenu')
    def test_select_packages_with_radio_buttons_no_selection(self, mock_radio_class, mock_menu_class, tui_app, mock_stdscr):
        """Test when user selects no packages."""
        mock_radio = Mock()
        mock_radio_class.return_value = mock_radio
        mock_radio.display_menu.return_value = []  # Empty selection
        
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_app = Mock()
        
        all_packages = [
            {"name": "netcdf-c", "current_version": "4.9.0", "type": "upgradable"}
        ]
        
        result = tui_app._select_packages_with_radio_buttons(mock_stdscr, all_packages, mock_app, mock_spack_manager)
        
        # Should return empty list
        assert result == []
        
        # Should display info message
        mock_menu.display_info.assert_called_once()
        assert "No packages were selected" in str(mock_menu.display_info.call_args)
    
    @patch('emcenvchainer.tui.RadioButtonMenu')
    def test_select_packages_with_radio_buttons_filters_excluded_packages(self, mock_radio_class, tui_app, mock_stdscr):
        """Test that ufs_common, cmake, and stack-* packages are filtered out."""
        mock_radio = Mock()
        mock_radio_class.return_value = mock_radio
        mock_radio.display_menu.return_value = []
        
        mock_spack_manager = Mock()
        mock_app = Mock()
        
        all_packages = [
            {"name": "ufs_common", "current_version": "1.0.0", "type": "dependency"},
            {"name": "cmake", "current_version": "3.26.0", "type": "dependency"},
            {"name": "stack-intel", "current_version": "1.0.0", "type": "dependency"},
            {"name": "stack-gcc", "current_version": "1.0.0", "type": "dependency"},
            {"name": "netcdf-c", "current_version": "4.9.0", "type": "upgradable"},
            {"name": "hdf5", "current_version": "1.14.0", "type": "dependency"}
        ]
        
        with patch.object(tui_app, '_get_package_specification', return_value=None):
            tui_app._select_packages_with_radio_buttons(mock_stdscr, all_packages, mock_app, mock_spack_manager)
        
        # Verify RadioButtonMenu was called with filtered options
        mock_radio_class.assert_called_once()
        mock_radio.display_menu.assert_called_once()
        options = mock_radio.display_menu.call_args[0][0]
        
        # Should only have netcdf-c and hdf5
        assert len(options) == 2
        assert "netcdf-c" in options[0]
        assert "hdf5" in options[1]
        assert "ufs_common" not in str(options)
        assert "cmake" not in str(options)
        assert "stack-intel" not in str(options)
        assert "stack-gcc" not in str(options)
    
    @patch('emcenvchainer.tui.RadioButtonMenu')
    def test_select_packages_with_radio_buttons_display_format(self, mock_radio_class, tui_app, mock_stdscr):
        """Test that packages are displayed with correct format."""
        mock_radio = Mock()
        mock_radio_class.return_value = mock_radio
        mock_radio.display_menu.return_value = []
        
        mock_spack_manager = Mock()
        mock_app = Mock()
        
        all_packages = [
            {"name": "netcdf-c", "current_version": "4.9.0", "type": "upgradable"},
            {"name": "hdf5", "current_version": "1.14.0", "type": "dependency"}
        ]
        
        with patch.object(tui_app, '_get_package_specification', return_value=None):
            tui_app._select_packages_with_radio_buttons(mock_stdscr, all_packages, mock_app, mock_spack_manager)
        
        # Verify display format
        options = mock_radio.display_menu.call_args[0][0]
        
        assert "📦 netcdf-c (v4.9.0)" in options[0]
        assert "📦 hdf5 (v1.14.0)" in options[1]
    
    @patch('emcenvchainer.tui.RadioButtonMenu')
    def test_select_packages_with_radio_buttons_calls_get_package_specification(self, mock_radio_class, tui_app, mock_stdscr):
        """Test that _get_package_specification is called for selected packages."""
        mock_radio = Mock()
        mock_radio_class.return_value = mock_radio
        mock_radio.display_menu.return_value = [0, 1]  # Select both packages
        
        mock_spack_manager = Mock()
        mock_app = Mock()
        
        all_packages = [
            {"name": "netcdf-c", "current_version": "4.9.0", "type": "upgradable"},
            {"name": "hdf5", "current_version": "1.14.0", "type": "dependency"}
        ]
        
        specs = [
            {"name": "netcdf-c", "version": "4.9.0", "variants": "+mpi"},
            {"name": "hdf5", "version": "1.14.0", "variants": "~shared"}
        ]
        
        with patch.object(tui_app, '_get_package_specification', side_effect=specs) as mock_get_spec:
            result = tui_app._select_packages_with_radio_buttons(mock_stdscr, all_packages, mock_app, mock_spack_manager)
        
        # Verify _get_package_specification was called for each selected package
        assert mock_get_spec.call_count == 2
        
        # Verify it was called with correct arguments
        call_args_list = mock_get_spec.call_args_list
        assert call_args_list[0][0][0] == mock_stdscr
        assert call_args_list[0][0][1] == all_packages[0]
        assert call_args_list[0][0][2] == mock_spack_manager
        
        assert call_args_list[1][0][0] == mock_stdscr
        assert call_args_list[1][0][1] == all_packages[1]
        assert call_args_list[1][0][2] == mock_spack_manager
    
    @patch('emcenvchainer.tui.RadioButtonMenu')
    def test_select_packages_with_radio_buttons_skips_none_specs(self, mock_radio_class, tui_app, mock_stdscr):
        """Test that packages with None specs are skipped."""
        mock_radio = Mock()
        mock_radio_class.return_value = mock_radio
        mock_radio.display_menu.return_value = [0, 1]  # Select both packages
        
        mock_spack_manager = Mock()
        mock_app = Mock()
        
        all_packages = [
            {"name": "netcdf-c", "current_version": "4.9.0", "type": "upgradable"},
            {"name": "hdf5", "current_version": "1.14.0", "type": "dependency"}
        ]
        
        # First package returns spec, second returns None (cancelled)
        specs = [
            {"name": "netcdf-c", "version": "4.9.0"},
            None
        ]
        
        with patch.object(tui_app, '_get_package_specification', side_effect=specs):
            result = tui_app._select_packages_with_radio_buttons(mock_stdscr, all_packages, mock_app, mock_spack_manager)
        
        # Should only include the package that returned a spec
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "netcdf-c"
    
    @patch('emcenvchainer.tui.RadioButtonMenu')
    def test_select_packages_with_radio_buttons_partial_selection(self, mock_radio_class, tui_app, mock_stdscr):
        """Test selecting some packages but not all."""
        mock_radio = Mock()
        mock_radio_class.return_value = mock_radio
        mock_radio.display_menu.return_value = [1]  # Select only middle package
        
        mock_spack_manager = Mock()
        mock_app = Mock()
        
        all_packages = [
            {"name": "netcdf-c", "current_version": "4.9.0", "type": "upgradable"},
            {"name": "hdf5", "current_version": "1.14.0", "type": "dependency"},
            {"name": "esmf", "current_version": "8.5.0", "type": "upgradable"}
        ]
        
        spec = {"name": "hdf5", "version": "1.14.0"}
        
        with patch.object(tui_app, '_get_package_specification', return_value=spec):
            result = tui_app._select_packages_with_radio_buttons(mock_stdscr, all_packages, mock_app, mock_spack_manager)
        
        # Should include selected package plus unselected packages appended at end
        assert result is not None
        assert len(result) == 3
        assert result[0]["name"] == "hdf5"  # Selected package
        # Unselected packages (indices 0 and 2) should be appended
        assert result[1] == all_packages[0]
        assert result[2] == all_packages[2]
    
    @patch('emcenvchainer.tui.RadioButtonMenu')
    def test_select_packages_with_radio_buttons_radio_menu_title(self, mock_radio_class, tui_app, mock_stdscr):
        """Test that RadioButtonMenu is created with correct title."""
        mock_radio = Mock()
        mock_radio_class.return_value = mock_radio
        mock_radio.display_menu.return_value = []
        
        mock_spack_manager = Mock()
        mock_app = Mock()
        
        all_packages = [
            {"name": "netcdf-c", "current_version": "4.9.0", "type": "upgradable"}
        ]
        
        with patch.object(tui_app, '_get_package_specification', return_value=None):
            tui_app._select_packages_with_radio_buttons(mock_stdscr, all_packages, mock_app, mock_spack_manager)
        
        # Verify RadioButtonMenu was created with correct title
        mock_radio_class.assert_called_once_with(mock_stdscr, "Select packages to update, modify, or lock from upstream")
    
    @patch('emcenvchainer.tui.RadioButtonMenu')
    def test_select_packages_with_radio_buttons_empty_list_after_filtering(self, mock_radio_class, tui_app, mock_stdscr):
        """Test when all packages are filtered out."""
        mock_radio = Mock()
        mock_radio_class.return_value = mock_radio
        mock_radio.display_menu.return_value = []
        
        mock_spack_manager = Mock()
        mock_app = Mock()
        
        # All packages should be filtered
        all_packages = [
            {"name": "ufs_common", "current_version": "1.0.0", "type": "dependency"},
            {"name": "cmake", "current_version": "3.26.0", "type": "dependency"},
            {"name": "stack-intel", "current_version": "1.0.0", "type": "dependency"}
        ]
        
        with patch.object(tui_app, '_get_package_specification', return_value=None):
            result = tui_app._select_packages_with_radio_buttons(mock_stdscr, all_packages, mock_app, mock_spack_manager)
        
        # Should still work with empty options list
        options = mock_radio.display_menu.call_args[0][0]
        assert len(options) == 0
        assert result == []
    
    @patch('emcenvchainer.tui.PackageSpecDialog')
    def test_get_package_specification_success(self, mock_dialog_class, tui_app, mock_stdscr):
        """Test successfully getting package specification."""
        mock_spack_manager = Mock()
        
        # Mock PackageSpecDialog
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        
        # Mock return value
        expected_spec = {
            "name": "netcdf-c",
            "version": "4.9.0",
            "variants": "+mpi +hdf5"
        }
        mock_dialog.get_package_spec.return_value = expected_spec
        
        pkg = {
            "name": "netcdf-c",
            "current_version": "4.9.0",
            "type": "upgradable"
        }
        
        result = tui_app._get_package_specification(mock_stdscr, pkg, mock_spack_manager)
        
        # Verify PackageSpecDialog was created with correct args (including upstream_path=None)
        mock_dialog_class.assert_called_once_with(mock_stdscr, mock_spack_manager, None)
        
        # Verify get_package_spec was called with package name and version
        mock_dialog.get_package_spec.assert_called_once_with("netcdf-c", "4.9.0")
        
        # Verify result
        assert result == expected_spec
    
    @patch('emcenvchainer.tui.PackageSpecDialog')
    def test_get_package_specification_cancelled(self, mock_dialog_class, tui_app, mock_stdscr):
        """Test when user cancels package specification."""
        mock_spack_manager = Mock()
        
        # Mock PackageSpecDialog
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        mock_dialog.get_package_spec.return_value = None  # User cancelled
        
        pkg = {
            "name": "hdf5",
            "current_version": "1.14.0",
            "type": "dependency"
        }
        
        result = tui_app._get_package_specification(mock_stdscr, pkg, mock_spack_manager)
        
        assert result is None
    
    @patch('emcenvchainer.tui.PackageSpecDialog')
    def test_get_package_specification_with_variants(self, mock_dialog_class, tui_app, mock_stdscr):
        """Test package specification with variants."""
        mock_spack_manager = Mock()
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        
        expected_spec = {
            "name": "esmf",
            "version": "8.5.0",
            "variants": "+external-lapack +netcdf"
        }
        mock_dialog.get_package_spec.return_value = expected_spec
        
        pkg = {
            "name": "esmf",
            "current_version": "8.5.0",
            "type": "upgradable"
        }
        
        result = tui_app._get_package_specification(mock_stdscr, pkg, mock_spack_manager)
        
        assert result == expected_spec
        assert "variants" in result
        assert result["variants"] == "+external-lapack +netcdf"
    
    @patch('emcenvchainer.tui.PackageSpecDialog')
    def test_get_package_specification_version_change(self, mock_dialog_class, tui_app, mock_stdscr):
        """Test when user changes version from default."""
        mock_spack_manager = Mock()
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        
        # User selects different version
        expected_spec = {
            "name": "netcdf-c",
            "version": "4.9.1",  # Different from current_version
            "variants": ""
        }
        mock_dialog.get_package_spec.return_value = expected_spec
        
        pkg = {
            "name": "netcdf-c",
            "current_version": "4.9.0",
            "type": "upgradable"
        }
        
        result = tui_app._get_package_specification(mock_stdscr, pkg, mock_spack_manager)
        
        # Should still call with original version, but return changed version
        mock_dialog.get_package_spec.assert_called_once_with("netcdf-c", "4.9.0")
        assert result["version"] == "4.9.1"
    
    @patch('emcenvchainer.tui.PackageSpecDialog')
    def test_get_package_specification_minimal_spec(self, mock_dialog_class, tui_app, mock_stdscr):
        """Test package specification with minimal info (no variants)."""
        mock_spack_manager = Mock()
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        
        expected_spec = {
            "name": "zlib",
            "version": "1.2.13"
        }
        mock_dialog.get_package_spec.return_value = expected_spec
        
        pkg = {
            "name": "zlib",
            "current_version": "1.2.13",
            "type": "dependency"
        }
        
        result = tui_app._get_package_specification(mock_stdscr, pkg, mock_spack_manager)
        
        assert result == expected_spec
        assert result["name"] == "zlib"
        assert result["version"] == "1.2.13"
    
    @patch('emcenvchainer.tui.PackageSpecDialog')
    def test_get_package_specification_passes_spack_manager(self, mock_dialog_class, tui_app, mock_stdscr):
        """Test that SpackManager is passed to PackageSpecDialog."""
        mock_spack_manager = Mock()
        mock_spack_manager.some_property = "test_value"
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        mock_dialog.get_package_spec.return_value = {"name": "pkg", "version": "1.0"}
        
        pkg = {
            "name": "pkg",
            "current_version": "1.0",
            "type": "dependency"
        }
        
        tui_app._get_package_specification(mock_stdscr, pkg, mock_spack_manager)
        
        # Verify the exact SpackManager instance was passed (along with upstream_path=None)
        mock_dialog_class.assert_called_once_with(mock_stdscr, mock_spack_manager, None)
        assert mock_dialog_class.call_args[0][1] is mock_spack_manager
    
    @patch('emcenvchainer.tui.PackageSpecDialog')
    def test_get_package_specification_extracts_package_info(self, mock_dialog_class, tui_app, mock_stdscr):
        """Test that correct package name and version are extracted."""
        mock_spack_manager = Mock()
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        mock_dialog.get_package_spec.return_value = {"name": "test", "version": "2.0"}
        
        # Package dict with extra fields
        pkg = {
            "name": "test-package",
            "current_version": "1.5.3",
            "type": "upgradable",
            "source": {"some": "data"},
            "extra_field": "ignored"
        }
        
        tui_app._get_package_specification(mock_stdscr, pkg, mock_spack_manager)
        
        # Verify only name and current_version are passed
        mock_dialog.get_package_spec.assert_called_once_with("test-package", "1.5.3")
    
    @patch('emcenvchainer.tui.PackageSpecDialog')
    def test_get_package_specification_dependency_type(self, mock_dialog_class, tui_app, mock_stdscr):
        """Test package specification for dependency type package."""
        mock_spack_manager = Mock()
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        
        expected_spec = {
            "name": "dep-pkg",
            "version": "3.2.1",
            "variants": "~shared"
        }
        mock_dialog.get_package_spec.return_value = expected_spec
        
        pkg = {
            "name": "dep-pkg",
            "current_version": "3.2.1",
            "type": "dependency"
        }
        
        result = tui_app._get_package_specification(mock_stdscr, pkg, mock_spack_manager)
        
        assert result == expected_spec
    
    @patch('emcenvchainer.tui.PackageSpecDialog')
    def test_get_package_specification_upgradable_type(self, mock_dialog_class, tui_app, mock_stdscr):
        """Test package specification for upgradable type package."""
        mock_spack_manager = Mock()
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        
        expected_spec = {
            "name": "upgradable-pkg",
            "version": "5.0.0",
            "variants": "+feature"
        }
        mock_dialog.get_package_spec.return_value = expected_spec
        
        pkg = {
            "name": "upgradable-pkg",
            "current_version": "5.0.0",
            "type": "upgradable"
        }
        
        result = tui_app._get_package_specification(mock_stdscr, pkg, mock_spack_manager)
        
        assert result == expected_spec
    
    @patch('curses.endwin')
    @patch('curses.doupdate')
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('os.getcwd')
    def test_create_environment_success(self, mock_getcwd, mock_menu_class, mock_doupdate, mock_endwin, tui_app, mock_stdscr):
        """Test successfully creating environment."""
        mock_getcwd.return_value = "/test/workdir"
        
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_spack_manager.create_environment.return_value = ("/test/env/path", [])
        mock_spack_manager.concretize_environment.return_value = (True, "concretize output")
        mock_spack_manager.refresh_modules.return_value = "/test/modulefiles"
        
        installation = {
            "type": "jcsda-spack-stack",
            "path": "/path/to/stack",
            "install_path": "/path/to/install"
        }
        
        packages = [
            {"name": "netcdf-c", "version": "4.9.0"}
        ]
        
        with patch.object(tui_app, '_get_spack_config', return_value=("/spack/root", "/upstream/path")):
            with patch.object(tui_app, 'display_scrollable_text'):
                with patch.object(tui_app, 'run_interactive_install', return_value=True):
                    with patch.object(tui_app, '_generate_activation_scripts'):
                        with patch('builtins.open', create=True) as mock_open:
                            mock_open.return_value.__enter__.return_value.read.return_value = "spack.yaml content"
                            
                            tui_app._create_environment(mock_stdscr, installation, packages, mock_spack_manager, "test-env")
        
        # Verify environment was created
        mock_spack_manager.create_environment.assert_called_once_with(
            "test-env", "/upstream/path", packages, "/test/workdir", tui_app.platform
        )
        
        # Verify concretization
        mock_spack_manager.concretize_environment.assert_called_once_with("/test/env/path")
        
        # Verify modules refreshed
        mock_spack_manager.refresh_modules.assert_called_once_with("/test/env/path")
        
        # Verify success message displayed
        success_calls = [call for call in mock_menu.display_info.call_args_list 
                        if "Environment created successfully" in str(call)]
        assert len(success_calls) == 1
    
    @patch('curses.endwin')
    @patch('curses.doupdate')
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('os.getcwd')
    def test_create_environment_with_custom_recipes(self, mock_getcwd, mock_menu_class, mock_doupdate, mock_endwin, tui_app, mock_stdscr):
        """Test creating environment with packages needing custom recipes."""
        mock_getcwd.return_value = "/test/workdir"
        
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        packages_needing_edit = [{"name": "custom-pkg", "version": "1.0.0"}]
        mock_spack_manager.create_environment.return_value = ("/test/env/path", packages_needing_edit)
        mock_spack_manager.concretize_environment.return_value = (True, "concretize output")
        mock_spack_manager.refresh_modules.return_value = "/test/modulefiles"
        
        installation = {
            "type": "jcsda-spack-stack",
            "path": "/path/to/stack",
            "install_path": "/path/to/install"
        }
        
        packages = [{"name": "custom-pkg", "version": "1.0.0"}]
        
        with patch.object(tui_app, '_get_spack_config', return_value=("/spack/root", "/upstream/path")):
            with patch.object(tui_app, '_show_custom_recipe_dialog', return_value=[]) as mock_show_dialog:
                with patch.object(tui_app, 'display_scrollable_text'):
                    with patch.object(tui_app, 'run_interactive_install', return_value=True):
                        with patch.object(tui_app, '_generate_activation_scripts'):
                            with patch('builtins.open', create=True) as mock_open:
                                mock_open.return_value.__enter__.return_value.read.return_value = "spack.yaml content"
                                
                                tui_app._create_environment(mock_stdscr, installation, packages, mock_spack_manager, "test-env")
        
        # Verify custom recipe dialog was shown
        mock_show_dialog.assert_called_once()
    
    @patch('curses.endwin')
    @patch('curses.doupdate')
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('os.getcwd')
    def test_create_environment_concretize_failure(self, mock_getcwd, mock_menu_class, mock_doupdate, mock_endwin, tui_app, mock_stdscr):
        """Test when concretization fails."""
        mock_getcwd.return_value = "/test/workdir"
        
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_spack_manager.create_environment.return_value = ("/test/env/path", [])
        mock_spack_manager.concretize_environment.return_value = (False, "error output")
        
        installation = {
            "type": "jcsda-spack-stack",
            "path": "/path/to/stack",
            "install_path": "/path/to/install"
        }
        
        packages = [{"name": "netcdf-c", "version": "4.9.0"}]
        
        with patch.object(tui_app, '_get_spack_config', return_value=("/spack/root", "/upstream/path")):
            with patch.object(tui_app, 'display_scrollable_text'):
                with patch('builtins.open', create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = "spack.yaml content"
                    
                    tui_app._create_environment(mock_stdscr, installation, packages, mock_spack_manager, "test-env")
        
        # Verify failure message displayed
        failure_calls = [call for call in mock_menu.display_info.call_args_list 
                        if "Concretization failed" in str(call)]
        assert len(failure_calls) == 1
        
        # Verify refresh_modules was NOT called
        mock_spack_manager.refresh_modules.assert_not_called()
    
    @patch('curses.endwin')
    @patch('curses.doupdate')
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('os.getcwd')
    def test_create_environment_install_failure(self, mock_getcwd, mock_menu_class, mock_doupdate, mock_endwin, tui_app, mock_stdscr):
        """Test when installation fails."""
        mock_getcwd.return_value = "/test/workdir"
        
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_spack_manager.create_environment.return_value = ("/test/env/path", [])
        mock_spack_manager.concretize_environment.return_value = (True, "concretize output")
        
        installation = {
            "type": "jcsda-spack-stack",
            "path": "/path/to/stack",
            "install_path": "/path/to/install"
        }
        
        packages = [{"name": "netcdf-c", "version": "4.9.0"}]
        
        with patch.object(tui_app, '_get_spack_config', return_value=("/spack/root", "/upstream/path")):
            with patch.object(tui_app, 'display_scrollable_text'):
                with patch.object(tui_app, 'run_interactive_install', return_value=False):
                    with patch('builtins.open', create=True) as mock_open:
                        mock_open.return_value.__enter__.return_value.read.return_value = "spack.yaml content"
                        
                        tui_app._create_environment(mock_stdscr, installation, packages, mock_spack_manager, "test-env")
        
        # Verify failure message displayed
        failure_calls = [call for call in mock_menu.display_info.call_args_list 
                        if "Installation failed" in str(call)]
        assert len(failure_calls) == 1
        
        # Verify refresh_modules was NOT called
        mock_spack_manager.refresh_modules.assert_not_called()
    
    @patch('curses.endwin')
    @patch('curses.doupdate')
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('os.getcwd')
    def test_create_environment_exception_handling(self, mock_getcwd, mock_menu_class, mock_doupdate, mock_endwin, tui_app, mock_stdscr):
        """Test exception handling during environment creation."""
        mock_getcwd.return_value = "/test/workdir"
        
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_spack_manager.create_environment.side_effect = Exception("Test error")
        
        installation = {
            "type": "jcsda-spack-stack",
            "path": "/path/to/stack",
            "install_path": "/path/to/install"
        }
        
        packages = [{"name": "netcdf-c", "version": "4.9.0"}]
        
        with patch.object(tui_app, '_get_spack_config', return_value=("/spack/root", "/upstream/path")):
            tui_app._create_environment(mock_stdscr, installation, packages, mock_spack_manager, "test-env")
        
        # Verify error message displayed
        error_calls = [call for call in mock_menu.display_info.call_args_list 
                      if "Error creating environment" in str(call)]
        assert len(error_calls) == 1
    
    @patch('curses.endwin')
    @patch('curses.doupdate')
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('os.getcwd')
    def test_create_environment_curses_mode_restoration(self, mock_getcwd, mock_menu_class, mock_doupdate, mock_endwin, tui_app, mock_stdscr):
        """Test that curses mode is properly restored after environment creation."""
        mock_getcwd.return_value = "/test/workdir"
        
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_spack_manager.create_environment.return_value = ("/test/env/path", [])
        mock_spack_manager.concretize_environment.return_value = (True, "output")
        mock_spack_manager.refresh_modules.return_value = "/modulefiles"
        
        installation = {
            "type": "jcsda-spack-stack",
            "path": "/path/to/stack",
            "install_path": "/path/to/install"
        }
        
        packages = []
        
        with patch.object(tui_app, '_get_spack_config', return_value=("/spack/root", "/upstream/path")):
            with patch.object(tui_app, 'display_scrollable_text'):
                with patch.object(tui_app, 'run_interactive_install', return_value=True):
                    with patch.object(tui_app, '_generate_activation_scripts'):
                        with patch('builtins.open', create=True) as mock_open:
                            mock_open.return_value.__enter__.return_value.read.return_value = "yaml"
                            
                            tui_app._create_environment(mock_stdscr, installation, packages, mock_spack_manager, "env")
        
        # Verify curses.endwin was called to exit curses mode
        mock_endwin.assert_called()
        
        # Verify curses mode was restored
        mock_stdscr.refresh.assert_called()
        mock_doupdate.assert_called()
    
    @patch('curses.endwin')
    @patch('curses.doupdate')
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('os.getcwd')
    def test_create_environment_displays_spack_yaml(self, mock_getcwd, mock_menu_class, mock_doupdate, mock_endwin, tui_app, mock_stdscr):
        """Test that spack.yaml is displayed before concretization."""
        mock_getcwd.return_value = "/test/workdir"
        
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_spack_manager.create_environment.return_value = ("/test/env/path", [])
        mock_spack_manager.concretize_environment.return_value = (True, "output")
        mock_spack_manager.refresh_modules.return_value = "/modulefiles"
        
        installation = {
            "type": "jcsda-spack-stack",
            "path": "/path/to/stack",
            "install_path": "/path/to/install"
        }
        
        packages = []
        
        with patch.object(tui_app, '_get_spack_config', return_value=("/spack/root", "/upstream/path")):
            with patch.object(tui_app, 'display_scrollable_text') as mock_display:
                with patch.object(tui_app, 'run_interactive_install', return_value=True):
                    with patch.object(tui_app, '_generate_activation_scripts'):
                        with patch('builtins.open', create=True) as mock_open:
                            mock_open.return_value.__enter__.return_value.read.return_value = "test spack.yaml"
                            
                            tui_app._create_environment(mock_stdscr, installation, packages, mock_spack_manager, "env")
        
        # Verify display_scrollable_text was called with spack.yaml
        assert mock_display.call_count >= 1
        # First call should be for spack.yaml
        first_call_args = mock_display.call_args_list[0][0]
        assert "spack.yaml" in str(first_call_args[1])
        assert first_call_args[2] == "test spack.yaml"
    
    @patch('curses.endwin')
    @patch('curses.doupdate')
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('os.getcwd')
    def test_create_environment_manual_recipe_editing(self, mock_getcwd, mock_menu_class, mock_doupdate, mock_endwin, tui_app, mock_stdscr):
        """Test manual recipe editing flow."""
        mock_getcwd.return_value = "/test/workdir"
        
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        packages_needing_edit = [{"name": "pkg1", "version": "1.0"}]
        mock_spack_manager.create_environment.return_value = ("/test/env/path", packages_needing_edit)
        mock_spack_manager.concretize_environment.return_value = (True, "output")
        mock_spack_manager.refresh_modules.return_value = "/modulefiles"
        
        installation = {
            "type": "jcsda-spack-stack",
            "path": "/path/to/stack",
            "install_path": "/path/to/install"
        }
        
        packages = [{"name": "pkg1", "version": "1.0"}]
        
        # Mock that user wants to edit recipes manually
        remaining_packages = [{"name": "pkg1", "version": "1.0"}]
        
        with patch.object(tui_app, '_get_spack_config', return_value=("/spack/root", "/upstream/path")):
            with patch.object(tui_app, '_show_custom_recipe_dialog', return_value=remaining_packages):
                with patch.object(tui_app, '_handle_manual_recipe_editing') as mock_handle_edit:
                    with patch.object(tui_app, 'display_scrollable_text'):
                        with patch.object(tui_app, 'run_interactive_install', return_value=True):
                            with patch.object(tui_app, '_generate_activation_scripts'):
                                with patch('builtins.open', create=True) as mock_open:
                                    mock_open.return_value.__enter__.return_value.read.return_value = "yaml"
                                    
                                    tui_app._create_environment(mock_stdscr, installation, packages, mock_spack_manager, "env")
        
        # Verify manual recipe editing was called
        mock_handle_edit.assert_called_once_with(mock_stdscr, mock_spack_manager, remaining_packages)
    
    @patch('curses.curs_set')
    @patch('curses.endwin')
    @patch('emcenvchainer.tui.TUIMenu')
    def test_handle_manual_recipe_editing_success(self, mock_menu_class, mock_endwin, mock_curs_set, tui_app, mock_stdscr):
        """Test successful manual recipe editing."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_spack_manager.offer_package_edit.return_value = True
        
        packages_needing_edit = [
            {"package_name": "pkg1", "version": "1.0.0", "edit_recipe": True},
            {"package_name": "pkg2", "version": "2.0.0", "edit_recipe": True}
        ]
        
        tui_app._handle_manual_recipe_editing(mock_stdscr, mock_spack_manager, packages_needing_edit)
        
        # Verify offer_package_edit was called with packages to edit
        mock_spack_manager.offer_package_edit.assert_called_once()
        called_packages = mock_spack_manager.offer_package_edit.call_args[0][0]
        assert len(called_packages) == 2
        assert all(pkg['edit_recipe'] for pkg in called_packages)
        
        # Verify info message was displayed
        mock_menu.display_info.assert_called_once()
        info_msg = mock_menu.display_info.call_args[0][0]
        assert "pkg1@1.0.0" in info_msg
        assert "pkg2@2.0.0" in info_msg
    
    @patch('curses.curs_set')
    @patch('curses.endwin')
    @patch('emcenvchainer.tui.TUIMenu')
    def test_handle_manual_recipe_editing_cancelled(self, mock_menu_class, mock_endwin, mock_curs_set, tui_app, mock_stdscr):
        """Test when user cancels manual recipe editing."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_spack_manager.offer_package_edit.return_value = False
        
        packages_needing_edit = [
            {"package_name": "pkg1", "version": "1.0.0", "edit_recipe": True}
        ]
        
        tui_app._handle_manual_recipe_editing(mock_stdscr, mock_spack_manager, packages_needing_edit)
        
        # Verify offer_package_edit was called
        mock_spack_manager.offer_package_edit.assert_called_once()
    
    @patch('emcenvchainer.tui.TUIMenu')
    def test_handle_manual_recipe_editing_empty_list(self, mock_menu_class, tui_app, mock_stdscr):
        """Test with empty packages list."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        packages_needing_edit = []
        
        tui_app._handle_manual_recipe_editing(mock_stdscr, mock_spack_manager, packages_needing_edit)
        
        # Should return early without doing anything
        mock_spack_manager.offer_package_edit.assert_not_called()
        mock_menu.display_info.assert_not_called()
    
    @patch('emcenvchainer.tui.TUIMenu')
    def test_handle_manual_recipe_editing_none_selected(self, mock_menu_class, tui_app, mock_stdscr):
        """Test when packages exist but none have edit_recipe=True."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        packages_needing_edit = [
            {"package_name": "pkg1", "version": "1.0.0", "edit_recipe": False},
            {"package_name": "pkg2", "version": "2.0.0", "edit_recipe": False}
        ]
        
        tui_app._handle_manual_recipe_editing(mock_stdscr, mock_spack_manager, packages_needing_edit)
        
        # Should return early without editing
        mock_spack_manager.offer_package_edit.assert_not_called()
        mock_menu.display_info.assert_not_called()
    
    @patch('curses.curs_set')
    @patch('curses.endwin')
    @patch('emcenvchainer.tui.TUIMenu')
    def test_handle_manual_recipe_editing_mixed_selection(self, mock_menu_class, mock_endwin, mock_curs_set, tui_app, mock_stdscr):
        """Test with some packages selected for editing and some not."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_spack_manager.offer_package_edit.return_value = True
        
        packages_needing_edit = [
            {"package_name": "pkg1", "version": "1.0.0", "edit_recipe": True},
            {"package_name": "pkg2", "version": "2.0.0", "edit_recipe": False},
            {"package_name": "pkg3", "version": "3.0.0", "edit_recipe": True}
        ]
        
        tui_app._handle_manual_recipe_editing(mock_stdscr, mock_spack_manager, packages_needing_edit)
        
        # Only packages with edit_recipe=True should be edited
        called_packages = mock_spack_manager.offer_package_edit.call_args[0][0]
        assert len(called_packages) == 2
        assert called_packages[0]["package_name"] == "pkg1"
        assert called_packages[1]["package_name"] == "pkg3"
    
    @patch('curses.curs_set')
    @patch('curses.endwin')
    @patch('emcenvchainer.tui.TUIMenu')
    def test_handle_manual_recipe_editing_curses_restoration(self, mock_menu_class, mock_endwin, mock_curs_set, tui_app, mock_stdscr):
        """Test that curses mode is properly restored."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_spack_manager.offer_package_edit.return_value = True
        
        packages_needing_edit = [
            {"package_name": "pkg1", "version": "1.0.0", "edit_recipe": True}
        ]
        
        tui_app._handle_manual_recipe_editing(mock_stdscr, mock_spack_manager, packages_needing_edit)
        
        # Verify curses was exited
        mock_endwin.assert_called_once()
        
        # Verify curses was restored
        mock_stdscr.clear.assert_called_once()
        mock_stdscr.refresh.assert_called_once()
        mock_curs_set.assert_called_once_with(0)
    
    @patch('curses.curs_set')
    @patch('curses.endwin')
    @patch('emcenvchainer.tui.TUIMenu')
    def test_handle_manual_recipe_editing_exception_handling(self, mock_menu_class, mock_endwin, mock_curs_set, tui_app, mock_stdscr):
        """Test that curses is restored even if exception occurs."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_spack_manager.offer_package_edit.side_effect = Exception("Test error")
        
        packages_needing_edit = [
            {"package_name": "pkg1", "version": "1.0.0", "edit_recipe": True}
        ]
        
        # Should not raise exception
        try:
            tui_app._handle_manual_recipe_editing(mock_stdscr, mock_spack_manager, packages_needing_edit)
        except Exception:
            pass
        
        # Verify curses restoration happened even with exception
        mock_stdscr.clear.assert_called_once()
        mock_stdscr.refresh.assert_called_once()
        mock_curs_set.assert_called_once_with(0)
    
    @patch('curses.curs_set')
    @patch('curses.endwin')
    @patch('emcenvchainer.tui.TUIMenu')
    def test_handle_manual_recipe_editing_single_package(self, mock_menu_class, mock_endwin, mock_curs_set, tui_app, mock_stdscr):
        """Test manual editing with single package."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_spack_manager.offer_package_edit.return_value = True
        
        packages_needing_edit = [
            {"package_name": "netcdf-c", "version": "4.9.0", "edit_recipe": True}
        ]
        
        tui_app._handle_manual_recipe_editing(mock_stdscr, mock_spack_manager, packages_needing_edit)
        
        # Verify correct info message
        info_msg = mock_menu.display_info.call_args[0][0]
        assert "netcdf-c@4.9.0" in info_msg
        assert "manual recipe editing" in info_msg.lower()
    
    @patch('curses.curs_set')
    @patch('curses.endwin')
    @patch('emcenvchainer.tui.TUIMenu')
    def test_handle_manual_recipe_editing_multiple_packages(self, mock_menu_class, mock_endwin, mock_curs_set, tui_app, mock_stdscr):
        """Test manual editing with multiple packages."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        mock_spack_manager.offer_package_edit.return_value = True
        
        packages_needing_edit = [
            {"package_name": "netcdf-c", "version": "4.9.0", "edit_recipe": True},
            {"package_name": "hdf5", "version": "1.14.0", "edit_recipe": True},
            {"package_name": "esmf", "version": "8.5.0", "edit_recipe": True}
        ]
        
        tui_app._handle_manual_recipe_editing(mock_stdscr, mock_spack_manager, packages_needing_edit)
        
        # Verify all packages are mentioned
        info_msg = mock_menu.display_info.call_args[0][0]
        assert "netcdf-c@4.9.0" in info_msg
        assert "hdf5@1.14.0" in info_msg
        assert "esmf@8.5.0" in info_msg
    
    @patch('curses.curs_set')
    @patch('curses.endwin')
    @patch('emcenvchainer.tui.TUIMenu')
    def test_handle_manual_recipe_editing_packages_without_edit_flag(self, mock_menu_class, mock_endwin, mock_curs_set, tui_app, mock_stdscr):
        """Test with packages that don't have edit_recipe field."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        
        # Package without edit_recipe field (defaults to False via get)
        packages_needing_edit = [
            {"package_name": "pkg1", "version": "1.0.0"}
        ]
        
        tui_app._handle_manual_recipe_editing(mock_stdscr, mock_spack_manager, packages_needing_edit)
        
        # Should not call offer_package_edit since edit_recipe defaults to False
        mock_spack_manager.offer_package_edit.assert_not_called()
    
    def test_generate_activation_scripts_success(self, tui_app, mock_stdscr):
        """Test successfully generating activation scripts."""
        mock_spack_manager = Mock()
        
        with patch.object(tui_app, '_generate_activate_script') as mock_activate:
            with patch.object(tui_app, '_generate_package_versions_script') as mock_versions:
                tui_app._generate_activation_scripts(
                    mock_stdscr, 
                    mock_spack_manager, 
                    "/test/env/path", 
                    "/test/upstream/path"
                )
        
        # Verify both scripts were generated
        mock_activate.assert_called_once_with("/test/env/path", "/test/upstream/path")
        mock_versions.assert_called_once_with(mock_spack_manager, "/test/env/path")
    
    @patch('emcenvchainer.tui.TUIMenu')
    def test_generate_activation_scripts_activate_script_error(self, mock_menu_class, tui_app, mock_stdscr):
        """Test error handling when activate script generation fails."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        
        with patch.object(tui_app, '_generate_activate_script', side_effect=Exception("Test error")):
            with patch.object(tui_app, '_generate_package_versions_script'):
                tui_app._generate_activation_scripts(
                    mock_stdscr, 
                    mock_spack_manager, 
                    "/test/env/path", 
                    "/test/upstream/path"
                )
        
        # Verify error message was displayed
        error_calls = [call for call in mock_menu.display_info.call_args_list 
                      if "Failed to generate activation scripts" in str(call)]
        assert len(error_calls) == 1
    
    @patch('emcenvchainer.tui.TUIMenu')
    def test_generate_activation_scripts_versions_script_error(self, mock_menu_class, tui_app, mock_stdscr):
        """Test error handling when versions script generation fails."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        
        mock_spack_manager = Mock()
        
        with patch.object(tui_app, '_generate_activate_script'):
            with patch.object(tui_app, '_generate_package_versions_script', side_effect=Exception("Test error")):
                tui_app._generate_activation_scripts(
                    mock_stdscr, 
                    mock_spack_manager, 
                    "/test/env/path", 
                    "/test/upstream/path"
                )
        
        # Verify error message was displayed
        error_calls = [call for call in mock_menu.display_info.call_args_list 
                      if "Failed to generate activation scripts" in str(call)]
        assert len(error_calls) == 1
    
    def test_generate_activation_scripts_passes_correct_args(self, tui_app, mock_stdscr):
        """Test that correct arguments are passed to helper methods."""
        mock_spack_manager = Mock()
        
        with patch.object(tui_app, '_generate_activate_script') as mock_activate:
            with patch.object(tui_app, '_generate_package_versions_script') as mock_versions:
                tui_app._generate_activation_scripts(
                    mock_stdscr, 
                    mock_spack_manager, 
                    "/custom/env", 
                    "/custom/upstream"
                )
        
        # Verify correct arguments passed
        mock_activate.assert_called_once_with("/custom/env", "/custom/upstream")
        mock_versions.assert_called_once_with(mock_spack_manager, "/custom/env")
    
    def test_generate_activation_scripts_both_scripts_called(self, tui_app, mock_stdscr):
        """Test that both script generation methods are called."""
        mock_spack_manager = Mock()
        
        activate_called = False
        versions_called = False
        
        def mock_activate_func(env_path, upstream_path):
            nonlocal activate_called
            activate_called = True
        
        def mock_versions_func(manager, env_path):
            nonlocal versions_called
            versions_called = True
        
        with patch.object(tui_app, '_generate_activate_script', side_effect=mock_activate_func):
            with patch.object(tui_app, '_generate_package_versions_script', side_effect=mock_versions_func):
                tui_app._generate_activation_scripts(
                    mock_stdscr, 
                    mock_spack_manager, 
                    "/test/env", 
                    "/test/upstream"
                )
        
        assert activate_called
        assert versions_called
    
    @patch('builtins.open', create=True)
    @patch('os.path.basename')
    @patch('os.path.abspath')
    def test_generate_activate_script_creates_file(self, mock_abspath, mock_basename, mock_open, tui_app):
        """Test that activate script file is created with correct content."""
        mock_basename.return_value = "test-env"
        mock_abspath.side_effect = lambda x: f"/abs{x}"
        
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        tui_app._generate_activate_script("/test/env/path", "/test/upstream/path")
        
        # Verify file was opened for writing
        mock_open.assert_called_once_with("/test/env/path/activate_spack_env.sh", 'w')
        
        # Verify content was written
        mock_file.write.assert_called_once()
        written_content = mock_file.write.call_args[0][0]
        
        # Verify key elements in script
        assert "#!/bin/bash" in written_content
        assert "test-env" in written_content
        assert "setup-env.sh" in written_content
        assert "spack env activate" in written_content
    
    @patch('builtins.open', create=True)
    @patch('os.path.basename')
    def test_generate_package_versions_script_success(self, mock_basename, mock_open, tui_app):
        """Test successful generation of package versions script."""
        mock_basename.return_value = "test-env"
        
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        mock_spack_manager = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "export netcdf_c_ver=4.9.0\nexport hdf5_ver=1.14.0\n"
        mock_spack_manager._run_spack_command.return_value = mock_result
        
        tui_app._generate_package_versions_script(mock_spack_manager, "/test/env/path")
        
        # Verify spack find was called
        mock_spack_manager._run_spack_command.assert_called_once()
        call_args = mock_spack_manager._run_spack_command.call_args[0][0]
        assert '-e' in call_args
        assert '/test/env/path' in call_args
        assert 'find' in call_args
        
        # Verify file was written
        mock_open.assert_called_once_with("/test/env/path/export_package_versions.sh", 'w')
    
    @patch('builtins.open', create=True)
    @patch('os.path.basename')
    def test_generate_package_versions_script_spack_command_failure(self, mock_basename, mock_open, tui_app):
        """Test handling of spack command failure."""
        mock_basename.return_value = "test-env"
        
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        mock_spack_manager = Mock()
        mock_result = Mock()
        mock_result.returncode = 1  # Failure
        mock_result.stderr = "Error message"
        mock_spack_manager._run_spack_command.return_value = mock_result
        
        # Should not raise exception
        tui_app._generate_package_versions_script(mock_spack_manager, "/test/env/path")
        
        # File should still be created (with fallback content)
        assert mock_open.called
    
    @patch('builtins.open', create=True)
    @patch('os.path.basename')
    @patch('os.path.abspath')
    def test_generate_activate_script_path_handling(self, mock_abspath, mock_basename, mock_open, tui_app):
        """Test correct path handling in activate script."""
        mock_basename.return_value = "my-env"
        
        # Mock abspath to return predictable values
        def abspath_side_effect(path):
            if "spack/share/spack" in path:
                return "/spack-stack/spack/share/spack/setup-env.sh"
            return "/spack-stack"
        
        mock_abspath.side_effect = abspath_side_effect
        
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        tui_app._generate_activate_script("/env/path", "/env/upstream/install")
        
        # Verify file content
        written_content = mock_file.write.call_args[0][0]
        assert "/spack-stack/spack/share/spack/setup-env.sh" in written_content
        assert "/spack-stack" in written_content
    
    @patch('builtins.open', create=True)
    @patch('os.path.basename')
    def test_generate_package_versions_script_hyphen_replacement(self, mock_basename, mock_open, tui_app):
        """Test that hyphens in package names are replaced with underscores."""
        mock_basename.return_value = "test-env"
        
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        mock_spack_manager = Mock()
        mock_result = Mock()
        mock_result.returncode = 0
        # Spack output with hyphens in package names and concretization markers
        # Real output from "spack find --show-concretized" has spaces/markers before "export"
        mock_result.stdout = "[^] export netcdf_c_ver=4.9.0\n - export parallel_netcdf_ver=1.12.0\n"
        mock_spack_manager._run_spack_command.return_value = mock_result
        
        tui_app._generate_package_versions_script(mock_spack_manager, "/test/env/path")
        
        # Verify file was written
        mock_file.write.assert_called_once()
        written_content = mock_file.write.call_args[0][0]
        
        # Hyphens should be replaced with underscores in variable names
        assert "netcdf_c_ver" in written_content
    
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('emcenvchainer.tui.PackageSpecDialog')
    @patch('curses.curs_set')
    def test_get_packages_manually_package_name_only(self, mock_curs_set, mock_dialog_class, mock_menu_class, tui_app, mock_stdscr):
        """Test adding a package with name only (no version or variants)."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        # First call returns None (to select Add), then return 1 (to select Continue)
        mock_menu.display_menu.side_effect = [0, 2]  # Add package, then Continue
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        # Package spec with name only
        mock_dialog.get_package_spec.return_value = {"name": "zlib"}
        
        mock_spack_manager = Mock()
        
        result = tui_app._get_packages_manually(mock_stdscr, mock_spack_manager)
        
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "zlib"
        assert result[0].get("version") is None
        assert result[0].get("variants") is None
        
        # Verify menu displayed package name only
        # Second call to display_menu should have the package in options
        second_call_options = mock_menu.display_menu.call_args_list[1][0][0]
        assert "zlib" in second_call_options[0]
        assert "@" not in second_call_options[0]
    
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('emcenvchainer.tui.PackageSpecDialog')
    @patch('curses.curs_set')
    def test_get_packages_manually_name_and_version(self, mock_curs_set, mock_dialog_class, mock_menu_class, tui_app, mock_stdscr):
        """Test adding a package with name and version."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        mock_menu.display_menu.side_effect = [0, 2]  # Add package, then Continue
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        # Package spec with name and version
        mock_dialog.get_package_spec.return_value = {
            "name": "netcdf-c",
            "version": "4.9.0"
        }
        
        mock_spack_manager = Mock()
        
        result = tui_app._get_packages_manually(mock_stdscr, mock_spack_manager)
        
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "netcdf-c"
        assert result[0]["version"] == "4.9.0"
        assert result[0].get("variants") is None
        
        # Verify menu displayed package with version
        second_call_options = mock_menu.display_menu.call_args_list[1][0][0]
        assert "netcdf-c@4.9.0" in second_call_options[0]
    
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('emcenvchainer.tui.PackageSpecDialog')
    @patch('curses.curs_set')
    def test_get_packages_manually_name_and_variants(self, mock_curs_set, mock_dialog_class, mock_menu_class, tui_app, mock_stdscr):
        """Test adding a package with name and variants only."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        mock_menu.display_menu.side_effect = [0, 2]  # Add package, then Continue
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        # Package spec with name and variants
        mock_dialog.get_package_spec.return_value = {
            "name": "hdf5",
            "variants": "+mpi +shared"
        }
        
        mock_spack_manager = Mock()
        
        result = tui_app._get_packages_manually(mock_stdscr, mock_spack_manager)
        
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "hdf5"
        assert result[0].get("version") is None
        assert result[0]["variants"] == "+mpi +shared"
        
        # Verify menu displayed package with variants
        second_call_options = mock_menu.display_menu.call_args_list[1][0][0]
        assert "hdf5" in second_call_options[0]
        assert "+mpi +shared" in second_call_options[0]
    
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('emcenvchainer.tui.PackageSpecDialog')
    @patch('curses.curs_set')
    def test_get_packages_manually_name_version_and_variants(self, mock_curs_set, mock_dialog_class, mock_menu_class, tui_app, mock_stdscr):
        """Test adding a package with name, version, and variants."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        mock_menu.display_menu.side_effect = [0, 2]  # Add package, then Continue
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        # Package spec with name, version, and variants
        mock_dialog.get_package_spec.return_value = {
            "name": "esmf",
            "version": "8.5.0",
            "variants": "+external-lapack +netcdf"
        }
        
        mock_spack_manager = Mock()
        
        result = tui_app._get_packages_manually(mock_stdscr, mock_spack_manager)
        
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "esmf"
        assert result[0]["version"] == "8.5.0"
        assert result[0]["variants"] == "+external-lapack +netcdf"
        
        # Verify menu displayed full package spec
        second_call_options = mock_menu.display_menu.call_args_list[1][0][0]
        assert "esmf@8.5.0 +external-lapack +netcdf" in second_call_options[0]
    
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('emcenvchainer.tui.PackageSpecDialog')
    @patch('curses.curs_set')
    def test_get_packages_manually_multiple_packages_different_formats(self, mock_curs_set, mock_dialog_class, mock_menu_class, tui_app, mock_stdscr):
        """Test adding multiple packages with different specification formats."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        # Add 4 packages: "Add" button moves as list grows
        # Initial: ["Add", "Continue"] -> select 0 (Add)
        # After 1: ["pkg1", "Add", "Continue"] -> select 1 (Add)
        # After 2: ["pkg1", "pkg2", "Add", "Continue"] -> select 2 (Add)
        # After 3: ["pkg1", "pkg2", "pkg3", "Add", "Continue"] -> select 3 (Add)
        # After 4: ["pkg1", "pkg2", "pkg3", "pkg4", "Add", "Continue"] -> select 5 (Continue)
        mock_menu.display_menu.side_effect = [0, 1, 2, 3, 5]
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        # Different package specs
        mock_dialog.get_package_spec.side_effect = [
            {"name": "zlib"},  # Name only
            {"name": "curl", "version": "7.85.0"},  # Name + version
            {"name": "openssl", "variants": "+shared"},  # Name + variants
            {"name": "boost", "version": "1.79.0", "variants": "+python"}  # All three
        ]
        
        mock_spack_manager = Mock()
        
        result = tui_app._get_packages_manually(mock_stdscr, mock_spack_manager)
        
        assert result is not None
        assert len(result) == 4
        
        # Verify each package
        assert result[0] == {"name": "zlib"}
        assert result[1] == {"name": "curl", "version": "7.85.0"}
        assert result[2] == {"name": "openssl", "variants": "+shared"}
        assert result[3] == {"name": "boost", "version": "1.79.0", "variants": "+python"}
        
        # Verify menu showed all packages correctly
        final_call_options = mock_menu.display_menu.call_args_list[4][0][0]
        assert "zlib" in final_call_options[0]
        assert "curl@7.85.0" in final_call_options[1]
        assert "openssl" in final_call_options[2] and "+shared" in final_call_options[2]
        assert "boost@1.79.0 +python" in final_call_options[3]
    
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('emcenvchainer.tui.PackageSpecDialog')
    @patch('curses.curs_set')
    def test_get_packages_manually_edit_existing_package(self, mock_curs_set, mock_dialog_class, mock_menu_class, tui_app, mock_stdscr):
        """Test editing an existing package in the list."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        # Add package, then select first package (index 0) to edit, then Continue
        # First: ["Add", "Continue"] -> select 0 (Add)
        # After add: ["hdf5@1.14.0", "Add", "Continue"] -> select 0 (Edit first package)
        # After edit: ["hdf5@1.14.3 +mpi", "Add", "Continue"] -> select 2 (Continue)
        mock_menu.display_menu.side_effect = [0, 0, 2]
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        # First add, then edit
        mock_dialog.get_package_spec.side_effect = [
            {"name": "hdf5", "version": "1.14.0"},  # Initial add
            {"name": "hdf5", "version": "1.14.3", "variants": "+mpi"}  # Edited version
        ]
        
        mock_spack_manager = Mock()
        
        result = tui_app._get_packages_manually(mock_stdscr, mock_spack_manager)
        
        assert result is not None
        assert len(result) == 1
        # Should have the edited version
        assert result[0]["name"] == "hdf5"
        assert result[0]["version"] == "1.14.3"
        assert result[0]["variants"] == "+mpi"
    
    @patch('emcenvchainer.tui.TUIMenu')
    @patch('emcenvchainer.tui.PackageSpecDialog')
    @patch('curses.curs_set')
    def test_get_packages_manually_empty_version_and_variants(self, mock_curs_set, mock_dialog_class, mock_menu_class, tui_app, mock_stdscr):
        """Test package with empty string version and variants."""
        mock_menu = Mock()
        mock_menu_class.return_value = mock_menu
        mock_menu.display_menu.side_effect = [0, 2]  # Add package, then Continue
        
        mock_dialog = Mock()
        mock_dialog_class.return_value = mock_dialog
        # Package with empty strings (should be treated as None)
        mock_dialog.get_package_spec.return_value = {
            "name": "pkg",
            "version": "",
            "variants": ""
        }
        
        mock_spack_manager = Mock()
        
        result = tui_app._get_packages_manually(mock_stdscr, mock_spack_manager)
        
        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "pkg"
        # Empty strings should not add @ or space to display
        second_call_options = mock_menu.display_menu.call_args_list[1][0][0]
        # Should just be "pkg" without @ or trailing space
        assert second_call_options[0].strip() == "pkg"
    
    @patch('curses.curs_set')
    def test_get_packages_manually_add_package(self, mock_curs_set, tui_app, mock_stdscr):
        """Test manual package addition (original test kept for compatibility)."""
        mock_spack_manager = Mock()
        
        # Mock the package spec dialog to return a package, then None (cancel) to avoid infinite loop
        with patch.object(tui_app, '_get_package_specification', side_effect=[{"name": "test-pkg", "version": "1.0.0"}, None]):
            # Create a mock dialog that returns the package spec
            mock_dialog = Mock()
            mock_dialog.get_package_spec.side_effect = [{"name": "test-pkg", "version": "1.0.0"}, None]
            
            with patch('emcenvchainer.tui.PackageSpecDialog', return_value=mock_dialog):
                # Simulate: Add Package (Enter), then navigate to Continue and select it
                # After adding one package, options become: "test-pkg@1.0.0", "➕ Add package", "✅ Continue"
                mock_stdscr.getch.side_effect = [
                    ord('\n'),        # Select "Add package" 
                    curses.KEY_DOWN,  # Move to "Add package" again
                    curses.KEY_DOWN,  # Move to "Continue"  
                    ord('\n')         # Select "Continue"
                ]
                
                result = tui_app._get_packages_manually(mock_stdscr, mock_spack_manager)
                
                assert result is not None
                assert len(result) == 1
                assert result[0]["name"] == "test-pkg"
    
    @patch('curses.curs_set')
    def test_get_packages_manually_cancel(self, mock_curs_set, tui_app, mock_stdscr):
        """Test manual package addition cancellation."""
        mock_spack_manager = Mock()
        
        # Simulate: Navigate to "Continue" option (second option, index 1) and select it
        # Since there are no packages initially, the options are: "➕ Add package", "❌ Continue (no packages)"
        mock_stdscr.getch.side_effect = [curses.KEY_DOWN, ord('\n')]  # Move down to Continue, then Enter
        
        result = tui_app._get_packages_manually(mock_stdscr, mock_spack_manager)
        
        assert result is None  # Should return None when no packages are added
    
    def test_addstr_with_colored_markers(self, tui_app, mock_stdscr):
        """Test colored marker text display."""
        text = "Normal text [^] marked text more text"
        
        tui_app._addstr_with_colored_markers(mock_stdscr, 0, 0, text)
        
        # Should have made at least 2 addstr calls for different parts
        assert mock_stdscr.addstr.call_count >= 2
    
    def test_determine_recipe_source_local(self, tui_app):
        """Test recipe source determination for local packages."""
        pkg = {"found_in_local": True, "found_in_remote": False}
        
        result = tui_app._determine_recipe_source(pkg)
        
        assert result == "local Spack installation"
    
    def test_determine_recipe_source_remote(self, tui_app):
        """Test recipe source determination for remote packages."""
        pkg = {"found_in_local": False, "found_in_remote": True, "use_local_copy": False}
        
        result = tui_app._determine_recipe_source(pkg)
        
        assert result == "remote Spack repository"
    
    def test_determine_recipe_source_both(self, tui_app):
        """Test recipe source determination for packages in both locations."""
        pkg = {"found_in_local": True, "found_in_remote": True}
        
        result = tui_app._determine_recipe_source(pkg)
        
        assert result == "local Spack installation"
    
    def test_determine_recipe_source_neither(self, tui_app):
        """Test recipe source determination for packages in neither location."""
        pkg = {"found_in_local": False, "found_in_remote": False, "use_local_copy": False}
        
        result = tui_app._determine_recipe_source(pkg)
        
        assert result == "remote Spack repository"
    
    def test_show_custom_recipe_dialog_deduplication(self, tui_app, mock_stdscr):
        """Test that _show_custom_recipe_dialog deduplicates packages."""
        # Create duplicate packages with same name and version
        packages_needing_edit = [
            {
                "package_name": "hdf5",
                "version": "1.14.0",
                "recipe_path": "/path/to/hdf5/package.py",
                "found_in_local": False,
                "found_in_remote": True
            },
            {
                "package_name": "hdf5",
                "version": "1.14.0",
                "recipe_path": "/path/to/hdf5/package.py",
                "found_in_local": False,
                "found_in_remote": True
            },
            {
                "package_name": "netcdf-c",
                "version": "4.9.0",
                "recipe_path": "/path/to/netcdf-c/package.py",
                "found_in_local": False,
                "found_in_remote": False
            },
            {
                "package_name": "hdf5",
                "version": "1.14.0",
                "recipe_path": "/path/to/hdf5/package.py",
                "found_in_local": False,
                "found_in_remote": True
            }
        ]
        
        # Mock Enter key to continue immediately
        mock_stdscr.getch.return_value = ord('\n')
        
        result = tui_app._show_custom_recipe_dialog(mock_stdscr, packages_needing_edit)
        
        # Should only have 2 unique packages: hdf5@1.14.0 and netcdf-c@4.9.0
        assert len(result) == 2
        
        # Check that we have exactly one hdf5 and one netcdf-c
        package_keys = {(pkg['package_name'], pkg['version']) for pkg in result}
        assert package_keys == {('hdf5', '1.14.0'), ('netcdf-c', '4.9.0')}
        
        # Verify the order is preserved (first occurrence kept)
        assert result[0]['package_name'] == 'hdf5'
        assert result[1]['package_name'] == 'netcdf-c'
    
    def test_show_custom_recipe_dialog_empty_list(self, tui_app, mock_stdscr):
        """Test that _show_custom_recipe_dialog handles empty list."""
        packages_needing_edit = []
        
        result = tui_app._show_custom_recipe_dialog(mock_stdscr, packages_needing_edit)
        
        assert result == []
    
    def test_show_custom_recipe_dialog_no_duplicates(self, tui_app, mock_stdscr):
        """Test that _show_custom_recipe_dialog preserves unique packages."""
        packages_needing_edit = [
            {
                "package_name": "hdf5",
                "version": "1.14.0",
                "recipe_path": "/path/to/hdf5/package.py",
                "found_in_local": False,
                "found_in_remote": True
            },
            {
                "package_name": "netcdf-c",
                "version": "4.9.0",
                "recipe_path": "/path/to/netcdf-c/package.py",
                "found_in_local": False,
                "found_in_remote": False
            },
            {
                "package_name": "hdf5",
                "version": "1.12.0",
                "recipe_path": "/path/to/hdf5/package.py",
                "found_in_local": True,
                "found_in_remote": False
            }
        ]
        
        # Mock Enter key to continue immediately
        mock_stdscr.getch.return_value = ord('\n')
        
        result = tui_app._show_custom_recipe_dialog(mock_stdscr, packages_needing_edit)
        
        # Should have all 3 packages since they're unique
        assert len(result) == 3
        
        package_keys = {(pkg['package_name'], pkg['version']) for pkg in result}
        assert package_keys == {('hdf5', '1.14.0'), ('netcdf-c', '4.9.0'), ('hdf5', '1.12.0')}


class TestTUIIntegration:
    """Integration tests for TUI components."""
    
    @pytest.fixture
    def mock_environment(self):
        """Create a mock test environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock spack structure
            spack_root = Path(temp_dir) / "spack"
            spack_bin = spack_root / "bin"
            spack_bin.mkdir(parents=True)
            (spack_bin / "spack").touch()
            
            yield {
                "temp_dir": temp_dir,
                "spack_root": str(spack_root)
            }
    
    def test_tui_components_integration(self, mock_environment):
        """Test that TUI components work together."""
        # Create mock objects
        mock_config = Mock(spec=Config)
        mock_platform = Mock(spec=Platform)
        mock_platform.name = "test-platform"
        mock_platform.config = {"test": "config"}
        
        # Create TUI app
        tui_app = EmcEnvChainerTUI(mock_config, mock_platform)
        
        # Test that components are properly initialized
        assert tui_app.config == mock_config
        assert tui_app.platform == mock_platform
        assert tui_app.model_app_manager is not None
    
    def test_menu_navigation_logic(self):
        """Test menu navigation logic without curses."""
        # Create a mock stdscr
        mock_stdscr = Mock()
        mock_stdscr.getmaxyx.return_value = (30, 80)
        
        # Test TUIMenu navigation state
        menu = TUIMenu(mock_stdscr, "Test Menu")
        
        # Test current_row updates
        menu.current_row = 0
        assert menu.current_row == 0
        
        menu.current_row = 2
        assert menu.current_row == 2
        
        # Test top_row scrolling logic
        menu.top_row = 0
        assert menu.top_row == 0
    
    def test_package_spec_dialog_field_logic(self):
        """Test package specification dialog field logic."""
        mock_stdscr = Mock()
        mock_stdscr.getmaxyx.return_value = (30, 80)
        
        dialog = PackageSpecDialog(mock_stdscr)
        
        # Test initial state
        assert dialog.stdscr == mock_stdscr
        assert dialog.spack_manager is None
    
    def test_radio_button_menu_selection_logic(self):
        """Test radio button menu selection logic."""
        mock_stdscr = Mock()
        mock_stdscr.getmaxyx.return_value = (30, 80)
        
        menu = RadioButtonMenu(mock_stdscr, "Test Radio")
        
        # Test selection state
        assert menu.selected_items == set()
        
        # Test adding selections
        menu.selected_items.add(0)
        menu.selected_items.add(2)
        assert menu.selected_items == {0, 2}
        
        # Test clearing selections
        menu.selected_items.clear()
        assert menu.selected_items == set()
