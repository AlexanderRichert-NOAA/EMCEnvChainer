"""Model application management."""

import os
import re
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


class ModelApplication:
    """Represents a model application with its module file."""
    
    def __init__(self, name: str, config: Dict, platform_name: str, selected_module_url: str = None):
        """Initialize model application.
        
        Args:
            name: Application name
            config: Application configuration
            platform_name: Platform name for URL template
            selected_module_url: Specific module URL to use (if None, will need selection)
        """
        self.name = name
        self.config = config
        self.platform_name = platform_name
        self.selected_module_url = selected_module_url
        self._module_content = None
        self._install_path = None
        self._dependencies = None

    @property
    def module_urls(self) -> List[str]:
        """Get all available module URLs for this platform."""
        return self.config.get("module_url_templates", [])

    @property
    def module_url(self) -> str:
        """Get the selected module URL for this platform."""
        if self.selected_module_url:
            return self.selected_module_url
        urls = self.module_urls
        if urls:
            return urls[0]  # Default to first URL if none selected
        return ""
    
    @property
    def install_path_regex(self) -> str:
        """Get the regex pattern for extracting install path."""
        return self.config.get("install_path_regex", "")
    
    def download_module_file(self) -> str:
        """Download and return the module file content.
        
        Returns:
            Module file content as string
            
        Raises:
            RuntimeError: If download fails
        """
        if self._module_content is not None:
            return self._module_content
        
        try:
            response = requests.get(self.module_url, timeout=30)
            response.raise_for_status()
            self._module_content = response.text
            return self._module_content
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to download module file from {self.module_url}: {e}")
    
    def extract_install_path(self) -> Optional[str]:
        """Extract installation path from module file.
        
        Returns:
            Installation path if found, None otherwise
        """
        if self._install_path is not None:
            return self._install_path
        
        if not self.install_path_regex:
            return None
        
        module_content = self.download_module_file()
        match = re.search(self.install_path_regex, module_content)
        if match:
            self._install_path = match.group(1)
            return self._install_path
        
        return None
    
    def parse_dependencies(self) -> List[Dict]:
        """Parse package dependencies from module file.
        
        Returns:
            List of package dictionaries with name, version, and variants
        """
        if self._dependencies is not None:
            return self._dependencies
        
        self._dependencies = []
        
        module_content = self.download_module_file()
        
        # Pattern handlers with specific logic for each pattern type
        pattern_handlers = {
            'depends_on': {
                'pattern': r'depends_on\("([^@]+)@([^"]+)"\)',
                'handler': self._handle_depends_on_pattern
            },
            'load_unified': {
                'pattern': r'load\((?:pathJoin\("([^"]+)",\s*([^)]+)\)|\"([^\"]+)\")\)',
                'handler': self._handle_unified_load_pattern
            },
            'version_variable': {
                'pattern': r'([a-zA-Z0-9_]+)_ver\s*=\s*os\.getenv\("[^"]+"\)\s*or\s*"([^"]+)"',
                'handler': self._handle_version_variable_pattern
            }
        }
        
        for handler_name, config in pattern_handlers.items():
            matches = re.finditer(config['pattern'], module_content, re.MULTILINE)
            for match in matches:
                result = config['handler'](match, module_content)
                if result:
                    package_name, version = result
                    # Clean version to remove ESMF suffixes
                    version = re.sub(r'-esmf-.*', '', version)
                    
                    if self._is_valid_package(package_name, version):
                        self._dependencies.append({
                            "name": package_name,
                            "version": version,
                            "variants": "",
                            "raw_match": match.group(0)
                        })
        
        # Remove duplicates
        seen = set()
        unique_deps = []
        for dep in self._dependencies:
            key = (dep["name"], dep["version"])
            if key not in seen:
                seen.add(key)
                unique_deps.append(dep)
        
        self._dependencies = unique_deps
        return self._dependencies

    def _handle_depends_on_pattern(self, match, module_content):
        """Handle depends_on("package@version") patterns."""
        package_name = match.group(1).lower()
        version = match.group(2)
        return (package_name, version)

    def _handle_unified_load_pattern(self, match, module_content):
        """Handle both load("package/version") and load(pathJoin("package", version_var)) patterns."""
        # Check if this is a pathJoin pattern (groups 1 and 2) or simple pattern (group 3)
        if match.group(1) is not None:  # pathJoin pattern
            package_name = match.group(1).lower()
            version_var = match.group(2).strip()
            
            # Skip stack-* packages and ufs_common
            if package_name.startswith("stack-") or package_name in ["ufs_common", "zlib"]:
                return None
            
            # Try to find the version by looking for the variable definition
            version_pattern = f'{version_var.replace("_ver", "")}_ver\\s*=.*?"([^"]+)"'
            version_match = re.search(version_pattern, module_content)
            if version_match:
                version = version_match.group(1)
                return (package_name, version)
            
            return None
        else:  # Simple load pattern
            full_spec = match.group(3).lower()
            
            # Skip anything containing ufs_common or stack
            if any([x in full_spec for x in ["ufs_common", "stack-", "zlib"]]):
                return None
            
            if '/' in full_spec:
                parts = full_spec.split('/')
                package_name = parts[0]
                version = parts[1] if len(parts) > 1 else None
                if version:
                    return (package_name, version)
            
            return None

    def _handle_version_variable_pattern(self, match, module_content):
        """Handle package_ver=os.getenv("package_ver") or "version" patterns."""
        raw_package_name = match.group(1).lower().replace("_ver", "")
        version = match.group(2)
        
        # Skip stack-* packages and ufs_common
        if (raw_package_name.startswith("stack") or 
            raw_package_name == "ufs_common" or 
            "ufs_common" in raw_package_name or
            raw_package_name in ["stack_intel", "stack_impi"]):
            return None
        
        return (raw_package_name, version)

    def _is_valid_package(self, package_name, version):
        """Check if a package name and version are valid."""
        return (package_name and 
                version and
                version != "unknown" and 
                not version.endswith("_ver") and  # Filter out unresolved version variables
                len(package_name) > 2 and  # Filter out very short names
                not package_name[0].isdigit() and  # Filter out names starting with digits
                package_name != "ufs_common" and
                not package_name.startswith("stack"))

    def get_module_url_choices(self) -> List[Dict]:
        """Get module URL choices with user-friendly names.
        
        Returns:
            List of dicts with 'name' and 'url' keys
        """
        choices = []
        urls = self.module_urls
        
        for url in urls:
            # Extract compiler/variant info from URL
            name = self._extract_url_description(url)
            choices.append({
                'name': name,
                'url': url
            })
        
        return choices
    
    def _extract_url_description(self, url: str) -> str:
        """Extract a user-friendly description from a module URL.
        
        Args:
            url: Module file URL
            
        Returns:
            User-friendly description
        """
        # Extract filename from URL
        filename = urlparse(url).path.split('/')[-1]
        
        # Remove .lua extension
        base_name = filename.replace('.lua', '')
        
        # Extract platform and compiler info
        # Format is typically: platform.compiler.lua
        parts = base_name.split('.')
        if len(parts) >= 2:
            platform = parts[0]
            compiler = parts[1] if len(parts) > 1 else "default"
            return f"{platform} ({compiler.upper()})"
        else:
            return base_name.title()

    def get_upgradable_packages(self) -> List[Dict]:
        """Get list of upgradable packages from the common module file.
        
        Returns:
            List of dictionaries with package name and current version
        """
        # Return empty list if no common module URL is defined
        common_module_url = self.config.get("common_module_url")
        if not common_module_url:
            return []
            
        # Download the common module file
        response = requests.get(common_module_url, timeout=30)
        response.raise_for_status()
        common_module_content = response.text
        
        # Parse the common module to find package specifications
        upgradable_packages = []
        
        # Pattern handlers for upgradable packages
        pattern_handlers = {
            'ufs_table': {
                'pattern': r'\{\["([^"]+)"\]\s*=\s*"([^"]+)"\}',
                'handler': self._handle_ufs_table_pattern
            },
            'load_with_version': {
                'pattern': r'load\("([^/]+)/([^"]+)"\)',
                'handler': self._handle_simple_load_version_pattern
            },
            'pathjoin_load': {
                'pattern': r'load\(pathJoin\("([^"]+)",\s*([^)]+)\)\)',
                'handler': self._handle_pathjoin_upgradable_pattern
            },
            'version_variable': {
                'pattern': r'([a-zA-Z0-9_-]+)_ver\s*=\s*os\.getenv\("[^"]+"\)\s*or\s*"([^"]+)"',
                'handler': self._handle_version_variable_pattern
            },
            'local_version': {
                'pattern': r'local\s+([a-zA-Z0-9_-]+)_ver(?:sion)?\s*=\s*"([^"]+)"',
                'handler': self._handle_local_version_pattern
            }
        }
        
        for handler_name, config in pattern_handlers.items():
            matches = re.finditer(config['pattern'], common_module_content, re.MULTILINE)
            for match in matches:
                result = config['handler'](match, common_module_content)
                if result:
                    package_name, version = result
                    # Clean version to remove ESMF suffixes
                    version = re.sub(r'-esmf-.*', '', version)
                    
                    if self._is_valid_upgradable_package(package_name, version):
                        upgradable_packages.append({
                            "name": package_name,
                            "version": version,
                        })
        
        # Remove duplicates by package name
        seen = set()
        unique_packages = []
        for pkg in upgradable_packages:
            if pkg["name"] not in seen:
                seen.add(pkg["name"])
                unique_packages.append(pkg)
        
        return unique_packages

    def _handle_simple_load_version_pattern(self, match, module_content):
        """Handle load("package/version") patterns for upgradable packages."""
        package_name = match.group(1).lower()
        version = match.group(2)
        return (package_name, version)

    def _handle_ufs_table_pattern(self, match, module_content):
        """Handle UFS table format: {["package"] = "version"}."""
        package_name = match.group(1).lower()
        version = match.group(2)
        return (package_name, version)

    def _handle_pathjoin_upgradable_pattern(self, match, module_content):
        """Handle pathJoin pattern for upgradable packages."""
        package_name = match.group(1).lower()
        version_var = match.group(2).strip()
        # Try to find the version definition
        version_pattern = f'{version_var.replace("_ver", "")}_ver\\s*=.*?"([^"]+)"'
        version_match = re.search(version_pattern, module_content)
        version = version_match.group(1) if version_match else None
        if version:
            return (package_name, version)
        return None

    def _handle_local_version_pattern(self, match, module_content):
        """Handle local package_version = "version" patterns."""
        package_name = match.group(1).lower()
        # Clean up package name
        package_name = package_name.replace("_version", "").replace("_ver", "")
        version = match.group(2)
        return (package_name, version)

    def _is_valid_upgradable_package(self, package_name, version):
        """Check if a package name and version are valid for upgradable packages."""
        return (package_name and 
                version and
                not package_name.startswith("stack") and
                package_name != "ufs_common" and
                len(package_name) > 1 and
                not package_name[0].isdigit() and
                not ("-" in package_name and package_name.split("-")[0].isdigit()) and
                re.match(r'^[0-9]', version))
        

class ModelApplicationManager:
    """Manages model applications for a platform."""
    
    def __init__(self, platform_config: Dict, platform_name: str):
        """Initialize model application manager.
        
        Args:
            platform_config: Platform configuration
            platform_name: Platform name
        """
        self.platform_config = platform_config
        self.platform_name = platform_name
        self._applications = None
    
    @property
    def applications(self) -> List[ModelApplication]:
        """Get list of available model applications."""
        if self._applications is None:
            self._applications = []
            app_configs = self.platform_config.get("model_applications", {})
            
            for app_name, app_config in app_configs.items():
                app = ModelApplication(app_name, app_config, self.platform_name)
                self._applications.append(app)
        
        return self._applications

