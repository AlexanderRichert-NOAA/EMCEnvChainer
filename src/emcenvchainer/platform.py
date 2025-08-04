"""Platform detection and management."""

import os
import re
import socket
from pathlib import Path
from typing import List, Dict, Optional
import glob

from .config import Config


class Platform:
    """Represents a detected platform."""
    
    def __init__(self, name: str, spack_stack_path: str, config: Dict):
        """Initialize platform.
        
        Args:
            name: Platform name
            spack_stack_path: Path to spack-stack installation
            config: Platform configuration
        """
        self.name = name
        self.spack_stack_path = Path(spack_stack_path)
        self.config = config
        self._spack_installations = None
        self._model_applications = None
    
    @property
    def spack_installations(self) -> List[Dict]:
        """Get available Spack installations."""
        if self._spack_installations is None:
            self._spack_installations = self._discover_spack_installations()
        return self._spack_installations
    
    @property
    def model_applications(self) -> List[Dict]:
        """Get available model applications."""
        if self._model_applications is None:
            self._model_applications = list(self.config.get("model_applications", {}).items())
        return self._model_applications
    
    def _discover_spack_installations(self) -> List[Dict]:
        """Discover available Spack installations."""
        installations = []
        
        # Check if spack_stack_path exists first
        if not self.spack_stack_path.exists():
            return installations
        
        # Pattern: <platform-specific path>/spack-stack/spack-stack-<version>/envs/<env>/install/
        pattern = str(self.spack_stack_path / "spack-stack-*" / "envs" / "*" / "install")
        
        for install_path in glob.glob(pattern):
            install_path = Path(install_path)
            if install_path.is_dir():
                # Extract version and environment name
                parts = install_path.parts
                spack_stack_idx = None
                for i, part in enumerate(parts):
                    if part.startswith("spack-stack-"):
                        spack_stack_idx = i
                        break
                
                if spack_stack_idx is not None:
                    version = parts[spack_stack_idx].replace("spack-stack-", "")
                    env_name = parts[spack_stack_idx + 2]  # Skip "envs" directory
                    
                    # Get the spack root path
                    spack_root = Path(*parts[:spack_stack_idx+1]) / "spack"
                    
                    installations.append({
                        "name": f"{env_name} (v{version})",
                        "version": version,
                        "environment": env_name,
                        "install_path": str(install_path),
                        "spack_root": str(spack_root),
                        "type": "spack_installation"
                    })
        
        return sorted(installations, key=lambda x: (x["version"], x["environment"]))
    
    def get_spack_root(self, installation: Dict) -> str:
        """Get Spack root for an installation."""
        return installation["spack_root"]


class PlatformDetector:
    """Detects the current platform based on filesystem paths (or $SITE_OVERRIDE)."""
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize platform detector.
        
        Args:
            config: Configuration object
        """
        self.config = config or Config()
    
    def detect_platform(self) -> Optional[Platform]:
        """Detect the current platform.
        
        Returns:
            Platform object if detected, None otherwise
        """
        # Check built-in platform configurations
        platforms = self.config.get_platforms()
        for platform_key, platform_config in platforms.items():
            if self._check_platform_hostname(platform_config) or os.getenv("SITE_OVERRIDE")==platform_key:
                return Platform(
                    name=platform_config.get("name", platform_key),
                    spack_stack_path=platform_config["spack_stack_path"],
                    config=platform_config
                )
        
        print("No platform detected. Supported platforms:")
        for platform_key, platform_config in platforms.items():
            name = platform_config.get("name", platform_key)
            hostname_patterns = platform_config.get("hostname_patterns", [])
            print(f"  - {name}: hostname patterns {hostname_patterns}")
        
        return None
    
    def _check_platform_hostname(self, platform_config: Dict) -> bool:
        """Check if platform hostname patterns match the current hostname.
        
        Args:
            platform_config: Platform configuration
            
        Returns:
            True if platform is detected
        """
        hostname_patterns = platform_config.get("hostname_patterns", [])
        
        if not hostname_patterns:
            return False
        
        # Get the fully qualified domain name
        fqdn = socket.getfqdn()

        
        # Check if any hostname pattern matches
        for pattern in hostname_patterns:
            if re.match("^" + pattern.lower() + "$", fqdn.lower()):
                return True
        
        return False
