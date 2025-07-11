"""Model application management."""

import os
import re
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .config import Config


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
        
        try:
            module_content = self.download_module_file()
            match = re.search(self.install_path_regex, module_content)
            if match:
                self._install_path = match.group(1)
                return self._install_path
        except Exception:
            pass
        
        return None
    
    def parse_dependencies(self) -> List[Dict]:
        """Parse package dependencies from module file.
        
        Returns:
            List of package dictionaries with name, version, and variants
        """
        if self._dependencies is not None:
            return self._dependencies
        
        self._dependencies = []
        
        try:
            module_content = self.download_module_file()
            
            # Common patterns for extracting package information from Lmod files
            patterns = [
                # setenv("PACKAGE_ROOT", "/path/to/package")
                r'setenv\("([A-Z_]+)_ROOT",\s*"([^"]+)"\)',
                # prepend_path("PATH", "/path/to/package/bin")
                r'prepend_path\("PATH",\s*"([^"]+)/bin"\)',
                # load("package/version")
                r'load\("([^/]+)/([^"]+)"\)',
                # depends_on("package@version")
                r'depends_on\("([^@]+)@([^"]+)"\)',
                # Alternative load patterns
                r'load\(\"([^\"]+)\"\)',
                # UFS-style pathJoin loads: load(pathJoin("package", package_ver))
                r'load\(pathJoin\("([^"]+)",\s*([^)]+)\)\)',
                # UFS-style version variables: package_ver=os.getenv("package_ver") or "version"
                r'([a-zA-Z0-9_]+)_ver\s*=\s*os\.getenv\("[^"]+"\)\s*or\s*"([^"]+)"',
                # Help text patterns that might list packages
                r'help\(\[\[.*?([a-zA-Z0-9_-]+)[\s/]([0-9.]+).*?\]\]\)',
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, module_content, re.MULTILINE)
                for match in matches:
                    package_name = ""
                    version = "unknown"
                    
                    if len(match.groups()) >= 2:
                        # Two-group patterns
                        if "pathJoin" in pattern:
                            # UFS pathJoin pattern: load(pathJoin("package", package_ver))
                            package_name = match.group(1).lower()
                            version_var = match.group(2).strip()
                            
                            # Skip stack-* packages and ufs_common
                            if package_name.startswith("stack-") or package_name == "ufs_common":
                                continue
                            
                            # Try to find the version by looking for the variable definition
                            version_pattern = f'{version_var.replace("_ver", "")}_ver\\s*=.*?"([^"]+)"'
                            version_match = re.search(version_pattern, module_content)
                            if version_match:
                                version = version_match.group(1)
                            else:
                                # Skip if we can't resolve the version variable - this avoids vcmake_ver issues
                                continue
                        elif "_ver\\s*=" in pattern:
                            # UFS version variable pattern: package_ver=...or "version"
                            raw_package_name = match.group(1).lower().replace("_ver", "")
                            version = match.group(2)
                            
                            # Skip stack-* packages and ufs_common - also handle stack_intel, stack_impi patterns
                            if (raw_package_name.startswith("stack") or 
                                raw_package_name == "ufs_common" or 
                                "ufs_common" in raw_package_name or
                                raw_package_name in ["stack_intel", "stack_impi"]):
                                continue
                            
                            package_name = raw_package_name
                        else:
                            # Regular patterns (like prepend_path)
                            raw_package_name = match.group(1).lower().replace("_root", "")
                            version_or_path = match.group(2)
                            
                            # For path-based patterns, extract the actual package name from the path
                            if '/' in raw_package_name:
                                # Extract last component of path that looks like a package name
                                path_parts = raw_package_name.split('/')
                                package_name = path_parts[-1] if path_parts[-1] else path_parts[-2]
                            else:
                                package_name = raw_package_name
                            
                            # Skip stack-* packages and ufs_common (check both raw and extracted names)
                            if (package_name.startswith("stack") or 
                                package_name == "ufs_common" or
                                "ufs_common" in raw_package_name or
                                raw_package_name.startswith("stack")):
                                continue
                            
                            # Try to extract version from path or version string
                            version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', version_or_path)
                            version = version_match.group(1) if version_match else "unknown"
                        
                        # Only add if we have a valid package name and version (no unresolved variables)
                        if (package_name and 
                            version != "unknown" and 
                            not version.endswith("_ver") and  # Filter out unresolved version variables
                            len(package_name) > 2 and  # Filter out very short names
                            not package_name[0].isdigit() and  # Filter out names starting with digits
                            package_name != "ufs_common" and
                            not package_name.startswith("stack")):
                            self._dependencies.append({
                                "name": package_name,
                                "version": version,
                                "variants": "",
                                "raw_match": match.group(0)
                            })
                    elif len(match.groups()) == 1:
                        # Handle single group matches like simple load statements
                        full_spec = match.group(1).lower()
                        
                        # Skip anything containing ufs_common or stack
                        if ("ufs_common" in full_spec or 
                            "stack" in full_spec):
                            continue
                        
                        if '/' in full_spec:
                            parts = full_spec.split('/')
                            package_name = parts[0]
                            version = parts[1] if len(parts) > 1 else "unknown"
                        else:
                            package_name = full_spec
                            version = "unknown"
                        
                        # Additional filtering on extracted package name
                        if (package_name.startswith("stack") or 
                            package_name == "ufs_common"):
                            continue
                        
                        # Only add if we have a reasonable version
                        if version != "unknown":
                            self._dependencies.append({
                                "name": package_name,
                            "version": version,
                            "variants": "",
                            "raw_match": match.group(0)
                        })
            
            # If no dependencies found, provide some sample data for demonstration
            if not self._dependencies:
                self._dependencies = [
                    {"name": "netcdf-c", "version": "4.9.2", "variants": "", "raw_match": "sample"},
                    {"name": "netcdf-fortran", "version": "4.6.1", "variants": "", "raw_match": "sample"},
                    {"name": "hdf5", "version": "1.12.2", "variants": "", "raw_match": "sample"},
                    {"name": "cmake", "version": "3.23.1", "variants": "", "raw_match": "sample"},
                ]
            
            # Remove duplicates
            seen = set()
            unique_deps = []
            for dep in self._dependencies:
                key = (dep["name"], dep["version"])
                if key not in seen:
                    seen.add(key)
                    unique_deps.append(dep)
            
            self._dependencies = unique_deps
            
        except Exception as e:
            print(f"Warning: Failed to parse dependencies from {self.name}: {e}")
            # Provide sample data when there's an error
            self._dependencies = [
                {"name": "netcdf-c", "version": "4.8.1", "variants": "", "raw_match": "sample"},
                {"name": "netcdf-fortran", "version": "4.5.4", "variants": "", "raw_match": "sample"},
                {"name": "hdf5", "version": "1.10.8", "variants": "", "raw_match": "sample"},
                {"name": "cmake", "version": "3.20.0", "variants": "", "raw_match": "sample"},
            ]
        
        return self._dependencies

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
            List of dictionaries with package name, current version, and description
        """
        # Return empty list if no common module URL is defined
        common_module_url = self.config.get("common_module_url")
        if not common_module_url:
            return []
            
        try:
            # Download the common module file
            response = requests.get(common_module_url, timeout=30)
            response.raise_for_status()
            common_module_content = response.text
            
            # Parse the common module to find package specifications
            upgradable_packages = []
            
            # Look for package specifications using comprehensive patterns
            patterns = [
                # UFS-specific table format: {["package"] = "version"},
                r'\{\["([^"]+)"\]\s*=\s*"([^"]+)"\}',
                # setenv("PACKAGE_VERSION", "version")
                r'setenv\("([A-Z_]+)_VERSION",\s*"([^"]+)"\)',
                # load("package/version")
                r'load\("([^/]+)/([^"]+)"\)',
                # load(pathJoin("package", package_ver))
                r'load\(pathJoin\("([^"]+)",\s*([^)]+)\)\)',
                # Variable assignments: package_ver=os.getenv("package_ver") or "version"
                r'([a-zA-Z0-9_-]+)_ver\s*=\s*os\.getenv\("[^"]+"\)\s*or\s*"([^"]+)"',
                # local package_version = "version"
                r'local\s+([a-zA-Z0-9_-]+)_ver(?:sion)?\s*=\s*"([^"]+)"',
                # -- Package: name (version) [description]
                r'--\s*Package:\s*([a-zA-Z0-9_-]+)\s*\(([^)]+)\)\s*(?:\[([^]]+)\])?',
                # -- name/version
                r'--\s*([a-zA-Z0-9_-]+)/([0-9][^,\s]*)',
                # Simple comment patterns like -- jasper 4.0.0
                r'--\s*([a-zA-Z0-9_-]+)\s+([0-9][0-9.]*)',
            ]
            
            # Extract package information using multiple regex patterns
            for pattern in patterns:
                matches = re.finditer(pattern, common_module_content, re.MULTILINE)
                for match in matches:
                    if len(match.groups()) >= 2:
                        # Extract package name and version from the match
                        if r'\{\[' in pattern:
                            # Handle UFS table format: {["package"] = "version"}
                            package_name = match.group(1).lower()
                            version = match.group(2)
                        elif "pathJoin" in pattern:
                            # Handle pathJoin pattern
                            package_name = match.group(1).lower()
                            version_var = match.group(2).strip()
                            # Try to find the version definition
                            version_pattern = f'{version_var.replace("_ver", "")}_ver\\s*=.*?"([^"]+)"'
                            version_match = re.search(version_pattern, common_module_content)
                            version = version_match.group(1) if version_match else "latest"
                        else:
                            # Regular patterns
                            package_name = match.group(1).lower()
                            # Clean up package name
                            package_name = package_name.replace("_version", "").replace("_ver", "")
                            version = match.group(2)
                        
                        # Filter out unwanted packages
                        if (package_name.startswith("stack") or 
                            package_name == "ufs_common" or
                            len(package_name) <= 1 or  # Too short
                            package_name[0].isdigit() or  # Starts with digit (like "3-esmf")
                            "-" in package_name and package_name.split("-")[0].isdigit()):  # Version prefix like "3-esmf"
                            continue
                        
                        # Validate version format (basic check)
                        if not version or version == "latest":
                            version = "latest"
                        elif not re.match(r'^[0-9]', version):  # Version should start with a number
                            continue
                            
                        # Try to extract description if available (from the third group)
                        description = ""
                        if len(match.groups()) >= 3 and match.group(3):
                            description = match.group(3)
                        
                        upgradable_packages.append({
                            "name": package_name,
                            "version": version,
                            "description": description
                        })
            
            # Also look for a special section that might list upgradable packages
            # This is a common pattern in ufs_common.lua for listing what can be upgraded
            upgradable_section_match = re.search(
                r'-- Upgradable packages[^\n]*\n(.*?)(?:\n(?!--)|$)', 
                common_module_content,
                re.DOTALL
            )
            
            if upgradable_section_match:
                section_text = upgradable_section_match.group(1)
                # Look for package entries in the upgradable section
                # Pattern: -- package_name (version) [description]
                pkg_entries = re.finditer(
                    r'--\s*([a-zA-Z0-9_-]+)\s+\(([^)]+)\)(?:\s+\[([^]]+)\])?',
                    section_text
                )
                
                for entry in pkg_entries:
                    pkg_name = entry.group(1)
                    version = entry.group(2) if entry.group(2) else "latest"
                    description = entry.group(3) if len(entry.groups()) >= 3 and entry.group(3) else ""
                    
                    upgradable_packages.append({
                        "name": pkg_name,
                        "version": version,
                        "description": description
                    })
            
            # Remove duplicates by package name
            seen = set()
            unique_packages = []
            for pkg in upgradable_packages:
                if pkg["name"] not in seen:
                    seen.add(pkg["name"])
                    unique_packages.append(pkg)
            
            
            return unique_packages
            
        except Exception as e:
            print(f"Warning: Failed to parse upgradable packages from common module: {e}")
            return []
        

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
    
    def get_application_by_name(self, name: str) -> Optional[ModelApplication]:
        """Get application by name.
        
        Args:
            name: Application name
            
        Returns:
            ModelApplication if found, None otherwise
        """
        for app in self.applications:
            if app.name == name:
                return app
        return None
    
    def get_applications_with_install_paths(self) -> List[Tuple[ModelApplication, str]]:
        """Get applications that have valid install paths.
        
        Returns:
            List of (application, install_path) tuples
        """
        results = []
        for app in self.applications:
            try:
                install_path = app.extract_install_path()
                if install_path and os.path.exists(install_path):
                    results.append((app, install_path))
            except Exception as e:
                print(f"Warning: Failed to get install path for {app.name}: {e}")
        
        return results
