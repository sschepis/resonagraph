"""
ResonaGraph setup configuration.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="resonagraph",
    version="0.1.0",
    author="Sebastian Schepis",
    description="Prime-Resonant Graph Database implementing phase-modulated superpositions",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sschepis/resonagraph",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        # Core dependencies from copilot-instructions.md
        # Note: Some dependencies like quiche, GMP may require system libraries
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=23.0",
            "flake8>=6.0",
            "mypy>=1.0",
        ],
    },
)
