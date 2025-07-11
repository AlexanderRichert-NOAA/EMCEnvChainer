#!/usr/bin/env python3
"""Main entry point for emcenvchainer."""

import sys
import os
from pathlib import Path

from .tui import EmcEnvChainerTUI
from .platform import PlatformDetector
from .config import Config


def main():
    """Main entry point for the emcenvchainer utility."""
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
