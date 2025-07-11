"""Unit tests for TUI classes and methods."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
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
    
    def test_validate_and_add_version_not_exists(self, package_dialog, mock_spack_manager, mock_stdscr):
        """Test version validation when version doesn't exist."""
        mock_spack_manager.check_package_version_exists.return_value = False
        mock_spack_manager.check_version_in_remote_repo.return_value = True
        mock_spack_manager.add_pending_recipe = Mock()
        
        with patch.object(package_dialog, '_add_version_to_custom_repo', return_value=True):
            result = package_dialog._validate_and_add_version("test-pkg", "1.0.0")
            
            assert result is True
    
    def test_show_error(self, package_dialog, mock_stdscr):
        """Test error message display."""
        package_dialog._show_error("Test error message")
        
        assert mock_stdscr.addstr.called
        assert mock_stdscr.refresh.called


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
    
    def test_select_installation_default(self, tui_app, mock_stdscr):
        """Test installation selection with default option."""
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
    
    def test_get_spack_config_jcsda_stack(self, tui_app):
        """Test getting Spack config for JCSDA stack."""
        installation = {"type": "jcsda-spack-stack", "path": "/path/to/stack", "install_path": "/path/to/install"}
        
        spack_root, upstream_path = tui_app._get_spack_config(installation)
        
        # The method calls platform.get_spack_root() which we mocked to return "/test/stack/spack"
        assert spack_root == "/test/stack/spack"
        assert upstream_path == "/path/to/install"
    
    def test_get_spack_config_custom(self, tui_app):
        """Test getting Spack config for custom installation."""
        installation = {"type": "custom", "spack_root": "/custom/spack", "branch": "custom-branch", "install_path": "/custom/install"}
        
        spack_root, upstream_path = tui_app._get_spack_config(installation)
        
        # For non-model-application types, it uses platform.get_spack_root()
        assert spack_root == "/test/stack/spack"
        assert upstream_path == "/custom/install"
    
    @patch('curses.curs_set')
    def test_get_packages_manually_add_package(self, mock_curs_set, tui_app, mock_stdscr):
        """Test manual package addition."""
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
