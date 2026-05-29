#!/usr/bin/env python3
"""Main entry point for emcenvchainer."""

import sys
import os
import argparse
from pathlib import Path

try:
    from importlib.metadata import version
except ImportError:
    # Fallback for Python < 3.8
    from importlib_metadata import version

from .tui import EmcEnvChainerTUI
from .platform import PlatformDetector
from .config import Config


def get_version():
    """Get the package version."""
    try:
        return version("emcenvchainer")
    except Exception:
        return "unknown"


def main():
    """Main entry point for the emcenvchainer utility."""
    parser = argparse.ArgumentParser(
        description="EMC spack-stack Environment Chainer - Create chained Spack environments",
        prog="emcenvchainer"
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}"
    )
    
    # Parse arguments (currently only --version, but extensible for future options)
    parser.parse_args()
    
    try:
        # Initialize configuration
        config = Config()
        
        # Detect platform
        platform_detector = PlatformDetector()
        platform = platform_detector.detect_platform()
        
        if not platform:
            print("Error: Could not detect platform. Please ensure you're running on a supported system.")
            sys.exit(1)
        
        # Initialize and run TUI
        tui = EmcEnvChainerTUI(config, platform)
        tui.run()
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
