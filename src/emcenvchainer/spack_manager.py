"""Spack integration and environment management."""

import io
import os
import re
import sys
import shlex
import shutil
import subprocess
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ruamel.yaml import YAML

from .config import Config


class SpackManager:
    """Manages Spack operations and environment creation."""
    
    def __init__(self, spack_root: str, config: Config):
        """Initialize Spack manager.
        
        Args:
            spack_root: Path to Spack installation
            config: Configuration object
        """
        self.spack_root = Path(spack_root)
        self.config = config
        self.spack_exe = self.spack_root / "bin" / "spack"
        self.pending_recipes = {}  # Store recipes to be added when environment is created
        self.pending_checksums = []  # Store checksum operations to be performed when environment is created
        self.pending_git_commits = []  # Store git commit operations to be performed when environment is created
        self.logger = None  # Will be initialized when environment directory is created

        assert self.spack_exe.exists(), "Spack executable not found"
    
    def setup_logging(self, env_path: str) -> None:
        """Setup logging for the environment creation process.
        
        Args:
            env_path: Path to the environment directory
        """
        # Create logs directory
        logs_dir = Path(env_path) / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        log_filename = f"emcenvchainer_{timestamp}.log"
        log_path = logs_dir / log_filename
        
        # Setup logger
        self.logger = logging.getLogger(f"emcenvchainer_{env_path}")
        self.logger.setLevel(logging.INFO)
        
        # Remove any existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create file handler
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
        
        # Log initial message
        self.logger.info(f"EMC Environment Chainer logging started")
        self.logger.info(f"Environment path: {env_path}")
        self.logger.info(f"Log file: {log_path}")
        
        print(f"Logging to: {log_path}")
    
    def _log_and_print(self, message: str, level: str = "info") -> None:
        """Log a message and optionally print to console.
        
        Args:
            message: Message to log
            level: Log level (info, warning, error)
        """
        if self.logger:
            if level.lower() == "warning":
                self.logger.warning(message)
            elif level.lower() == "error":
                self.logger.error(message)
            else:
                self.logger.info(message)
        
        # Still print important messages to console
        print(message)
    
    def _run_spack_command(self, args: List[str], cwd: str = None, vars: Optional[dict] = {}) -> subprocess.CompletedProcess:
        """Run a spack command.
        
        Args:
            args: Command arguments
            cwd: Working directory
            
        Returns:
            CompletedProcess result
        """
        cmd = [str(self.spack_exe)] + args
        cmd_str = ' '.join(cmd)
        
        if self.logger:
            self.logger.info(f"Executing spack command: {cmd_str}")
            if cwd:
                self.logger.info(f"Working directory: {cwd}")
        
        try:
            env = os.environ.copy()
            for key in vars.keys():
                env[key] = vars[key]
                if key == "SPACK_ENV":
                    env[key] = ""
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            
            if self.logger:
                self.logger.info(f"Command completed with return code: {result.returncode}")
                if result.stdout:
                    self.logger.info(f"STDOUT:\n{result.stdout}")
                if result.stderr:
                    if result.returncode != 0:
                        self.logger.error(f"STDERR:\n{result.stderr}")
                    else:
                        self.logger.info(f"STDERR:\n{result.stderr}")
            
            return result
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to run spack command {cmd_str}: {e}")
            raise RuntimeError(f"Failed to run spack command {cmd_str}: {e}")
            
    def add_pending_recipe(self, package_name: str, version: str, recipe_content: str = None,
                          needs_manual_edit: bool = False, use_local_copy: bool = False,
                          found_in_local: bool = False, found_in_remote: bool = False):
        """Add a recipe to be created when environment is built.
        
        Args:
            package_name: Name of the package
            version: Version to add
            recipe_content: Optional recipe content (if None, will be fetched)
            needs_manual_edit: Whether this recipe needs manual editing after creation
            use_local_copy: Whether to copy the entire package directory from local installation
            found_in_local: Whether the version was found in local Spack repo
            found_in_remote: Whether the version was found in remote Spack repo
        """
        if package_name not in self.pending_recipes:
            self.pending_recipes[package_name] = []
        self.pending_recipes[package_name].append({
            'version': version,
            'recipe_content': recipe_content,
            'needs_manual_edit': needs_manual_edit,
            'use_local_copy': use_local_copy,
            'found_in_local': found_in_local,
            'found_in_remote': found_in_remote
        })
        print(f"Added {package_name}@{version} to pending recipes (manual edit: {needs_manual_edit}, local: {found_in_local}, remote: {found_in_remote})")

    def add_pending_checksum(self, package_name: str, version: str):
        """Add a checksum operation to be performed when environment is created.
        
        Args:
            package_name: Name of the package
            version: Version to add checksum for
        """
        checksum_info = {
            'package_name': package_name,
            'version': version
        }
        self.pending_checksums.append(checksum_info)
        print(f"Added {package_name}@{version} to pending checksums")

    def _process_pending_recipes(self, env_path: str) -> List[Dict]:
        """Process all pending recipes and add them to the environment repository.

        Args:
            env_path: Path to the environment

        Returns:
            List of packages that need manual editing
        """
        if not self.pending_recipes:
            return []

        self._log_and_print(f"Processing {len(self.pending_recipes)} pending recipe(s)...")

        # Get the environment repository path
        repo_path = Path(env_path) / "envrepo"
        packages_dir = repo_path / "packages"

        packages_needing_edit = []

        for package_name, versions in self.pending_recipes.items():
            for version_info in versions:
                version = version_info['version']
                recipe_content = version_info['recipe_content']
                needs_manual_edit = version_info.get('needs_manual_edit', False)
                use_local_copy = version_info.get('use_local_copy', False)
                found_in_local = version_info.get('found_in_local', False)
                found_in_remote = version_info.get('found_in_remote', False)

                self._log_and_print(f"Processing recipe for {package_name}@{version} (manual_edit={needs_manual_edit}, local={found_in_local}, remote={found_in_remote})")

                try:
                    # Always create the package directory
                    package_dir = packages_dir / package_name
                    package_dir.mkdir(parents=True, exist_ok=True)

                    # If the version exists in the remote repo, always fetch remote recipe and supporting files
                    if found_in_remote or recipe_content:
                        # Fetch recipe content if not already provided
                        if not recipe_content:
                            recipe_content = self._fetch_recipe_content(package_name)
                            if not recipe_content:
                                self._log_and_print(f"✗ Could not fetch remote recipe for {package_name}", "error")
                                continue

                        # Write package.py from remote
                        package_py_path = package_dir / "package.py"
                        with open(package_py_path, 'w') as f:
                            f.write(recipe_content)
                        if self.logger:
                            self.logger.info(f"Written remote recipe content for {package_name}")

                        # Fetch all patch/supporting files from remote
                        self._fetch_and_write_all_remote_files(package_name, package_dir)

                        # If manual edit requested, add to edit list
                        if needs_manual_edit:
                            packages_needing_edit.append({
                                'package_name': package_name,
                                'version': version,
                                'recipe_path': str(package_py_path),
                                'use_local_copy': use_local_copy,
                                'found_in_local': found_in_local,
                                'found_in_remote': True
                            })
                            if self.logger:
                                self.logger.info(f"Added {package_name} to manual editing list")
                        else:
                            if self.logger:
                                self.logger.info(f"Added {package_name} recipe to environment repository")
                                self.logger.info(f"Package directory: {package_dir}")

                    # If manual edit requested and use_local_copy, copy from local installation
                    elif needs_manual_edit and use_local_copy:
                        success = self._fetch_and_write_package_directory(package_name, package_dir)
                        if success:
                            packages_needing_edit.append({
                                'package_name': package_name,
                                'version': version,
                                'recipe_path': str(package_dir / "package.py"),
                                'use_local_copy': use_local_copy,
                                'found_in_local': True,
                                'found_in_remote': False
                            })
                            if self.logger:
                                self.logger.info(f"Copied {package_name} from local installation for manual editing")
                        else:
                            self._log_and_print(f"✗ Could not copy {package_name} from local installation", "warning")

                    # Otherwise, try to copy from local installation
                    else:
                        success = self._fetch_and_write_package_directory(package_name, package_dir)
                        if success:
                            if self.logger:
                                self.logger.info(f"Copied {package_name} from local Spack installation")
                                self.logger.info(f"Package directory: {package_dir}")
                        else:
                            self._log_and_print(f"✗ No recipe content available for {package_name}@{version}", "warning")

                except Exception as e:
                    self._log_and_print(f"✗ Error adding {package_name}@{version}: {e}", "error")

        # Clear pending recipes after processing
        self.pending_recipes.clear()
        
        if self.logger:
            self.logger.info(f"Completed processing {len(packages_needing_edit)} packages needing manual editing")

        return packages_needing_edit

    def _process_pending_checksums(self, env_path: str) -> List[Dict]:
        """Process all pending checksum operations.
        
        Args:
            env_path: Path to the environment
            
        Returns:
            List of packages that were processed and need manual editing
        """
        if not self.pending_checksums:
            return []
            
        self._log_and_print(f"Processing {len(self.pending_checksums)} pending checksum operation(s)...")
        
        # Get the environment repository path
        repo_path = Path(env_path) / "envrepo"
        packages_dir = repo_path / "packages"
        
        packages_for_editing = []
        
        for checksum_info in self.pending_checksums:
            package_name = checksum_info['package_name']
            version = checksum_info['version']
            
            try:
                self._log_and_print(f"Setting up custom recipe for {package_name}@{version}...")
                
                # Create package directory if it doesn't exist
                package_dir = packages_dir / package_name
                package_dir.mkdir(parents=True, exist_ok=True)
                
                package_py_path = package_dir / "package.py"
                
                # First, copy the recipe from local installation
                success = self._fetch_and_write_package_directory(package_name, package_dir)
                if not success:
                    # If that fails, try to get it from remote
                    recipe_content = self._fetch_recipe_content(package_name)
                    if recipe_content:
                        with open(package_py_path, 'w') as f:
                            f.write(recipe_content)
                        if self.logger:
                            self.logger.info(f"Fetched recipe from remote repository")
                    else:
                        self._log_and_print(f"✗ Could not obtain recipe for {package_name}", "error")
                        continue
                
                # Now that we have the recipe, run spack checksum to add the version
                self._log_and_print(f"Running spack checksum for {package_name}@{version}...")
                
                # Run spack checksum command in the environment context
                cmd = [str(self.spack_exe), '-e', env_path, 'checksum', '--add-to-package', package_name, version]
                edit_env = os.environ.copy()
                edit_env['EDITOR'] = 'echo' # Make it non-interactive, as we will edit it later
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=150,
                    env=edit_env,
                )
                
                if result.returncode == 0:
                    self._log_and_print(f"✓ Successfully added checksum for {package_name}@{version}")
                    
                    # The checksum command should have modified the recipe in the custom repo
                    # Add to packages for editing
                    packages_for_editing.append({
                        'package_name': package_name,
                        'version': version,
                        'recipe_path': str(package_py_path),
                        'use_local_copy': True,
                        'found_in_local': True,
                        'found_in_remote': False,
                        'operation': 'checksum'
                    })
                else:
                    self._log_and_print(f"✗ Failed to add checksum for {package_name}@{version}: {result.stderr}", "error")
                    # Still add to editing list so user can manually fix
                    packages_for_editing.append({
                        'package_name': package_name,
                        'version': version,
                        'recipe_path': str(package_py_path),
                        'use_local_copy': True,
                        'found_in_local': True,
                        'found_in_remote': False,
                        'operation': 'checksum_failed',
                        'error': result.stderr
                    })
                    
            except subprocess.TimeoutExpired:
                self._log_and_print(f"✗ Timeout adding checksum for {package_name}@{version}", "error")
                # Add to editing list for manual fixing
                packages_for_editing.append({
                    'package_name': package_name,
                    'version': version,
                    'recipe_path': str(package_dir / "package.py"),
                    'use_local_copy': True,
                    'found_in_local': True,
                    'found_in_remote': False,
                    'operation': 'checksum_timeout'
                })
            except Exception as e:
                self._log_and_print(f"✗ Error adding checksum for {package_name}@{version}: {e}", "error")
                # Add to editing list for manual fixing
                packages_for_editing.append({
                    'package_name': package_name,
                    'version': version,
                    'recipe_path': str(package_dir / "package.py"),
                    'use_local_copy': True,
                    'found_in_local': True,
                    'found_in_remote': False,
                    'operation': 'checksum_error',
                    'error': str(e)
                })
        
        # Clear pending checksums after processing
        self.pending_checksums.clear()
        
        return packages_for_editing

    def create_environment(self, env_name: str, upstream_path: str, 
                          packages: List[Dict], work_dir: str, platform) -> Tuple[str, List[Dict]]:
        """Create a new Spack environment with upstream chaining.
        
        Args:
            env_name: Name of the environment
            upstream_path: Path to upstream installation
            packages: List of package specifications
            work_dir: Working directory for environment creation
            
        Returns:
            Tuple of (path to created environment, list of packages needing manual edit)
            
        Raises:
            RuntimeError: If environment creation fails
        """
        try:
            # Create environment directory in current working directory
            env_path = Path(work_dir) / env_name
            env_path.mkdir(parents=True, exist_ok=True)
            print(f"Creating environment at: {env_path}")
            
            # Setup logging immediately after environment directory creation
            self.setup_logging(str(env_path))
            
            self._log_and_print(f"=== EMC Environment Chainer - Environment Creation Started ===")
            self._log_and_print(f"Environment name: {env_name}")
            self._log_and_print(f"Environment path: {env_path}")
            self._log_and_print(f"Upstream path: {upstream_path}")
            self._log_and_print(f"Work directory: {work_dir}")
            self._log_and_print(f"Packages to install: {[pkg['name'] for pkg in packages]}")

            # Process any pending recipes that were collected during package specification
            packages_needing_edit = self._process_pending_recipes(str(env_path))
            
            # Process any pending Git commit operations (these also create custom recipes)
            git_packages_needing_edit = self._process_pending_git_commits(str(env_path))
            packages_needing_edit.extend(git_packages_needing_edit)
                        
            # Create custom repository structure in the environment if any packages need it
            if packages_needing_edit or self.pending_checksums:
                self._ensure_env_repository(str(env_path))
            
            # Find and copy site/common directories from upstream environment
            upstream_env_path = self._find_upstream_env_path(upstream_path)
            self._copy_site_common_dirs(upstream_env_path, env_path)
            
            # Create spack.yaml configuration by copying and modifying upstream
            self._log_and_print("Creating spack.yaml configuration...")
            spack_yaml = self._create_spack_yaml(upstream_env_path, packages, env_path, packages_needing_edit, platform)
            spack_yaml_path = os.path.join(env_path, "spack.yaml")
            
            with open(spack_yaml_path, 'w') as f:
                f.write(spack_yaml)
            
            # Process any pending checksum operations (must be done after spack.yaml is created)
            checksum_packages_needing_edit = self._process_pending_checksums(str(env_path))
            packages_needing_edit.extend(checksum_packages_needing_edit)
            
            if self.logger:
                self.logger.info(f"Created spack.yaml at: {spack_yaml_path}")
            
            self._log_and_print(f"✓ Created environment directory: {env_path}")
            self._log_and_print(f"✓ Created spack.yaml with upstream: {upstream_path}")
            
            return str(env_path), packages_needing_edit
            
        except Exception as e:
            error_msg = f"Failed to create environment: {e}"
            if self.logger:
                self.logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    def _find_upstream_env_path(self, upstream_install_path: str) -> Path:
        """Find the upstream environment path from the install path.
        
        Args:
            upstream_install_path: Path to upstream installation directory
            
        Returns:
            Path to upstream environment directory
        """
        # upstream_install_path is typically: .../envs/env-name/install/
        # We want: .../envs/env-name/
        install_path = Path(upstream_install_path)
        
        # If the path ends with 'install', remove it
        if install_path.name == 'install':
            return install_path.parent
        else:
            # If it doesn't end with 'install', assume it's already the env path
            return install_path
    
    def _copy_site_common_dirs(self, upstream_env_path: Path, new_env_path: Path):
        """Copy site and common directories from upstream environment.
        
        Args:
            upstream_env_path: Path to upstream environment
            new_env_path: Path to new environment
        """
        import shutil
        
        for dirname in ["site", "common"]:
            upstream_dir = upstream_env_path / dirname
            new_dir = new_env_path / dirname
            
            if upstream_dir.exists():
                if new_dir.exists():
                    shutil.rmtree(new_dir)
                shutil.copytree(upstream_dir, new_dir)
                if self.logger:
                    self.logger.info(f"Copied {dirname} directory from upstream environment")
            else:
                if self.logger:
                    self.logger.info(f"No {dirname} directory found in upstream environment")
    
    def _create_spack_yaml(self, upstream_env_path: str, packages: List[Dict], env_path: Path, packages_needing_edit: List[Dict], platform) -> str:
        """Create spack.yaml content by copying and modifying upstream spack.yaml.
        
        Args:
            upstream_env_path: Path to upstream Spack env
            packages: List of package specifications
            env_path: Path to new environment
            packages_needing_edit: List of packages needing custom recipes
            
        Returns:
            YAML content as string
        """
        # Find upstream environment path and copy spack.yaml
        upstream_spack_yaml = os.path.join(upstream_env_path, "spack.yaml")
        
        if not os.path.exists(upstream_spack_yaml):
            raise RuntimeError(f"Upstream spack.yaml not found at: {upstream_spack_yaml}")
        
        # Initialize ruamel.yaml with comment preservation
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.default_flow_style = False
        
        # Load the upstream spack.yaml
        with open(upstream_spack_yaml, 'r') as f:
            spack_config = yaml.load(f)
        
        if 'spack' not in spack_config:
            spack_config['spack'] = {}
        
        spack_section = spack_config['spack']
        
        # Create specs list from packages
        specs = [self._build_spec_string(pkg) for pkg in packages]
        
        # Add custom repository if needed (at the beginning for priority)
        if packages_needing_edit:
            if 'repos' not in spack_section:
                spack_section['repos'] = []
            # Insert at beginning for highest priority
            if '$env/envrepo' not in spack_section['repos']:
                spack_section['repos'].insert(0, '$env/envrepo')

        if 'definitions' in spack_section:
            definitions_names = [list(x.keys())[0] for x in spack_section['definitions']]
            if len(spack_section['definitions'])==2 and set(definitions_names) == {'compilers', 'packages'}:
                for i in [0,1]:
                    if 'packages' in spack_section['definitions'][i]:
                        spack_section['definitions'][i]['packages'] = []
                        for pkg in packages:
                            if pkg['name'] == 'scotch':
                                spack_section['specs'].append(self._build_spec_string(pkg))
                            elif pkg['name'] not in ['cmake']:
                                spack_section['definitions'][i]['packages'].append(self._build_spec_string(pkg))
            else:
                del(spack_section['definitions'])
                spack_section['specs'] = specs
        else:
            spack_section['specs'] = specs
        
        # Set upstream configuration
        if 'upstreams' not in spack_section:
            spack_section['upstreams'] = {}
        
        # Insert emcenvchainer-upstream as the first entry
        upstream_config = {'install_tree': os.path.join(upstream_env_path, "install")}
        
        # If upstreams already exists and has entries, preserve order with our entry first
        if spack_section['upstreams']:
            # Create a new dict with our entry first
            existing_upstreams = dict(spack_section['upstreams'])
            spack_section['upstreams'].clear()
            spack_section['upstreams']['emcenvchainer-upstream'] = upstream_config
            # Add back existing entries (except if emcenvchainer-upstream already existed)
            for key, value in existing_upstreams.items():
                spack_section['upstreams'][key] = value
        else:
            # No existing entries, just add ours
            spack_section['upstreams']['emcenvchainer-upstream'] = upstream_config
        
        # Set concretizer settings
        if 'concretizer' not in spack_section:
            spack_section['concretizer'] = {}
        spack_section['concretizer']['unify'] = True
        spack_section['concretizer']['reuse'] = True
        
        # Set config settings
        if 'config' not in spack_section:
            spack_section['config'] = {}
        spack_section['config']['deprecated'] = True
        spack_section['config']['build_stage'] = '$env/build_stage'

        # Add package-specific overrides for packages being updated
        if 'packages' not in spack_section:
            spack_section['packages'] = {}
        package_info = self._get_upstream_package_info(upstream_env_path, packages)
        if package_info:            
            for package_name, info in package_info.items():
                version = info.get('version', '')
                variants = info.get('variants', '')
                
                # Use extra colon to override existing package settings
                package_key = f"{package_name}:"
                
                # Add version constraint if available
                if version:
                    if package_key not in spack_section['packages']:
                        spack_section['packages'][package_key] = {}
                    spack_section['packages'][package_key]['version'] = [version]
                
                # Add variant overrides if available
                if variants:
                    if package_key not in spack_section['packages']:
                        spack_section['packages'][package_key] = {}
                    spack_section['packages'][package_key]['variants'] = variants

        # Always set common build deps (cmake, gmake, ...) as non-buildable
        always_upstream_packages = ['cmake', 'gmake', 'ecbuild', 'bison', 'diffutils']
        for pkg_name in always_upstream_packages:
            coloned_name = pkg_name + ":"
            if coloned_name in spack_section['packages']:
                pkg_name = pkg_name + ":"
            elif pkg_name not in spack_section['packages']:
                spack_section['packages'][pkg_name] = {}
            spack_section['packages'][pkg_name]['buildable'] = False

        # Set target by platform config
        cpu_target = platform.config.get('cpu_target', '')
        if cpu_target:
            if self.logger:
                self.logger.info(f"Setting CPU target for all packages: {cpu_target}")
        
            # Set target for all packages
            if 'all' not in spack_section['packages']:
                spack_section['packages']['all'] = {}
            spack_section['packages']['all']['target'] = [cpu_target]

        # Convert back to string
        string_stream = io.StringIO()
        yaml.dump(spack_config, string_stream)
        return string_stream.getvalue()
    
    def _build_spec_string(self, pkg: Dict) -> str:
        """Build Spack spec string from package dictionary.
        
        Args:
            pkg: Package dictionary with name, version, variants
            
        Returns:
            Spack spec string
        """
        spec = pkg["name"]
        
        if pkg.get("version"):
            spec += f"@{pkg['version']}"
        
        if pkg.get("variants"):
            variants = pkg["variants"].strip()
            if variants and not variants.startswith((' ', '+')):
                spec += f" {variants}"
            elif variants:
                spec += variants
        
        return spec
    
    def concretize_environment(self, env_path: str) -> Tuple[bool, str]:
        """Concretize the environment and check for new installations.
        
        Args:
            env_path: Path to environment
            
        Returns:
            Tuple of (success, list of packages to be installed, command output)
        """
        try:
            self._run_spack_command(['-e', env_path, '-C', env_path, 'bootstrap', 'root', os.path.join(env_path, 'bootstrap')])
            self._run_spack_command(['-e', env_path, '-C', env_path, 'bootstrap', 'now'])
            # Run spack concretize using -e flag
            result = self._run_spack_command(['-e', env_path, '-C', env_path, 'concretize'])
            
            concretize_output = result.stdout + result.stderr if result.stdout or result.stderr else ""
            
            if result.returncode == 0:
                return True, concretize_output
            else:
                return False, [f"Concretization failed: {result.stderr}"], concretize_output
                
        except Exception as e:
            return False, [str(e)], ""
    
    def install_environment_interactive(self, env_path: str) -> bool:
        """Install packages in the environment with live output and logging.
        
        Args:
            env_path: Path to environment
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import threading
            import time
            
            cmd = [str(self.spack_exe), '-e', env_path, 'install']
            
            if self.logger:
                self.logger.info(f"Starting interactive spack install: {' '.join(cmd)}")
            
            # Use Popen for real-time output capture and stdin pass-through
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                stdin=sys.stdin,  # Pass through stdin for user interaction
                text=True,
                bufsize=1  # Line buffering
            )
            
            # Capture output in a separate thread while allowing terminal interaction
            output_lines = []
            
            def output_reader():
                """Read output from subprocess and write to both terminal and log."""
                try:
                    while True:
                        line = process.stdout.readline()
                        if not line:
                            break
                        
                        # Write to terminal immediately (preserving user interaction)
                        sys.stdout.write(line)
                        sys.stdout.flush()
                        
                        # Store for logging
                        output_lines.append(line.rstrip())
                        
                        # Log to file if logger is available
                        if self.logger:
                            self.logger.info(f"SPACK: {line.rstrip()}")
                            
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Error in output reader thread: {e}")
            
            # Start the output reading thread
            reader_thread = threading.Thread(target=output_reader, daemon=True)
            reader_thread.start()
            
            # Wait for process to complete
            return_code = process.wait()
            
            # Wait for output thread to finish reading any remaining output
            reader_thread.join(timeout=5.0)
            
            # Log final status
            if self.logger:
                self.logger.info(f"Spack install completed with return code: {return_code}")
                if output_lines:
                    self.logger.info(f"Total output lines captured: {len(output_lines)}")
            
            return return_code == 0
            
        except Exception as e:
            error_msg = f"Error during interactive install: {e}"
            if self.logger:
                self.logger.error(error_msg)
            print(f"Install failed: {e}")
            return False
    
    def refresh_modules(self, env_path: str) -> str:
        """Refresh Lmod modules for the environment.
        
        Args:
            env_path: Path to environment
            
        Returns:
            Path to modulefiles directory
        """
        try:
            self._log_and_print("Refreshing Lmod modules...")

            # Add the ESMF-based suffix for MAPL
            result = self._run_spack_command([
                '-e', env_path, 'config', 'add',
                'modules:default:lmod:mapl::suffixes:^esmf:esmf-{^esmf.version}'
            ])
            if result.returncode != 0:
                error_msg = f"Failed to configure MAPL suffixes: {result.stderr}"
                if self.logger:
                    self.logger.error(error_msg)
                raise RuntimeError(error_msg)

            # Run module refresh equivalent
            result = self._run_spack_command(['-e', env_path, 'module', 'lmod', 'refresh', '--yes-to-all', '--upstream-modules'])
            
            if result.returncode != 0:
                error_msg = f"Module creation failed: {result.stderr}"
                if self.logger:
                    self.logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            self._log_and_print("Setting up meta-modules...")
            
            # Run spack stack setup-meta-modules
            result = self._run_spack_command(['-e', env_path, 'stack', 'setup-meta-modules'])
            
            if result.returncode != 0:
                error_msg = f"Metamodule (stack-* modules) creation failed: {result.stderr}"
                if self.logger:
                    self.logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            # Return modulefiles path
            install_path = Path(env_path) / "install"
            modulefiles_path = install_path / "modulefiles" / "Core"
            
            self._log_and_print(f"✓ Module refresh completed. Modulefiles at: {modulefiles_path}")
            
            return str(modulefiles_path)
                
        except Exception as e:
            error_msg = f"Failed to refresh modules: {e}"
            if self.logger:
                self.logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    def check_package_version_exists(self, package_name: str, version: str) -> bool:
        """Check if a specific package version exists in the current Spack installation.
        
        Args:
            package_name: Name of the package
            version: Version to check
            
        Returns:
            True if version exists, False otherwise
        """
        # Strip whitespace from inputs to be more robust
        package_name = package_name.strip()
        version = version.strip()
        
        # Use spack versions to get all available versions for the package
        result = self._run_spack_command(['versions', '--safe', package_name])
        
        if result.returncode != 0:
            # Package doesn't exist at all
            return False
        
        # Parse the output to find versions
        available_versions = re.split(r"[\n ]+", result.stdout.strip())

        return version in available_versions

    def _fetch_recipe_content(self, package_name: str) -> str:
        """Fetch the recipe content for a package from the remote repository.
        
        Args:
            package_name: Name of the package
            
        Returns:
            Recipe content as string, or None if not found
        """
        try:
            base_url = self.config.get("spack_repository", {}).get("base_url", 
                                      "https://github.com/JCSDA/spack.git")
            
            # Get repository info from config
            repo_config = self.config.get("spack_repository", {})
            
            # Extract org/repo from base_url like "https://github.com/JCSDA/spack.git"
            base_url_parts = base_url.replace("https://github.com/", "").replace(".git", "").split("/")
            git_org = base_url_parts[0]
            git_repo = base_url_parts[1]
            git_branch = repo_config.get("branch", "develop")
            
            # Construct the raw GitHub URL directly
            package_url = f"https://raw.githubusercontent.com/{git_org}/{git_repo}/refs/heads/{git_branch}/var/spack/repos/builtin/packages/{package_name}/package.py"
            
            import requests
            if self.logger:
                self.logger.info(f"Fetching recipe from: {package_url}")
            response = requests.get(package_url, timeout=10)
            
            if response.status_code == 200:
                if self.logger:
                    self.logger.info(f"Successfully fetched recipe for {package_name}")
                return response.text
            else:
                if self.logger:
                    self.logger.warning(f"Failed to fetch recipe: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error fetching recipe for {package_name}: {e}")
            return None

    def _fetch_and_write_package_directory(self, package_name: str, package_dir: Path) -> bool:
        """Copy the entire package directory from the local Spack installation.
        
        Args:
            package_name: Name of the package
            package_dir: Local directory to write package files to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use spack location --package-dir to find the local package directory
            result = self._run_spack_command(['location', '--package-dir', package_name])
            
            if result.returncode != 0:
                print(f"  Package {package_name} not found in local Spack installation")
                return False
            
            local_package_dir = Path(result.stdout.strip())
            if not local_package_dir.exists():
                if self.logger:
                    self.logger.error(f"Local package directory not found: {local_package_dir}")
                return False
            
            if self.logger:
                self.logger.info(f"Copying package directory from: {local_package_dir}")
                self.logger.info(f"Copying to: {package_dir}")
            
            # Remove the target directory if it exists
            if package_dir.exists():
                shutil.rmtree(package_dir)
            
            # Copy the entire directory tree, excluding Python cache files
            shutil.copytree(
                local_package_dir, 
                package_dir,
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc')
            )
            
            # Count what was copied
            copied_files = list(package_dir.rglob('*'))
            file_count = len([f for f in copied_files if f.is_file()])
            dir_count = len([f for f in copied_files if f.is_dir()])
            
            if self.logger:
                self.logger.info(f"Successfully copied {file_count} files and {dir_count} directories")
            return True
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error copying package directory for {package_name}: {e}")
            return False


    def check_version_in_remote_repo(self, package_name: str, version: str, base_url: str = None) -> bool:
        """Check if a package version exists in the remote Spack repository.
        
        Args:
            package_name: Name of the package
            version: Version to check
            base_url: Base URL of Spack repository
            
        Returns:
            True if version might be available, False otherwise
        """
        if not base_url:
            base_url = self.config.get("spack_repository", {}).get("base_url", 
                                      "https://github.com/JCSDA/spack.git")
        
        try:
            # Get repository info from config
            repo_config = self.config.get("spack_repository", {})
            
            # Extract org/repo from base_url like "https://github.com/JCSDA/spack.git"
            base_url_parts = base_url.replace("https://github.com/", "").replace(".git", "").split("/")
            git_org = base_url_parts[0]
            git_repo = base_url_parts[1]
            git_branch = repo_config.get("branch", "develop")
            
            # Construct the raw GitHub URL directly
            package_url = f"https://raw.githubusercontent.com/{git_org}/{git_repo}/refs/heads/{git_branch}/var/spack/repos/builtin/packages/{package_name}/package.py"
            
            # Try to fetch the package.py file
            import requests
            response = requests.get(package_url, timeout=10)
            
            if response.status_code == 200:
                # Check if the version appears in the package.py content
                content = response.text
                
                # Simple heuristic: look for version strings
                version_found = f'"{version}"' in content or f"'{version}'" in content
                if version_found:
                    return True
                else:
                    return False
            else:
                return False
                
        except Exception as e:
            return False
    
    def add_package_version(self, package_name: str, version: str, env_path: str = None, offer_editor: bool = False) -> Tuple[bool, str, str]:
        """Add a new version to a package using Spack's built-in capabilities.
        
        Args:
            package_name: Name of the package
            version: Version to add
            env_path: Environment path where custom repo should be created
            offer_editor: Whether to offer $EDITOR for manual editing
            
        Returns:
            Tuple of (success, message, recipe_path)
        """
        try:
            # Create custom repository in environment directory
            repo_path = self._ensure_env_repository(env_path)
            
            # Check if the package already exists in the custom repo
            custom_package_dir = Path(repo_path) / "packages" / package_name
            
            if not custom_package_dir.exists():
                # Copy the package from the main repository
                success, message = self._copy_package_to_custom_repo(package_name, repo_path)
                if not success:
                    return False, message, ""
            
            # Add the new version using spack checksum
            package_py_path = custom_package_dir / "package.py"
            success, message = self._add_version_to_package(package_name, version, str(package_py_path))
            
            if success:
                return True, f"Version {version} added to {package_name}", str(package_py_path)
            else:
                return False, message, str(package_py_path)
                
        except Exception as e:
            return False, f"Failed to add package version: {e}", ""
    
    def _ensure_env_repository(self, env_path: str) -> str:
        """Ensure custom repository exists in environment directory.
        
        Args:
            env_path: Path to the Spack environment
            
        Returns:
            Path to the repository
        """
        # Create repository directory in environment
        env_dir = Path(env_path)
        repo_path = env_dir / "envrepo"
        repo_path.mkdir(parents=True, exist_ok=True)
        
        # Create repo.yaml if it doesn't exist
        repo_yaml = repo_path / "repo.yaml"
        if not repo_yaml.exists():
            with open(repo_yaml, 'w') as f:
                f.write(f"""repo:
  namespace: envrepo
""")
        
        # Create packages directory
        packages_dir = repo_path / "packages"
        packages_dir.mkdir(exist_ok=True)
        
        return str(repo_path)

    
    def _copy_package_to_custom_repo(self, package_name: str, repo_path: str) -> Tuple[bool, str]:
        """Copy a package from the main Spack repository to the custom repository.
        
        Args:
            package_name: Name of the package to copy
            repo_path: Path to the custom repository
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Find the original package
            result = self._run_spack_command(['location', '-p', package_name])
            
            if result.returncode != 0:
                return False, f"Package {package_name} not found in main repository"
            
            original_package_dir = Path(result.stdout.strip())
            if not original_package_dir.exists():
                return False, f"Original package directory not found: {original_package_dir}"
            
            # Copy to custom repository
            custom_package_dir = Path(repo_path) / "packages" / package_name
            custom_package_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy package.py file
            original_package_py = original_package_dir / "package.py"
            custom_package_py = custom_package_dir / "package.py"
            
            if original_package_py.exists():
                shutil.copy2(original_package_py, custom_package_py)
                return True, f"Package {package_name} copied to custom repository"
            else:
                return False, f"Original package.py not found: {original_package_py}"
                
        except Exception as e:
            return False, f"Failed to copy package: {e}"
    
    def _add_version_to_package(self, package_name: str, version: str, package_py_path: str) -> Tuple[bool, str]:
        """Add a version to a package.py file.
        
        Args:
            package_name: Name of the package
            version: Version to add
            package_py_path: Path to the package.py file
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Use spack checksum to add the version
            # This will automatically fetch checksums and update the package
            result = self._run_spack_command(['checksum', package_name, version])
            
            if result.returncode == 0:
                return True, f"Version {version} added with checksum"
            else:
                # If automatic checksum fails, we can add it manually with a placeholder
                return self._manually_add_version(version, package_py_path)
                
        except Exception as e:
            return False, f"Failed to add version: {e}"
    
    def _manually_add_version(self, version: str, package_py_path: str) -> Tuple[bool, str]:
        """Manually add a version to package.py file.
        
        Args:
            version: Version to add
            package_py_path: Path to the package.py file
            
        Returns:
            Tuple of (success, message)
        """
        try:
            with open(package_py_path, 'r') as f:
                content = f.read()
            
            # Find the version section and add the new version
            lines = content.split('\n')
            new_lines = []
            in_version_section = False
            version_added = False
            
            for line in lines:
                stripped = line.strip()
                
                # Look for version declarations
                if 'version(' in stripped and not version_added:
                    new_lines.append(line)
                    # Add the new version after the first version declaration
                    indent = len(line) - len(line.lstrip())
                    new_version_line = ' ' * indent + f'version("{version}", sha256="PLACEHOLDER_CHECKSUM")'
                    new_lines.append(new_version_line)
                    version_added = True
                else:
                    new_lines.append(line)
            
            if version_added:
                with open(package_py_path, 'w') as f:
                    f.write('\n'.join(new_lines))
                return True, f"Version {version} added manually (checksum needs to be updated)"
            else:
                return False, "Could not find version section in package.py"
                
        except Exception as e:
            return False, f"Failed to manually add version: {e}"
    
    
    def offer_package_edit(self, packages_to_edit: List[Dict]) -> bool:
        """Launch editors for packages that need manual editing.
        
        Args:
            packages_to_edit: List of package info dictionaries (user has already confirmed editing)
            
        Returns:
            True if all editing completed successfully, False if any editor failed
        """
        if not packages_to_edit:
            return True
            
        import subprocess
        import os
        
        print(f"\nLaunching editors for {len(packages_to_edit)} package(s)...")
        
        for pkg in packages_to_edit:
            package_name = pkg['package_name']
            version = pkg['version']
            recipe_path = pkg['recipe_path']
            
            print(f"\nEditing recipe for {package_name}@{version}")
            print(f"Recipe path: {recipe_path}")
            
            try:
                editor = os.environ.get('EDITOR', 'nano')
                print(f"Opening {editor}...")
                
                # Split editor command to handle arguments (e.g., "vim -n", "code --wait")
                import shlex
                try:
                    editor_cmd = shlex.split(editor) + [recipe_path]
                except ValueError:
                    # Fallback to simple split if shlex fails
                    editor_cmd = editor.split() + [recipe_path]
                
                subprocess.run(editor_cmd, check=True)
                print(f"✓ Finished editing {package_name}@{version}")
                
            except subprocess.CalledProcessError:
                print(f"✗ Editor failed for {package_name}@{version}")
                return False
            except Exception as e:
                print(f"✗ Error opening editor: {e}")
                return False
        
        print("\n✓ Manual recipe editing phase completed.")
        return True
    
    def get_local_package_path(self, package_name: str) -> str:
        """Get the local path to a package's package.py file.
        
        Args:
            package_name: Name of the package
            
        Returns:
            Path to the package.py file
        """
        # Standard Spack package path structure
        return str(self.spack_root / "var" / "spack" / "repos" / "builtin" / "packages" / package_name / "package.py")

    def add_pending_git_commit(self, package_name: str, version: str, commit_hash: str):
        """Add a Git commit version operation to be performed when environment is created.
        
        Args:
            package_name: Name of the package
            version: Version to add
            commit_hash: Git commit hash
        """
        git_commit_info = {
            'package_name': package_name,
            'version': version,
            'commit_hash': commit_hash
        }
        self.pending_git_commits.append(git_commit_info)
        print(f"Added {package_name}@{version} (commit: {commit_hash[:8]}...) to pending Git commits")

    def _process_pending_git_commits(self, env_path: str) -> List[Dict]:
        """Process all pending Git commit operations.
        
        Args:
            env_path: Path to the environment
            
        Returns:
            List of packages that were processed and need manual editing
        """
        if not self.pending_git_commits:
            return []
            
        self._log_and_print(f"Processing {len(self.pending_git_commits)} pending Git commit operation(s)...")
        
        # Get the environment repository path
        repo_path = Path(env_path) / "envrepo"
        packages_dir = repo_path / "packages"
        
        packages_for_editing = []
        
        for git_commit_info in self.pending_git_commits:
            package_name = git_commit_info['package_name']
            version = git_commit_info['version']
            commit_hash = git_commit_info['commit_hash']
            
            try:
                self._log_and_print(f"Adding Git commit version for {package_name}@{version} (commit: {commit_hash[:8]}...)")
                
                # Create package directory if it doesn't exist
                package_dir = packages_dir / package_name
                package_dir.mkdir(parents=True, exist_ok=True)
                
                package_py_path = package_dir / "package.py"
                
                # First, copy the recipe from local installation
                success = self._fetch_and_write_package_directory(package_name, package_dir)
                if not success:
                    # If that fails, try to get it from remote
                    recipe_content = self._fetch_recipe_content(package_name)
                    if recipe_content:
                        # Remove newer type hinting that breaks with spack-stack 1.9 and before
                        recipe_content = recipe_content.replace(": EnvironmentModifications", "")
                        with open(package_py_path, 'w') as f:
                            f.write(recipe_content)
                        self._log_and_print(f"  ✓ Fetched recipe from remote repository for {package_name}")
                    else:
                        self._log_and_print(f"  ✗ Could not obtain recipe for {package_name}", "error")
                        continue
                
                # Add the Git commit version to the recipe
                success = self._add_git_commit_version_to_recipe(package_py_path, version, commit_hash)
                
                if success:
                    self._log_and_print(f"  ✓ Added Git commit version {version} (commit: {commit_hash[:8]}...) to {package_name}")
                    # Add to packages for editing
                    packages_for_editing.append({
                        'package_name': package_name,
                        'version': version,
                        'recipe_path': str(package_py_path),
                        'use_local_copy': True,
                        'found_in_local': True,
                        'found_in_remote': False,
                        'operation': 'git_commit',
                        'commit_hash': commit_hash
                    })
                else:
                    self._log_and_print(f"  ✗ Failed to add Git commit version to {package_name}", "error")
                    
            except Exception as e:
                self._log_and_print(f"  ✗ Error processing Git commit for {package_name}@{version}: {e}", "error")
        
        # Clear pending git commits after processing
        self.pending_git_commits.clear()
        
        return packages_for_editing

    def _add_git_commit_version_to_recipe(self, package_py_path: Path, version: str, commit_hash: str) -> bool:
        """Add a Git commit version to a package.py file.
        
        Args:
            package_py_path: Path to the package.py file
            version: Version to add
            commit_hash: Git commit hash
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(package_py_path, 'r') as f:
                content = f.read()
            
            # Find the version section and add the new version
            lines = content.split('\n')
            new_lines = []
            version_added = False
            
            for line in lines:
                stripped = line.strip()
                
                # Look for version declarations
                if 'version(' in stripped and not version_added:
                    new_lines.append(line)
                    # Add the new version after the first version declaration
                    indent = len(line) - len(line.lstrip())
                    new_version_line = ' ' * indent + f'version("{version}", commit="{commit_hash}")'
                    new_lines.append(new_version_line)
                    version_added = True
                else:
                    new_lines.append(line)
            
            if version_added:
                with open(package_py_path, 'w') as f:
                    f.write('\n'.join(new_lines))
                return True
            else:
                # If no version declarations found, try to add after the class definition
                new_lines = []
                class_found = False
                
                for line in lines:
                    new_lines.append(line)
                    if 'class ' in line and '(Package)' in line and not class_found:
                        class_found = True
                        # Add version after class definition
                        indent = '    '  # Standard indentation
                        new_lines.append('')
                        new_lines.append(f'{indent}version("{version}", commit="{commit_hash}")')
                        version_added = True
                        break
                
                if version_added:
                    with open(package_py_path, 'w') as f:
                        f.write('\n'.join(new_lines))
                    return True
                else:
                    return False
                    
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error modifying recipe: {e}")
            return False

    def _fetch_and_write_all_remote_files(self, package_name: str, package_dir: Path):
        """Fetch and write all supporting files for a package from the remote repository."""
        try:
            base_url = self.config.get("spack_repository", {}).get("base_url", "https://github.com/JCSDA/spack.git")
            repo_config = self.config.get("spack_repository", {})
            base_url_parts = base_url.replace("https://github.com/", "").replace(".git", "").split("/")
            git_org = base_url_parts[0]
            git_repo = base_url_parts[1]
            git_branch = repo_config.get("branch", "develop")
            import requests
            api_url = f"https://api.github.com/repos/{git_org}/{git_repo}/contents/var/spack/repos/builtin/packages/{package_name}"
            api_params = {"ref": git_branch}
            response = requests.get(api_url, params=api_params, timeout=10)
            if response.status_code == 200:
                files_data = response.json()
                for file_info in files_data:
                    if file_info["type"] == "file" and file_info["name"] != "package.py":
                        file_url = file_info["download_url"]
                        file_path = package_dir / file_info["name"]
                        file_response = requests.get(file_url, timeout=10)
                        if file_response.status_code == 200:
                            with open(file_path, 'wb') as f:
                                f.write(file_response.content)
                            if self.logger:
                                self.logger.info(f"Downloaded supporting file: {file_info['name']}")
            elif response.status_code == 404:
                if self.logger:
                    self.logger.info(f"Package directory not found in remote repository (this is normal for new packages)")
            else:
                if self.logger:
                    self.logger.warning(f"Failed to list files: HTTP {response.status_code}")
                
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Could not fetch all remote files for {package_name}: {e}")
    
    def _get_upstream_package_info(self, upstream_env_path: Path, packages: List[Dict]) -> Dict[str, Dict[str, str]]:
        """Get version and variants (except 'patches') for packages from the upstream environment.
        
        Args:
            upstream_env_path: Path to upstream environment directory
            packages: List of package specifications being added
            
        Returns:
            Dictionary mapping package names to their info dictionaries with 'version' and 'variants' keys
        """
        package_info = {}
        
        for pkg in packages:
            package_name = pkg["name"]
            
            try:
                SPACK_STACK_DIR = os.path.abspath(os.path.join(upstream_env_path, "../../"))
                # Use spack find with format to get both version and variants from upstream environment
                result = self._run_spack_command([
                    '-e', str(upstream_env_path), 
                    'find', 
                    '--format', '{version}:VARIANTS:{variants}', 
                    package_name
                ], vars={"SPACK_STACK_DIR": SPACK_STACK_DIR})

                if result.returncode == 0 and result.stdout.strip():
                    # Take the first line in case there are multiple copies
                    info_line = result.stdout.strip().split('\n')[0]
                    
                    # Parse the output format: version<VARIANTS>variants
                    if info_line and info_line.strip():
                        info_line = info_line.strip()
                        
                        # Split on the delimiter to get version and variants
                        version, variants = info_line.split(":VARIANTS:")
                        variants = re.sub(r"patches=[\w,]+", "", variants).strip()
                        
                        # Store the info for this package
                        package_info[package_name] = {
                            'variants': variants,
                        }

                        # Use version from modulefile in case of multiple versions in upstream env.
                        if 'current_version' in pkg:
                            package_info[package_name]['version'] = pkg['current_version']
                        
                        if self.logger:
                            self.logger.info(f"Found upstream info for {package_name}: version={version}, variants={variants}")
                    else:
                        if self.logger:
                            self.logger.warning(f"No info found for {package_name} in upstream environment")
                else:
                    if self.logger:
                        self.logger.warning(f"Package {package_name} not found in upstream environment")
                    
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Could not retrieve info for {package_name}: {e}")
 
        return package_info
