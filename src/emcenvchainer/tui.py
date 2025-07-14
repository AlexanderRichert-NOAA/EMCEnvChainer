"""Terminal User Interface for emcenvchainer."""

import curses
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

from .config import Config
from .platform import Platform
from .model_apps import ModelApplicationManager
from .spack_manager import SpackManager


class TUIMenu:
    """Base class for TUI menus."""
    
    def __init__(self, stdscr, title: str):
        """Initialize menu.
        
        Args:
            stdscr: Curses screen object
            title: Menu title
        """
        self.stdscr = stdscr
        self.title = title
        self.current_row = 0
        self.top_row = 0
    
    def display_menu(self, options: List[str], selected_row: int = 0) -> Optional[int]:
        """Display menu and handle selection.
        
        Args:
            options: List of menu options
            selected_row: Initially selected row
            
        Returns:
            Selected option index, None if cancelled
        """
        self.current_row = selected_row
        
        while True:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()
            
            # Display title
            title_x = (width - len(self.title)) // 2
            self.stdscr.addstr(1, title_x, self.title, curses.A_BOLD)
            
            # Calculate display window
            max_display = height - 6
            if self.current_row >= self.top_row + max_display:
                self.top_row = self.current_row - max_display + 1
            elif self.current_row < self.top_row:
                self.top_row = self.current_row
            
            # Display options
            for idx, option in enumerate(options[self.top_row:self.top_row + max_display]):
                row_idx = self.top_row + idx
                y = 4 + idx
                
                if row_idx == self.current_row:
                    self.stdscr.addstr(y, 2, f"> {option}", curses.A_REVERSE)
                else:
                    self.stdscr.addstr(y, 4, option)
            
            # Display instructions
            instructions = "Use ↑/↓ to navigate, Enter to select, Ctrl+C to quit"
            self.stdscr.addstr(height - 2, 2, instructions)
            
            # Show scroll indicators
            if self.top_row > 0:
                self.stdscr.addstr(3, width - 3, "↑")
            if self.top_row + max_display < len(options):
                self.stdscr.addstr(height - 3, width - 3, "↓")
            
            self.stdscr.refresh()
            
            # Handle input
            key = self.stdscr.getch()
            
            if key == curses.KEY_UP and self.current_row > 0:
                self.current_row -= 1
            elif key == curses.KEY_DOWN and self.current_row < len(options) - 1:
                self.current_row += 1
            elif key in [curses.KEY_ENTER, ord('\n'), ord('\r')]:
                return self.current_row
            elif key in [27]:  # Escape
                return None
    
    def display_info(self, message: str, wait_for_key: bool = True):
        """Display an information message.
        
        Args:
            message: Message to display
            wait_for_key: Whether to wait for keypress
        """
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()
        
        # Split message into lines
        lines = message.split('\n')
        start_y = (height - len(lines)) // 2
        
        for i, line in enumerate(lines):
            x = (width - len(line)) // 2
            self.stdscr.addstr(start_y + i, x, line)
        
        if wait_for_key:
            self.stdscr.addstr(height - 2, 2, "Press any key to continue...")
            self.stdscr.refresh()
            self.stdscr.getch()
        else:
            self.stdscr.refresh()


class PackageSpecDialog:
    """Dialog for specifying package details."""
    
    def __init__(self, stdscr, spack_manager=None):
        """Initialize dialog.
        
        Args:
            stdscr: Curses screen object
            spack_manager: Optional SpackManager for version validation
        """
        self.stdscr = stdscr
        self.spack_manager = spack_manager
    
    def get_package_spec(self, package_name: str = "", default_version: str = "") -> Optional[Dict]:
        """Get package specification from user with inline editing.
        
        Args:
            package_name: Default package name
            default_version: Default version
            
        Returns:
            Package specification dict, None if cancelled
        """
        fields = {
            "name": package_name,
            "version": default_version,
            "variants": ""
        }
        
        # Track if validation has been performed for this dialog session
        validation_performed = False
        # Track the last validated package spec to detect changes
        last_validated_spec = None
        
        field_names = ["Package Name", "Version", "Variants"]
        field_keys = list(fields.keys())
        current_field = 0
        
        # Track cursor position for each field (only for actual text fields)
        cursors = [len(fields[k]) for k in fields.keys()] + [0]  # Add 0 for continue button
        scrolls = [0 for _ in field_keys]
        
        while True:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()
            
            # Title
            title = "Package Specification"
            title_x = (width - len(title)) // 2
            self.stdscr.addstr(2, title_x, title, curses.A_BOLD)
            
            # Display fields with inline editing
            final_cursor_y = 0
            final_cursor_x = 0
            for i, (field_key, field_label) in enumerate(zip(field_keys, field_names)):
                y = 5 + i * 2
                
                # Handle continue button as a simple selectable item
                if field_key == "continue":
                    # Just show the button without separate label and input box
                    if i == current_field:
                        self.stdscr.addstr(y, 4, f"> {field_label}", curses.A_REVERSE)
                        final_cursor_y = y
                        final_cursor_x = 6
                    else:
                        self.stdscr.addstr(y, 4, f"  {field_label}")
                else:
                    # Regular text field with label and input box
                    self.stdscr.addstr(y, 4, f"{field_label}:")
                    
                    # Input box
                    box_y = y + 1
                    box_x = 6
                    box_width = width - 12
                    
                    if i == current_field:
                        self.stdscr.addstr(box_y, box_x, ">" + "─" * (box_width - 2) + "<", curses.A_REVERSE)
                    else:
                        self.stdscr.addstr(box_y, box_x, " " + "─" * (box_width - 2) + " ")
                    
                    # Regular text field with horizontal scrolling
                    value = fields[field_key]
                    cursor_pos = cursors[i]
                    scroll_offset = scrolls[i]
                    input_width = box_width - 2
                    
                    # Adjust scroll to keep cursor visible
                    if cursor_pos < scroll_offset:
                        scroll_offset = cursor_pos
                    elif cursor_pos > scroll_offset + input_width - 1:
                        scroll_offset = cursor_pos - input_width + 1
                    scrolls[i] = scroll_offset
                    
                    # Display visible portion
                    visible_value = value[scroll_offset:scroll_offset + input_width]
                    self.stdscr.addstr(box_y, box_x + 1, visible_value.ljust(input_width))
                    
                    # Position cursor for current field
                    if i == current_field:
                        display_cursor = cursor_pos - scroll_offset
                        final_cursor_y = box_y
                        final_cursor_x = box_x + 1 + display_cursor
            
            # Position cursor and make it visible
            curses.curs_set(1)  # Show cursor
            self.stdscr.move(final_cursor_y, final_cursor_x)
            
            # Instructions
            instructions = [
                "Use ↑/↓ or Tab to navigate fields, type to edit, ←/→ to move cursor",
                "Backspace/Delete/Home/End supported. Press Enter to continue."
            ]
            for i, instruction in enumerate(instructions):
                self.stdscr.addstr(height - 4 + i, 2, instruction)
            
            self.stdscr.refresh()
            
            # Handle input
            key = self.stdscr.getch()
            
            if key == curses.KEY_UP and current_field > 0:
                current_field -= 1
            elif key == curses.KEY_DOWN and current_field < len(field_keys) - 1:
                current_field += 1
            elif key == ord('\t'):
                current_field = (current_field + 1) % len(field_keys)
            elif key in [curses.KEY_ENTER, ord('\n'), ord('\r')]:
                if not fields["name"].strip():
                    self._show_error("Package name is required!")
                    continue
                
                package_name = fields["name"].strip()
                assert package_name, "Package name cannot be empty"
                version = fields["version"].strip()
                current_spec = f"{package_name}@{version}"
                
                # Check if the package spec has changed since last validation
                if validation_performed and current_spec != last_validated_spec:
                    # Package spec has changed, reset validation flag
                    validation_performed = False
                    last_validated_spec = None
                
                # Check if validation has already been performed for this dialog session
                if validation_performed:
                    # Validation already done, proceed without validation screen
                    curses.curs_set(0)  # Hide cursor
                    return fields
                
                # First check if version exists locally
                if self.spack_manager.check_package_version_exists(package_name, version) or not version:
                    # Version exists or isn't set; proceed without validation screen
                    curses.curs_set(0)  # Hide cursor
                    return fields
                else:
                    # Version doesn't exist, show validation screen
                    if not self._validate_and_add_version(package_name, version):
                        continue  # Stay in dialog if validation failed
                    else:
                        # Version validation succeeded, mark as validated
                        validation_performed = True
                        last_validated_spec = current_spec
                        curses.curs_set(0)  # Hide cursor
                        return fields
                
                curses.curs_set(0)  # Hide cursor
                return fields
            elif key == curses.KEY_LEFT:
                # Move cursor left in current field (only for text fields)
                if field_keys[current_field] != "continue" and cursors[current_field] > 0:
                    cursors[current_field] -= 1
            elif key == curses.KEY_RIGHT:
                # Move cursor right in current field (only for text fields)
                if field_keys[current_field] != "continue" and cursors[current_field] < len(fields[field_keys[current_field]]):
                    cursors[current_field] += 1
            elif key == curses.KEY_HOME or key == 1:  # Ctrl+A
                # Move to beginning of field (only for text fields)
                if field_keys[current_field] != "continue":
                    cursors[current_field] = 0
            elif key == curses.KEY_END or key == 5:  # Ctrl+E
                # Move to end of field (only for text fields)
                if field_keys[current_field] != "continue":
                    cursors[current_field] = len(fields[field_keys[current_field]])
            elif key in [curses.KEY_BACKSPACE, 127, 8]:  # Backspace
                # Only for text fields
                if field_keys[current_field] != "continue":
                    pos = cursors[current_field]
                    if pos > 0:
                        field_value = fields[field_keys[current_field]]
                        fields[field_keys[current_field]] = field_value[:pos-1] + field_value[pos:]
                        cursors[current_field] -= 1
            elif key == curses.KEY_DC:  # Delete
                # Only for text fields
                if field_keys[current_field] != "continue":
                    pos = cursors[current_field]
                    field_value = fields[field_keys[current_field]]
                    if pos < len(field_value):
                        fields[field_keys[current_field]] = field_value[:pos] + field_value[pos+1:]
            elif key == 24:  # Ctrl+X - Clear field
                # Only for text fields
                if field_keys[current_field] != "continue":
                    fields[field_keys[current_field]] = ""
                    cursors[current_field] = 0
                
                curses.curs_set(0)  # Hide cursor
                return fields
            elif 32 <= key <= 126:  # Printable characters
                # Insert character at cursor position (only for text fields)
                if field_keys[current_field] != "continue":
                    field_value = fields[field_keys[current_field]]
                    pos = cursors[current_field]
                    fields[field_keys[current_field]] = field_value[:pos] + chr(key) + field_value[pos:]
                    cursors[current_field] += 1
            elif key == 27:  # Escape - Cancel
                curses.curs_set(0)  # Hide cursor
                return None
    
    def _validate_and_add_version(self, package_name: str, version: str) -> bool:
        """Validate package version and offer to add if missing.
        
        Args:
            package_name: Name of the package
            version: Requested version
            
        Returns:
            True if validation successful, False if should stay in dialog
        """
        try:
            # This method is only called when the version doesn't exist locally
            # Show information to user about the missing version
            height, width = self.stdscr.getmaxyx()
            self.stdscr.clear()
            
            title = f"Version {version} not found for {package_name}"
            title_x = (width - len(title)) // 2
            self.stdscr.addstr(2, title_x, title, curses.A_BOLD)
            
            # Get the repository URL that will be checked
            base_url = self.spack_manager.config.get("spack_repository", {}).get("base_url", "")
            
            # Get the local package.py path
            local_package_path = self.spack_manager.get_local_package_path(package_name)
            
            info_lines = [
                f"Version {version} is not available in the local Spack installation ({local_package_path})",
                f"► Checking remote Spack repository: {base_url}",
                "  Please wait...",
            ]
            
            for i, line in enumerate(info_lines):
                self.stdscr.addstr(4 + i, 4, line)
            
            self.stdscr.refresh()
            
            # Check if version exists in remote repository
            remote_exists = self.spack_manager.check_version_in_remote_repo(package_name, version)
            
            # Reconstruct the URL that was checked for display
            repo_config = self.spack_manager.config.get("spack_repository", {})
            base_url_parts = base_url.replace("https://github.com/", "").replace(".git", "").split("/")
            git_org = base_url_parts[0]
            git_repo = base_url_parts[1]
            git_branch = repo_config.get("branch", "develop")
            package_url = f"https://raw.githubusercontent.com/{git_org}/{git_repo}/refs/heads/{git_branch}/var/spack/repos/builtin/packages/{package_name}/package.py"
            
            # Clear screen and redraw everything to handle any stray output
            self.stdscr.clear()
            self.stdscr.addstr(2, title_x, title, curses.A_BOLD)
            self.stdscr.addstr(4, 4, f"Version {version} is not available in the current Spack installation ({local_package_path}).")
            self.stdscr.addstr(5, 4, "")
            
            if not remote_exists:
                # Version not found in remote repo either
                self.stdscr.addstr(6, 4, f"✗ Version {version} not found in remote recipe: {package_url}")
                self.stdscr.addstr(8, 4, "This version may not exist or may require manual recipe creation.")
                self.stdscr.addstr(10, 4, "(p) Choose different version")
                self.stdscr.addstr(11, 4, "(a) Attempt to automatically add version with Spack")
                self.stdscr.addstr(12, 4, "(g) Add version by Git commit")
                self.stdscr.addstr(13, 4, "(c) Continue (add version to recipe manually)")
                self.stdscr.refresh()
                
                while True:
                    key = self.stdscr.getch()
                    if key in [ord('p'), ord('P')]:
                        return False  # Go back to edit version
                    elif key in [ord('a'), ord('A')]:
                        return self._add_version_with_checksum(package_name, version)
                    elif key in [ord('g'), ord('G')]:
                        return self._add_version_with_git_commit(package_name, version)
                    elif key in [ord('c'), ord('C')]:
                        # Add version for manual editing - we already know remote_exists is False
                        try:
                            self.spack_manager.add_pending_recipe(
                                package_name, version, recipe_content=None, 
                                needs_manual_edit=True, use_local_copy=True,
                                found_in_local=False, found_in_remote=False
                            )
                            return True
                        except Exception as e:
                            self._show_error(f"Error marking for manual editing: {e}")
                            return False
            else:
                # Version found in remote repo - automatically add to custom repo
                try:
                    self.spack_manager.add_pending_recipe(
                        package_name, version, recipe_content=None,
                        needs_manual_edit=False, use_local_copy=False,
                        found_in_local=False, found_in_remote=True
                    )
                    return True
                except Exception as e:
                    self._show_error(f"Error adding version from remote: {e}")
                    return False
                        
        except Exception as e:
            self._show_error(f"Error validating version: {e}")
            return False
    
    
    def _add_version_with_git_commit(self, package_name: str, version: str) -> bool:
        """Add version with Git commit hash.
        
        Args:
            package_name: Name of the package
            version: Version to add
            
        Returns:
            True if successful, False otherwise
        """
        try:
            height, width = self.stdscr.getmaxyx()
            self.stdscr.clear()
            
            title = f"Add Git commit version for {package_name}@{version}"
            title_x = (width - len(title)) // 2
            self.stdscr.addstr(2, title_x, title, curses.A_BOLD)
            
            # Instructions
            instructions = [
                f"Enter the Git commit hash for {package_name} requested version {version}:",
                "",
                "The commit hash will be added to the {package_name} recipe as:",
                f'version("{version}", commit="<your-commit-hash>")',
                "",
                "Commit hash: "
            ]
            
            for i, line in enumerate(instructions):
                self.stdscr.addstr(4 + i, 4, line)
            
            # Input field for commit hash
            input_y = 4 + len(instructions)
            input_x = 4
            input_width = width - 12
            
            # Text input handling
            commit_hash = ""
            cursor_pos = 0
            scroll_offset = 0
            
            # Enable cursor
            curses.curs_set(1)
            
            while True:
                # Handle horizontal scrolling
                if cursor_pos < scroll_offset:
                    scroll_offset = cursor_pos
                elif cursor_pos >= scroll_offset + input_width:
                    scroll_offset = cursor_pos - input_width + 1
                
                # Display input field
                self.stdscr.move(input_y, input_x)
                self.stdscr.clrtoeol()
                
                # Show input box
                visible_text = commit_hash[scroll_offset:scroll_offset + input_width]
                self.stdscr.addstr(input_y, input_x, f"[{visible_text.ljust(input_width)}]")
                
                # Position cursor
                display_cursor_pos = cursor_pos - scroll_offset
                self.stdscr.move(input_y, input_x + 1 + display_cursor_pos)
                
                # Show scroll indicators if needed
                if scroll_offset > 0:
                    self.stdscr.addstr(input_y, input_x - 1, "←", curses.A_BOLD)
                if scroll_offset + input_width < len(commit_hash):
                    self.stdscr.addstr(input_y, input_x + input_width + 2, "→", curses.A_BOLD)
                
                # Instructions at bottom
                self.stdscr.addstr(height - 4, 4, "Enter: Continue with commit hash")
                self.stdscr.addstr(height - 3, 4, "Ctrl+X: Clear input")
                self.stdscr.addstr(height - 2, 4, "Esc: Cancel")
                
                self.stdscr.refresh()
                
                # Get input
                key = self.stdscr.getch()
                
                if key == ord('\n') or key == ord('\r'):  # Enter
                    curses.curs_set(0)  # Hide cursor
                    
                    if not commit_hash.strip():
                        self._show_error("Commit hash cannot be empty!")
                        continue
                    
                    # Validate commit hash format (basic check)
                    commit_hash_clean = commit_hash.strip()
                    if len(commit_hash_clean) < 7:
                        self._show_error("Commit hash seems too short (should be at least 7 characters)!")
                        continue
                    
                    # Add to pending recipes with Git commit info
                    self.spack_manager.add_pending_git_commit(package_name, version, commit_hash_clean)

                    # Also add to pending recipes for manual editing
                    self.spack_manager.add_pending_recipe(
                        package_name=package_name,
                        version=version,
                        recipe_content=None,  # Will be populated after Git commit operation
                        needs_manual_edit=True,
                        use_local_copy=True,  # Copy from local repo after Git commit version is added
                        found_in_local=True,
                        found_in_remote=False
                    )
                    
                    # Show success message
                    self.stdscr.clear()
                    self.stdscr.addstr(2, title_x, title, curses.A_BOLD)
                    self.stdscr.addstr(4, 4, f"✓ Git commit-based version added for {package_name}@{version}")
                    self.stdscr.addstr(5, 4, f"Commit hash: {commit_hash_clean}")
                    self.stdscr.addstr(7, 4, "The version will be added to the recipe as:")
                    self.stdscr.addstr(8, 4, f'version("{version}", commit="{commit_hash_clean}")')
                    self.stdscr.addstr(10, 4, "Press any key to continue...")
                    self.stdscr.refresh()
                    self.stdscr.getch()
                    
                    return True
                    
                elif key == 27:  # Escape
                    curses.curs_set(0)  # Hide cursor
                    return False
                    
                elif key == curses.KEY_BACKSPACE or key == 8 or key == 127:
                    if cursor_pos > 0:
                        commit_hash = commit_hash[:cursor_pos-1] + commit_hash[cursor_pos:]
                        cursor_pos -= 1
                        
                elif key == curses.KEY_DC:  # Delete
                    if cursor_pos < len(commit_hash):
                        commit_hash = commit_hash[:cursor_pos] + commit_hash[cursor_pos+1:]
                        
                elif key == curses.KEY_LEFT:
                    if cursor_pos > 0:
                        cursor_pos -= 1
                        
                elif key == curses.KEY_RIGHT:
                    if cursor_pos < len(commit_hash):
                        cursor_pos += 1
                        
                elif key == curses.KEY_HOME:
                    cursor_pos = 0
                    
                elif key == curses.KEY_END:
                    cursor_pos = len(commit_hash)
                    
                elif key == 24:  # Ctrl+X
                    commit_hash = ""
                    cursor_pos = 0
                    
                elif 32 <= key <= 126:  # Printable characters
                    commit_hash = commit_hash[:cursor_pos] + chr(key) + commit_hash[cursor_pos:]
                    cursor_pos += 1
                    
        except Exception as e:
            self._show_error(f"Error adding Git commit version: {e}")
            return False

    def _add_version_with_checksum(self, package_name: str, version: str) -> bool:
        """Add version with automatic checksum via Spack.
        
        Args:
            package_name: Name of the package
            version: Version to add
            
        Returns:
            True if successful, False otherwise
        """
        try:
            height, width = self.stdscr.getmaxyx()
            self.stdscr.clear()
            
            title = f"Auto-add checksum for {package_name}@{version}"
            title_x = (width - len(title)) // 2
            self.stdscr.addstr(2, title_x, title, curses.A_BOLD)
            
            self.stdscr.addstr(4, 4, f"Spack will attempt to automatically add version {version}")
            self.stdscr.addstr(5, 4, f"for package {package_name} using 'spack checksum'.")
            
            # Queue the checksum operation
            self.spack_manager.add_pending_checksum(package_name, version)
                    
            # Add to pending recipes with needs_manual_edit=True to ensure it's offered for editing
            self.spack_manager.add_pending_recipe(
                package_name=package_name,
                version=version,
                recipe_content=None,  # Will be populated after checksum operation
                needs_manual_edit=True,
                use_local_copy=True,  # Copy from local repo after checksum
                found_in_local=True,
                found_in_remote=False,
            )

            self.stdscr.addstr(7, 4, f"✓ {package_name}@{version} queued for 'spack checksum'")
            self.stdscr.addstr(9, 4, "Press any key to continue...")
            self.stdscr.refresh()
            self.stdscr.getch()
            
            return True
            
        except Exception as e:
            self._show_error(f"Error queuing checksum operation: {e}")
            return False

    def _add_version_to_custom_repo(self, package_name: str, version: str) -> bool:
        """Add version to custom repository automatically.
        
        Args:
            package_name: Name of the package
            version: Version to add
            
        Returns:
            True if successful, False otherwise
        """
        try:
            height, width = self.stdscr.getmaxyx()
            self.stdscr.clear()
            
            title = f"Adding version {version} for {package_name}"
            title_x = (width - len(title)) // 2
            self.stdscr.addstr(2, title_x, title, curses.A_BOLD)
            
            # Show progress steps
            steps = [
                "Creating custom repository and adding version...",
                "Fetching recipe from remote repository...",
                "Processing package files...",
                "Adding to environment repository..."
            ]
            
            current_step = 0
            for i, step in enumerate(steps):
                if i == current_step:
                    self.stdscr.addstr(5 + i, 4, f"► {step}")
                else:
                    self.stdscr.addstr(5 + i, 4, f"  {step}")
            self.stdscr.refresh()
            
            # Fetch the recipe content from remote repository
            current_step = 1
            self.stdscr.addstr(5, 4, "✓ Creating custom repository and adding version...")
            self.stdscr.addstr(6, 4, "► Fetching recipe from remote repository...")
            
            # Reconstruct the URL for display
            repo_config = self.spack_manager.config.get("spack_repository", {})
            base_url = repo_config.get("base_url", "https://github.com/JCSDA/spack.git")
            base_url_parts = base_url.replace("https://github.com/", "").replace(".git", "").split("/")
            git_org = base_url_parts[0]
            git_repo = base_url_parts[1]
            git_branch = repo_config.get("branch", "develop")
            package_url = f"https://raw.githubusercontent.com/{git_org}/{git_repo}/refs/heads/{git_branch}/var/spack/repos/builtin/packages/{package_name}/package.py"
            
            self.stdscr.addstr(7, 4, f"  URL: {package_url}")
            self.stdscr.refresh()
            
            recipe_content = self.spack_manager._fetch_recipe_content(package_name)
            
            # Clear screen and redraw to handle any stray output from spack_manager
            self.stdscr.clear()
            self.stdscr.addstr(2, title_x, title, curses.A_BOLD)
            
            current_step = 2
            self.stdscr.addstr(5, 4, "✓ Creating custom repository and adding version...")
            self.stdscr.addstr(6, 4, "✓ Fetching recipe from remote repository...")
            self.stdscr.addstr(7, 4, f"✓ Successfully fetched from: {package_url}")
            self.stdscr.addstr(8, 4, "► Processing package files...")
            self.stdscr.refresh();
            
            # Add to pending recipes with the actual recipe content
            # This version was found in remote but not local
            self.spack_manager.add_pending_recipe(package_name, version, recipe_content,
                                                found_in_local=False, found_in_remote=True)
            
            current_step = 3
            self.stdscr.addstr(8, 4, "✓ Processing package files...")
            self.stdscr.addstr(9, 4, "✓ Adding to environment repository...")
            self.stdscr.refresh()
            
            # Show completion message
            self.stdscr.addstr(11, 4, f"✓ Version {version} successfully added to environment repository")
            self.stdscr.addstr(12, 4, "The package specification has been saved.")
            self.stdscr.addstr(13, 4, "You will return to the package configuration screen.")
            self.stdscr.addstr(15, 4, "Press any key to continue...")
            self.stdscr.refresh()
            self.stdscr.getch()
            return True
                
        except Exception as e:
            self._show_error(f"Error adding version: {e}")
            return False
    
    def _show_error(self, message: str):
        """Show error message.
        
        Args:
            message: Error message
        """
        height, width = self.stdscr.getmaxyx()
        
        # Clear error area and show message
        error_y = height - 6
        self.stdscr.addstr(error_y, 2, " " * (width - 4))  # Clear line
        self.stdscr.addstr(error_y, 2, f"Error: {message}", curses.A_BOLD)
        self.stdscr.refresh()


class RadioButtonMenu:
    """Menu with radio button (checkbox) selection functionality."""
    
    def __init__(self, stdscr, title: str):
        """Initialize radio button menu.
        
        Args:
            stdscr: Curses screen object
            title: Menu title
        """
        self.stdscr = stdscr
        self.title = title
        self.current_row = 0
        self.top_row = 0
        self.selected_items = set()
    
    def display_menu(self, options: List[str], selected_row: int = 0) -> Optional[set]:
        """Display menu with radio button selection.
        
        Args:
            options: List of menu options
            selected_row: Initially selected row
            
        Returns:
            Set of selected option indices, None if cancelled
        """
        self.current_row = selected_row
        
        while True:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()
            
            # Display title
            title_x = (width - len(self.title)) // 2
            self.stdscr.addstr(1, title_x, self.title, curses.A_BOLD)
            
            # Calculate display window
            max_display = height - 8  # Leave room for instructions
            if self.current_row >= self.top_row + max_display:
                self.top_row = self.current_row - max_display + 1
            elif self.current_row < self.top_row:
                self.top_row = self.current_row
            
            # Display options with checkboxes
            for idx, option in enumerate(options[self.top_row:self.top_row + max_display]):
                row_idx = self.top_row + idx
                y = 4 + idx
                
                # Checkbox indicator
                checkbox = "☑️" if row_idx in self.selected_items else "☐"
                
                # Current row highlight
                if row_idx == self.current_row:
                    self.stdscr.addstr(y, 2, f"> {checkbox} {option}", curses.A_REVERSE)
                else:
                    self.stdscr.addstr(y, 4, f"{checkbox} {option}")
            
            # Display instructions
            instructions = [
                "Use ↑/↓ to navigate, Space to toggle selection",
                "'a' to select all, 'n' to select none",
                "Enter to continue with selected packages, Ctrl+C to quit"
            ]
            
            start_y = height - len(instructions) - 1
            for i, instruction in enumerate(instructions):
                self.stdscr.addstr(start_y + i, 2, instruction)
            
            # Show scroll indicators
            if self.top_row > 0:
                self.stdscr.addstr(3, width - 3, "↑")
            if self.top_row + max_display < len(options):
                self.stdscr.addstr(height - len(instructions) - 2, width - 3, "↓")
            
            # Show selection count
            count_text = f"Selected: {len(self.selected_items)}"
            self.stdscr.addstr(2, width - len(count_text) - 2, count_text)
            
            self.stdscr.refresh()
            
            # Handle input
            key = self.stdscr.getch()
            
            if key == curses.KEY_UP and self.current_row > 0:
                self.current_row -= 1
            elif key == curses.KEY_DOWN and self.current_row < len(options) - 1:
                self.current_row += 1
            elif key == ord(' '):  # Space to toggle selection
                if self.current_row in self.selected_items:
                    self.selected_items.remove(self.current_row)
                else:
                    self.selected_items.add(self.current_row)
            elif key in [ord('a'), ord('A')]:  # Select all
                self.selected_items = set(range(len(options)))
            elif key in [ord('n'), ord('N')]:  # Select none
                self.selected_items.clear()
            elif key in [curses.KEY_ENTER, ord('\n'), ord('\r')]:
                return self.selected_items
            elif key in [27]:  # Escape
                return None

class EmcEnvChainerTUI:
    """Main TUI application for emcenvchainer."""
    
    def __init__(self, config: Config, platform: Platform):
        """Initialize TUI application.
        
        Args:
            config: Configuration object
            platform: Detected platform
        """
        self.config = config
        self.platform = platform
        self.model_app_manager = ModelApplicationManager(
            platform.config, platform.name
        )

    def run(self):
        """Run the TUI application."""
        try:
            curses.wrapper(self._main_loop)
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
        except Exception as e:
            print(f"Error running TUI: {e}")

    def display_scrollable_text(self, stdscr, title: List[str], content: str):
        """Display scrollable text content."""
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        lines = content.split('\n')
        
        # Display title lines
        for i in range(len(title)):
            self._addstr_with_colored_markers(stdscr, i, 2, title[i])
        
        # Display separator line
        separator_y = len(title)
        stdscr.addstr(separator_y, 2, "=" * (width - 4))
        
        # Calculate header size (title lines + separator line + spacing)
        header_end_y = separator_y + 1
        
        # Add special note for Spack Concretize Output
        instruction_lines = ["Use UP/DOWN arrows to scroll, ENTER to continue..."]
        if "Spack Concretize Output" in title:
            instruction_lines.append("Note: [^] indicates packages from the upstream environment(s)")
        
        # Display instructions at bottom
        for i, instruction in enumerate(instruction_lines):
            self._addstr_with_colored_markers(stdscr, height - len(instruction_lines) - 1 + i, 2, instruction)
        
        # Calculate scrollable area dynamically based on header size
        display_start_y = header_end_y + 1  # Add one line of spacing after header
        display_height = height - display_start_y - len(instruction_lines) - 2  # Leave room for instructions and spacing
        scroll_pos = 0
        max_scroll = max(0, len(lines) - display_height)
        
        while True:
            for y in range(display_start_y, display_start_y + display_height):
                stdscr.move(y, 0)
                stdscr.clrtoeol()
            
            for i in range(display_height):
                line_idx = scroll_pos + i
                if line_idx < len(lines):
                    line = lines[line_idx]
                    if len(line) > width - 4:
                        line = line[:width - 7] + "..."
                    self._addstr_with_colored_markers(stdscr, display_start_y + i, 2, line)
            
            if max_scroll > 0:
                scroll_indicator = f"({scroll_pos + 1}-{min(scroll_pos + display_height, len(lines))} of {len(lines)})"
                indicator_y = height - len(instruction_lines) - 2  # Position above instruction lines
                stdscr.addstr(indicator_y, width - len(scroll_indicator) - 2, scroll_indicator)
            
            stdscr.refresh()
            key = stdscr.getch()
            
            if key == ord('\n') or key == ord('\r'):
                break
            elif key == curses.KEY_UP and scroll_pos > 0:
                scroll_pos -= 1
            elif key == curses.KEY_DOWN and scroll_pos < max_scroll:
                scroll_pos += 1

    def run_interactive_install(self, stdscr, spack_manager, env_path: str) -> bool:
        """Run spack install with live output, temporarily exiting curses mode.
        
        Args:
            stdscr: Curses screen object
            spack_manager: SpackManager instance
            env_path: Path to environment
            
        Returns:
            True if successful, False otherwise
        """
        # Exit curses mode temporarily
        curses.endwin()
        
        try:
            print("\n" + "="*60)
            print("Installing packages with Spack...")
            print("="*60)
            print("(This may take several minutes depending on packages)")
            print()
            
            # Run the interactive install
            success = spack_manager.install_environment_interactive(env_path)
            
            print()
            if success:
                print("Installation completed successfully!")
            else:
                print("Installation failed!")
            
            return success
            
        finally:
            # Restore curses mode
            stdscr.refresh()
            curses.doupdate()

    def _main_loop(self, stdscr):
        """Main TUI loop.
        
        Args:
            stdscr: Curses screen object
        """
        # Initialize curses
        curses.curs_set(0)  # Hide cursor
        stdscr.clear()
        
        # Initialize colors if supported
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            # Define color pairs
            curses.init_pair(1, curses.COLOR_RED, -1)  # Red text on default background
            curses.init_pair(2, curses.COLOR_GREEN, -1)  # Green text on default background
            curses.init_pair(3, curses.COLOR_YELLOW, -1)  # Yellow text on default background
        
        menu = TUIMenu(stdscr, "EMC spack-stack Environment Chainer")
        
        # Welcome screen with environment name configuration
        env_name = self._show_welcome_and_get_env_name(stdscr)
        if not env_name:
            return  # User cancelled
        
        # Main workflow
        selected_installation = self._select_installation(stdscr)
        if not selected_installation:
            return
        
        # Get packages and SpackManager
        packages, spack_manager = self._get_package_specifications_with_manager(stdscr, selected_installation)
        if not packages or not spack_manager:
            return
        
        self._create_environment(stdscr, selected_installation, packages, spack_manager, env_name)
    
    def _show_welcome_and_get_env_name(self, stdscr) -> Optional[str]:
        """Show welcome screen and get environment name from user.
        
        Args:
            stdscr: Curses screen object
            
        Returns:
            Environment name, None if cancelled
        """
        # Generate default name
        default_name = f"emcenv-{os.path.basename(os.getcwd())}"
        
        while True:
            stdscr.clear()
            height, width = stdscr.getmaxyx()
            
            # Title
            title = "EMC spack-stack Environment Chainer"
            title_x = (width - len(title)) // 2
            stdscr.addstr(2, title_x, title, curses.A_BOLD)
            
            # Welcome information
            welcome_lines = [
                "",
                f"Platform: {self.platform.name}",
                f"spack-stack top-level directory: {self.platform.spack_stack_path}",
                "",
                "Create a new Spack environment directory",
                "chained to an existing spack-stack installation.",
                "",
                f"Default environment name: {default_name}",
                "",
                "Enter a custom name below, or press ENTER to use the default.",
                "Ctrl+C to exit at any time."
            ]
            
            start_y = 5
            for i, line in enumerate(welcome_lines):
                if line:  # Skip empty lines for centering
                    line_x = (width - len(line)) // 2
                    stdscr.addstr(start_y + i, line_x, line)
            
            # Input prompt and field
            prompt = "Environment name: "
            prompt_y = start_y + len(welcome_lines) + 2
            prompt_x = (width - len(prompt) - 40) // 2  # Leave space for input
            stdscr.addstr(prompt_y, prompt_x, prompt)
            
            # Input field
            input_x = prompt_x + len(prompt)
            input_width = min(40, width - input_x - 4)
            
            # Text input handling
            text = ""
            cursor_pos = 0
            scroll_offset = 0
            
            # Enable cursor
            curses.curs_set(1)
            
            while True:
                # Handle horizontal scrolling
                if cursor_pos < scroll_offset:
                    scroll_offset = cursor_pos
                elif cursor_pos >= scroll_offset + input_width:
                    scroll_offset = cursor_pos - input_width + 1
                
                # Display visible portion of text
                visible_text = text[scroll_offset:scroll_offset + input_width]
                stdscr.move(prompt_y, input_x)
                stdscr.clrtoeol()
                stdscr.addstr(prompt_y, input_x, visible_text.ljust(input_width))
                
                # Position cursor
                display_cursor_pos = cursor_pos - scroll_offset
                stdscr.move(prompt_y, input_x + display_cursor_pos)
                
                # Show scroll indicators if needed
                if scroll_offset > 0:
                    stdscr.addstr(prompt_y, input_x - 1, "←", curses.A_BOLD)
                if scroll_offset + input_width < len(text):
                    stdscr.addstr(prompt_y, input_x + input_width, "→", curses.A_BOLD)
                
                stdscr.refresh()
                
                # Get input
                key = stdscr.getch()
                
                if key == ord('\n') or key == ord('\r'):  # Enter
                    curses.curs_set(0)  # Hide cursor
                    return text.strip() if text.strip() else default_name
                elif key == 27:  # Escape
                    curses.curs_set(0)  # Hide cursor
                    return None
                elif key == curses.KEY_BACKSPACE or key == 8 or key == 127:
                    if cursor_pos > 0:
                        text = text[:cursor_pos-1] + text[cursor_pos:]
                        cursor_pos -= 1
                elif key == curses.KEY_DC:  # Delete
                    if cursor_pos < len(text):
                        text = text[:cursor_pos] + text[cursor_pos+1:]
                elif key == curses.KEY_LEFT:
                    if cursor_pos > 0:
                        cursor_pos -= 1
                elif key == curses.KEY_RIGHT:
                    if cursor_pos < len(text):
                        cursor_pos += 1
                elif key == curses.KEY_HOME:
                    cursor_pos = 0
                elif key == curses.KEY_END:
                    cursor_pos = len(text)
                elif key == 24:  # Ctrl+X
                    text = ""
                    cursor_pos = 0
                elif 32 <= key <= 126:  # Printable characters
                    text = text[:cursor_pos] + chr(key) + text[cursor_pos:]
                    cursor_pos += 1

    def _select_installation(self, stdscr) -> Optional[Dict]:
        """Select installation or model application.
        
        Args:
            stdscr: Curses screen object
            
        Returns:
            Selected installation dict, None if cancelled
        """
        menu = TUIMenu(stdscr, "Select Installation Source")
        
        # Combine Spack installations and model applications
        options = []
        sources = []
        
        # Add Spack installations
        for installation in self.platform.spack_installations:
            options.append(f"🔗 {installation['name']} - {installation['install_path']}")
            sources.append(installation)
        
        # Add all model applications (showing module file URLs)
        for app in self.model_app_manager.applications:
            # Get the module URL choices for this application
            url_choices = app.get_module_url_choices()
            
            # Add an entry for each module URL choice
            for choice in url_choices:
                display_name = f"🌐 {app.config.get('name', app.name)} - {choice['name']}"
                options.append(display_name)
                sources.append({
                    "name": f"{app.name} ({choice['name']})",
                    "type": "model_application",
                    "application": app,
                    "selected_module_url": choice['url'],
                    "module_choice": choice
                })
        
        if not options:
            menu.display_info("No installations or model applications found!")
            return None
        
        # Add option to manually specify path
        options.append("📁 Specify custom path...")
        sources.append({"type": "custom"})
        
        selected_idx = menu.display_menu(options)
        if selected_idx is None:
            return None
        
        if sources[selected_idx]["type"] == "custom":
            return self._get_custom_path(stdscr)
        
        return sources[selected_idx]
    
    def _get_custom_path(self, stdscr) -> Optional[Dict]:
        """Get custom installation path from user.
        
        Args:
            stdscr: Curses screen object
            
        Returns:
            Custom installation dict, None if cancelled
        """
        dialog = PackageSpecDialog(stdscr)
        
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        
        title = "Enter Custom Installation Path"
        title_x = (width - len(title)) // 2
        stdscr.addstr(2, title_x, title, curses.A_BOLD)
        
        stdscr.addstr(5, 4, "Installation Path: ")
        stdscr.addstr(7, 4, "Enter the full path to the Spack installation directory")
        stdscr.addstr(8, 4, "(should contain .spack-db directory)")
        stdscr.addstr(height - 2, 4, "Press Enter when done, Ctrl+C to cancel")
        
        curses.echo()
        curses.curs_set(1)
        
        try:
            stdscr.refresh()
            path = stdscr.getstr(5, 22, width - 26).decode('utf-8').strip()
            
            if path and os.path.exists(path):
                return {
                    "name": f"Custom - {os.path.basename(path)}",
                    "install_path": path,
                    "type": "custom_path"
                }
            else:
                dialog._show_error("Invalid path!")
                return None
                
        except KeyboardInterrupt:
            return None
        finally:
            curses.noecho()
            curses.curs_set(0)
    
    def _get_spack_config(self, installation: Dict) -> Tuple[str, str]:
        """Get Spack configuration for the given installation.
        
        Args:
            installation: Installation configuration
            
        Returns:
            Tuple of (spack_root, upstream_path)
            
        Raises:
            RuntimeError: If Spack installation cannot be inferred from path structure
        """
        if installation.get("type") == "model_application":
            # For model applications, extract install path and infer Spack root
            app = installation["application"]
            selected_module_url = installation.get("selected_module_url")
            
            # Create model application instance if needed
            if selected_module_url:
                from .model_apps import ModelApplication
                model_app = ModelApplication(app.name, app.config, app.platform_name, selected_module_url)
            else:
                model_app = app
            
            # Extract install path from the model application
            install_path = model_app.extract_install_path()
            if not install_path:
                raise RuntimeError("Could not extract install path from model application!")
            
            upstream_path = install_path
            
            # Infer Spack root from upstream path structure
            # Expected structure: /path/to/spack-stack/spack-stack-X.Y.Z/envs/env-name/install
            # Spack root should be: /path/to/spack-stack/spack-stack-X.Y.Z/spack
            upstream_parts = Path(upstream_path).parts
            
            try:
                # Find 'install' in the path and go up 3 levels to get to spack-stack root
                install_index = upstream_parts.index('install')
                if install_index >= 3:  # Need at least: .../envs/env-name/install
                    # Go up 3 levels: install -> env-name -> envs -> spack-stack-root
                    spack_stack_root = os.path.join('/', *upstream_parts[:install_index-2])
                    spack_root = os.path.join(spack_stack_root, 'spack')
                    
                    # Verify the Spack installation exists
                    spack_exe = os.path.join(spack_root, 'bin', 'spack')
                    if not os.path.exists(spack_exe):
                        raise RuntimeError(
                            f"Spack executable not found at inferred location: {spack_exe}\n"
                            f"Cannot infer Spack installation from upstream path: {upstream_path}\n"
                            f"Expected structure: .../spack-stack-X.Y.Z/envs/env-name/install"
                        )
                    
                    return spack_root, upstream_path
                else:
                    raise RuntimeError(
                        f"Invalid upstream path structure: {upstream_path}\n"
                        f"Expected structure: .../spack-stack-X.Y.Z/envs/env-name/install"
                    )
                    
            except ValueError:
                # 'install' not found in path
                raise RuntimeError(
                    f"Cannot infer Spack installation from upstream path: {upstream_path}\n"
                    f"Expected path to end with '.../envs/env-name/install'"
                )
            
        else:
            # For regular Spack installations, use the installation directly
            spack_root = self.platform.get_spack_root(installation)
            upstream_path = installation["install_path"]
            
            # Verify the Spack installation exists
            spack_exe = os.path.join(spack_root, 'bin', 'spack')
            if not os.path.exists(spack_exe):
                raise RuntimeError(
                    f"Spack executable not found at: {spack_exe}\n"
                    f"Installation path: {upstream_path}"
                )
            
            return spack_root, upstream_path

    def _get_package_specifications_with_manager(self, stdscr, installation: Dict) -> Tuple[Optional[List[Dict]], Optional[SpackManager]]:
        """Get package specifications from user.
        
        Args:
            stdscr: Curses screen object
            installation: Selected installation
            
        Returns:
            Tuple of (package specifications, SpackManager), (None, None) if cancelled
        """
        # Initialize SpackManager early for version validation
        spack_root, upstream_path = self._get_spack_config(installation)
        spack_manager = SpackManager(spack_root, self.config)
        
        if installation["type"] == "model_application":
            packages = self._get_packages_from_model_app(stdscr, installation, spack_manager)
        else:
            packages = self._get_packages_manually(stdscr, spack_manager)
        
        return packages, spack_manager
    
    def _get_packages_from_model_app(self, stdscr, installation: Dict, spack_manager: SpackManager) -> Optional[List[Dict]]:
        """Get packages from model application dependencies using radio button selection.
        
        Args:
            stdscr: Curses screen object
            installation: Model application installation
            spack_manager: SpackManager instance for version validation
            
        Returns:
            List of package specifications, None if cancelled
        """
        app = installation["application"]
        
        # Create a model application instance with the pre-selected module URL
        selected_module_url = installation.get("selected_module_url")
        if selected_module_url:
            from .model_apps import ModelApplication
            selected_app = ModelApplication(app.name, app.config, app.platform_name, selected_module_url)
        else:
            # Fallback to the original app if no specific URL was selected
            selected_app = app
        
        menu = TUIMenu(stdscr, f"Loading {installation['name']} Information")
        menu.display_info("Downloading and parsing module files...", wait_for_key=False)
        
        try:
            # Get dependencies from the selected module
            dependencies = selected_app.parse_dependencies()
            
            # Get upgradable packages from common module
            upgradable_packages = selected_app.get_upgradable_packages()
            
        except Exception as e:
            menu.display_info(f"Error parsing module files: {e}")
            return None
        
        # Combine dependencies and upgradable packages for selection
        all_packages = []
        upgradable_names = {pkg['name'] for pkg in upgradable_packages}
        
        # Add upgradable packages first (these are preferred)
        for pkg in upgradable_packages:
            all_packages.append({
                "name": pkg['name'],
                "current_version": pkg['version'],
                "type": "upgradable", 
                "source": pkg
            })
        
        # Add dependencies only if they're not already available as upgradable packages
        for dep in dependencies:
            if dep['name'] not in upgradable_names:
                all_packages.append({
                    "name": dep['name'],
                    "current_version": dep['version'],
                    "type": "dependency",
                    "source": dep
                })
        
        if not all_packages:
            menu.display_info("No packages found in module files!")
            return None
        
        # Use radio button selection for packages
        return self._select_packages_with_radio_buttons(stdscr, all_packages, selected_app, spack_manager)
    
    def _select_packages_with_radio_buttons(self, stdscr, all_packages: List[Dict], selected_app, spack_manager: SpackManager) -> Optional[List[Dict]]:
        """Select packages using radio button interface.
        
        Args:
            stdscr: Curses screen object
            all_packages: All available packages
            selected_app: The model application instance
            spack_manager: SpackManager instance for version validation
            
        Returns:
            List of selected package specifications, None if cancelled
        """
        # Create display options for radio button menu
        options = []
        for pkg in all_packages:
            # Skip ufs_common, cmake, and spack-stack metamodules (stack-*)
            if pkg["name"] in ["ufs_common", "cmake"] or pkg["name"].startswith("stack-"):
                continue
                
            pkg_type = "📦"
            description = ""
            if pkg["type"] == "upgradable" and pkg["source"].get("description"):
                description = f" - {pkg['source']['description']}"
            options.append(f"{pkg_type} {pkg['name']} (v{pkg['current_version']}){description}")
        
        # Show radio button selection menu
        radio_menu = RadioButtonMenu(stdscr, "Select Packages to Include in Environment")
        selected_indices = radio_menu.display_menu(options)
        
        if selected_indices is None:
            return None
        
        if not selected_indices:
            menu = TUIMenu(stdscr, "No Packages Selected")
            menu.display_info("No packages were selected. The environment will be created without additional packages.")
            return []
        
        # Get detailed specifications for selected packages
        selected_packages = []
        for idx in selected_indices:
            pkg = all_packages[idx]
            
            # Get package specification with version and variants
            spec = self._get_package_specification(stdscr, pkg, spack_manager)
            if spec:
                selected_packages.append(spec)
        
        selected_packages.extend([pkg for idx, pkg in enumerate(all_packages) if idx not in selected_indices])

        return selected_packages if selected_packages else None
    
    def _get_package_specification(self, stdscr, pkg: Dict, spack_manager: SpackManager) -> Optional[Dict]:
        """Get detailed package specification (version, variants) from user.
        
        Args:
            stdscr: Curses screen object
            pkg: Package information
            spack_manager: SpackManager instance for version validation
            
        Returns:
            Package specification dict, None if cancelled
        """
        # Use existing PackageSpecDialog for detailed configuration
        dialog = PackageSpecDialog(stdscr, spack_manager)
        return dialog.get_package_spec(pkg["name"], pkg["current_version"])
    
    def _get_packages_manually(self, stdscr, spack_manager: SpackManager) -> Optional[List[Dict]]:
        """Get package specifications manually from user.
        
        Args:
            stdscr: Curses screen object
            spack_manager: SpackManager instance for version validation
            
        Returns:
            List of package specifications, None if cancelled
        """
        packages = []
        dialog = PackageSpecDialog(stdscr, spack_manager)
        
        while True:
            menu = TUIMenu(stdscr, "Package Specifications")
            
            options = []
            for pkg in packages:
                spec_str = pkg["name"]
                if pkg.get("version"):
                    spec_str += f"@{pkg['version']}"
                if pkg.get("variants"):
                    spec_str += f" {pkg['variants']}"
                options.append(spec_str)
            
            options.extend(["➕ Add package", "✅ Continue" if packages else "❌ Continue (no packages)"])
            
            selected_idx = menu.display_menu(options)
            if selected_idx is None:
                return None
            
            if selected_idx == len(packages):  # Add package
                pkg_spec = dialog.get_package_spec()
                if pkg_spec:
                    packages.append(pkg_spec)
            elif selected_idx == len(packages) + 1:  # Continue
                return packages if packages else None
            else:  # Edit existing package
                pkg_spec = dialog.get_package_spec(
                    packages[selected_idx]["name"],
                    packages[selected_idx]["version"]
                )
                if pkg_spec:
                    packages[selected_idx] = pkg_spec
    
    def _create_environment(self, stdscr, installation: Dict, packages: List[Dict], spack_manager: SpackManager, env_name: str):
        """Create the Spack environment.
        
        Args:
            stdscr: Curses screen object
            installation: Selected installation
            packages: Package specifications
            spack_manager: SpackManager instance (already initialized)
            env_name: Name for the environment
        """
        menu = TUIMenu(stdscr, "Creating Environment")
        
        # Check if we need to handle custom recipes
        has_custom_recipes = False
        try:
            # Get upstream path from installation config
            _, upstream_path = self._get_spack_config(installation)
            
            # Use the provided SpackManager (already initialized)
            # Create environment
            work_dir = os.getcwd()
            env_path, packages_needing_edit = spack_manager.create_environment(
                env_name, upstream_path, packages, work_dir, self.platform,
            )
            
            has_custom_recipes = len(packages_needing_edit) > 0
            
            # Show environment creation message with appropriate timeout
            if has_custom_recipes:
                # Show custom recipe dialog and get user's editing choices
                packages_needing_edit = self._show_custom_recipe_dialog(stdscr, packages_needing_edit)
                menu.display_info(f"Environment created at: {env_path}")
            
                # Handle manual recipe editing if needed
                if packages_needing_edit:
                    self._handle_manual_recipe_editing(stdscr, spack_manager, packages_needing_edit)
            
            # Concretize
            with open(os.path.join(env_path, "spack.yaml"), "r") as f:
                spack_yaml = f.read()
            self.display_scrollable_text(
                stdscr,
                [f"Environment created at: {env_path}", "Proceed with concretization?", "Make any manual changes to spack.yaml & package.py's now.", "spack.yaml:"],
                spack_yaml
            )
            menu.display_info("Concretizing environment...", wait_for_key=False)
            success, new_installs, concretize_output = spack_manager.concretize_environment(env_path)
            
            if not success:
                failure_msg = f"Concretization failed for environment: {env_path}\n\n{chr(10).join(new_installs)}"
                menu.display_info(failure_msg)
                return
            
            # Show concretization output
            self.display_scrollable_text(stdscr, ["Proceed with build?", "'spack concretize' output below", " > '[^]': existing package from upstream installation", " > ' - ': package to be built"], concretize_output)

            # Install packages
            install_success = self.run_interactive_install(stdscr, spack_manager, env_path)
            
            if not install_success:
                menu.display_info("Installation failed!")
                return

            # Refresh modules
            menu.display_info("Refreshing modules...", wait_for_key=False)
            modulefiles_path = spack_manager.refresh_modules(env_path)
            
            # Generate activation scripts
            menu.display_info("Generating activation scripts...", wait_for_key=False)
            self._generate_activation_scripts(stdscr, spack_manager, env_path, upstream_path)
            
            # Final success message
            success_msg = f"Environment created successfully!\n"
            success_msg += "Environment path: {env_path}\n\n"
            success_msg += "• To load packages via spack-stack metamodules (stack-*), prepend the following to $MODULEPATH *instead* of the existing spack-stack installation:\n"
            success_msg += f"{modulefiles_path}\n\n"
            success_msg += "• To export package version variables (e.g., 'hdf5_ver', 'netcdf_c_ver') into the environment:\n"
            success_msg += f". {env_path}/export_package_versions.sh\n\n"
            success_msg += "• To activate the Spack environment (such as for further modification):\n"
            success_msg += f". {env_path}/activate_spack_env.sh"
            
            menu.display_info(success_msg)
            
        except Exception as e:
            menu.display_info(f"Error creating environment: {e}")
    
    def _show_custom_recipe_dialog(self, stdscr, packages_needing_edit: List[Dict]) -> List[Dict]:
        """Show dialog for custom recipes and editing choices.
        
        Args:
            stdscr: Curses screen object
            packages_needing_edit: List of packages needing custom recipes
            
        Returns:
            Updated list of packages with editing choices
        """
        if not packages_needing_edit:
            return packages_needing_edit
        
        # Create copies to avoid modifying the original
        packages = [pkg.copy() for pkg in packages_needing_edit]
        
        # Initialize editing choices (only for packages not found in either repo)
        for pkg in packages:
            found_in_local = pkg.get('found_in_local', False)
            found_in_remote = pkg.get('found_in_remote', False)
            # Only offer editing if version was not found in either local or remote
            pkg['can_edit'] = not found_in_local and not found_in_remote
            pkg['edit_recipe'] = False  # Default to False
        
        current_selection = 0
        
        while True:
            height, width = stdscr.getmaxyx()
            stdscr.clear()
            
            # Title
            title = "Custom Recipes Configuration"
            title_x = (width - len(title)) // 2
            stdscr.addstr(2, title_x, title, curses.A_BOLD)
            
            # Instructions
            instructions = [
                "The following packages will have custom recipes created.",
                "Editing is only available for versions not found in local or remote repositories.",
                "Use ↑/↓ to navigate, Space to toggle editing (where available), Enter to continue.",
                "",
            ]
            
            start_y = 4
            for i, line in enumerate(instructions):
                if start_y + i < height - 2:
                    stdscr.addstr(start_y + i, 4, line[:width-8])
            
            # Package list
            list_start_y = start_y + len(instructions)
            
            for i, pkg in enumerate(packages):
                package_name = pkg['package_name']
                version = pkg['version']
                recipe_path = pkg['recipe_path']
                edit_recipe = pkg.get('edit_recipe', False)
                can_edit = pkg.get('can_edit', False)
                found_in_local = pkg.get('found_in_local', False)
                found_in_remote = pkg.get('found_in_remote', False)
                
                # Determine source and status
                source = self._determine_recipe_source(pkg)
                if found_in_local:
                    status = "found in local, copied for custom repo"
                elif found_in_remote:
                    status = "found in remote, copied for custom repo"
                else:
                    status = "not found, requires manual creation"
                
                # Calculate line position
                line_y = list_start_y + (i * 5)  # Increased spacing for status line
                
                if line_y >= height - 8:
                    break  # Don't overflow screen
                
                # Highlight current selection
                if i == current_selection:
                    stdscr.addstr(line_y, 2, "►", curses.A_BOLD)
                else:
                    stdscr.addstr(line_y, 2, " ")
                
                # Package info
                pkg_line = f"{package_name}@{version}"
                stdscr.addstr(line_y, 4, pkg_line, curses.A_BOLD if i == current_selection else 0)
                
                # Source info
                source_line = f"Source: {source}"
                stdscr.addstr(line_y + 1, 6, source_line)
                
                # Status info
                status_line = f"Status: {status}"
                stdscr.addstr(line_y + 2, 6, status_line)
                
                # Recipe path (truncated if too long)
                recipe_line = f"Recipe: {recipe_path}"
                max_recipe_len = width - 14
                if len(recipe_line) > max_recipe_len:
                    recipe_line = recipe_line[:max_recipe_len-3] + "..."
                stdscr.addstr(line_y + 3, 6, recipe_line)
                
                # Edit choice (only if editing is available)
                edit_status = "✓ Edit recipe" if edit_recipe else "✗ Edit recipe"
                edit_attr = curses.A_REVERSE if i == current_selection else 0
                stdscr.addstr(line_y + 4, 6, edit_status, edit_attr)
            
            # Footer instructions
            footer_lines = [
                "",
                "Controls:",
                "↑/↓ - Navigate packages",
                "Space - Toggle recipe editing (for packages requiring manual creation)",
                "Enter - Continue with current settings",
                "Esc - Cancel"
            ]
            
            footer_start_y = height - len(footer_lines) - 1
            for i, line in enumerate(footer_lines):
                if footer_start_y + i < height:
                    stdscr.addstr(footer_start_y + i, 4, line)
            
            stdscr.refresh()
            
            # Handle input
            key = stdscr.getch()
            
            if key == curses.KEY_UP and current_selection > 0:
                current_selection -= 1
            elif key == curses.KEY_DOWN and current_selection < len(packages) - 1:
                current_selection += 1
            elif key == ord(' '):  # Space - toggle editing (only if editing is available)
                packages[current_selection]['edit_recipe'] = not packages[current_selection].get('edit_recipe', False)
            elif key in [curses.KEY_ENTER, ord('\n'), ord('\r')]:
                # Continue with current settings
                return packages
            elif key == 27:  # Escape
                # Cancel - return original packages without editing choices
                return packages_needing_edit
    
    def _determine_recipe_source(self, pkg: Dict) -> str:
        """Determine the source of a recipe.
        
        Args:
            pkg: Package dictionary
            
        Returns:
            Source description string
        """
        # Check if the package uses a local copy (from SpackManager pending recipes)
        use_local_copy = pkg.get('use_local_copy', True)  # Default to local if not specified
        
        if use_local_copy:
            return "local Spack installation"
        else:
            return "remote Spack repository"


    def _handle_manual_recipe_editing(self, stdscr, spack_manager: SpackManager, packages_needing_edit: List[Dict]):
        """Handle manual recipe editing in the TUI.
        
        Args:
            stdscr: Curses screen object
            spack_manager: SpackManager instance
            packages_needing_edit: List of packages that need manual editing (with edit_recipe flags)
        """
        if not packages_needing_edit:
            return
        
        # Filter packages that user chose to edit
        packages_to_edit = [pkg for pkg in packages_needing_edit if pkg.get('edit_recipe', False)]
        
        if not packages_to_edit:
            return
            
        menu = TUIMenu(stdscr, "Manual Recipe Editing")
        
        # Show packages that user chose to edit
        package_list = []
        for pkg in packages_to_edit:
            package_list.append(f"  • {pkg['package_name']}@{pkg['version']}")
        
        info_msg = f"""The following package(s) will be opened for manual recipe editing:

{chr(10).join(package_list)}

Each recipe file has been created with a template that you can customize.
The editor will open each recipe file in sequence.

Ready to edit these recipes?"""

        menu.display_info(info_msg)

        # Temporarily exit curses to run the editing workflow
        curses.endwin()
        try:
            success = spack_manager.offer_package_edit(packages_to_edit)
            if success:
                print("\n✓ All manual recipe editing completed successfully!")
            else:
                print("\n⚠ Manual recipe editing was cancelled or failed.")
        finally:
            # Re-initialize curses
            stdscr.clear()
            stdscr.refresh()
            curses.curs_set(0)

    def _generate_activation_scripts(self, stdscr, spack_manager: SpackManager, env_path: str, upstream_path: str):
        """Generate activation scripts for the environment.
        
        Args:
            stdscr: Curses screen object
            spack_manager: SpackManager instance
            env_path: Path to the environment
            upstream_path: Path to the upstream installation
        """
        import os
        
        try:
            # Generate activate_spack_env.sh
            self._generate_activate_script(env_path, upstream_path)
            
            # Generate export_package_versions.sh
            self._generate_package_versions_script(spack_manager, env_path)
            
        except Exception as e:
            menu = TUIMenu(stdscr, "Script Generation")
            menu.display_info(f"Warning: Failed to generate activation scripts: {e}")

    def _generate_activate_script(self, env_path: str, upstream_path: str):
        """Generate the activate_spack_env.sh script.
        
        Args:
            env_path: Path to the environment
            upstream_path: Path to the upstream installation
        """
        import os
        from pathlib import Path
        
        env_name = os.path.basename(env_path)
        output_script_path = os.path.join(env_path, "activate_spack_env.sh")
        
        spack_stack_path = os.path.abspath(os.path.join(upstream_path, "../../../"))
        setup_sh_path = os.path.abspath(os.path.join(spack_stack_path, "spack/share/spack/setup-env.sh"))
        
        script_content = f"""#!/bin/bash
# Activation script for Spack environment in the same directory ({env_name})
# Generated by emcenvchainer

unset SPACK_ENV

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${{BASH_SOURCE[0]}}" )" &> /dev/null && pwd )"

# Source the spack-stack setup
"""
        script_content += f'source "{setup_sh_path}" &> /dev/null\n'
        
        script_content += f"""
# Activate the Spack environment
spack env activate "$SCRIPT_DIR"

echo "Spack environment ${{SPACK_ENV?'Setup/activation failed!'}} activated"
echo "using spack-stack installation at {spack_stack_path}"
"""
        
        with open(output_script_path, 'w') as f:
            f.write(script_content)

    def _generate_package_versions_script(self, spack_manager: SpackManager, env_path: str):
        """Generate the export_package_versions.sh script.
        
        Args:
            spack_manager: SpackManager instance
            env_path: Path to the environment
        """
        import os
        
        script_path = os.path.join(env_path, "export_package_versions.sh")
        env_name = os.path.basename(env_path)
        
        try:
            # Run spack find to get package versions using SpackManager
            args = ['find', '--format', 'export {name}_ver={version}']
            result = spack_manager._run_spack_command(args, cwd=env_path)
            
            if result.returncode == 0:
                # Process the output to replace hyphens with underscores before the equal sign
                lines = result.stdout.strip().split('\n')
                processed_lines = []
                
                for line in lines:
                    if '=' in line and line.startswith('export '):
                        # Split at the equal sign
                        before_eq, after_eq = line.split('=', 1)
                        # Replace hyphens with underscores in the part before the equal sign
                        before_eq = before_eq.replace('-', '_')
                        processed_line = f"{before_eq}={after_eq}"
                        processed_lines.append(processed_line)
                
                export_content = '\n'.join(processed_lines)
            else:
                # Fallback if spack find fails
                export_content = "# Failed to generate package versions automatically"
                
        except Exception as e:
            # Fallback content if command fails
            export_content = f"# Failed to generate package versions: {e}"
        
        script_content = f"""#!/bin/bash
# The script exports version variables for all packages in the Spack environment in this directory ({env_name})
# Generated by emcenvchainer

{export_content}

echo "Package versions exported for environment '{env_name}'"
"""
        
        with open(script_path, 'w') as f:
            f.write(script_content)

    def _addstr_with_colored_markers(self, stdscr, y, x, text, attr=0):
        """Add string with colored [^] markers.
        
        Args:
            stdscr: Curses screen object
            y: Y position
            x: X position
            text: Text to display
            attr: Base text attributes
        """
        if "[^]" not in text:
            # No markers to color, display normally
            stdscr.addstr(y, x, text, attr)
            return
        
        current_x = x
        parts = text.split("[^]")
        
        for i, part in enumerate(parts):
            if i > 0:  # Add colored [^] before each part except the first
                try:
                    # Red + bold for [^] marker
                    marker_attr = curses.color_pair(1) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD
                    stdscr.addstr(y, current_x, "[^]", marker_attr)
                    current_x += 3
                except curses.error:
                    pass  # Ignore if we go off screen
            
            if part:  # Add the text part
                try:
                    stdscr.addstr(y, current_x, part, attr)
                    current_x += len(part)
                except curses.error:
                    pass  # Ignore if we go off screen
