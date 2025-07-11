#!/usr/bin/env python3
"""Setup script for emcenvchainer."""

from setuptools import setup, find_packages
import os

setup(
    name="emcenvchainer",
    version="0.1.0",
    description="A TUI utility for creating test installations using Spack environment chaining",
    long_description_content_type="text/markdown",
    author="EMC Development Team",
    author_email="",
    url="https://github.com/your-org/emcenvchainer",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",    # For downloading module files
        "termcolor>=1.1.0",    # For colored terminal output
        "ruamel.yaml>=0.17.0", # For YAML manipulation preserving comments
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.12.0",
            "black>=21.0.0",
            "flake8>=3.9.0",
            "mypy>=0.910",
        ],
    },
    entry_points={
        "console_scripts": [
            "emcenvchainer=emcenvchainer.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: POSIX :: Linux",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Installation/Setup",
    ],
    keywords="spack environment chaining hpc scientific-computing",
)
