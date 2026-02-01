"""
Zaphod - Local-first Canvas LMS course management

Install in development mode:
    pip install -e .

This makes 'from zaphod.xxx import yyy' work from anywhere.
"""

from setuptools import setup, find_packages

setup(
    name="zaphod",
    version="1.0.0",
    description="Local-first Canvas LMS course management",
    packages=["zaphod"],
    package_dir={"zaphod": "."},
    install_requires=[
        "canvasapi>=3.0.0",
        "click>=8.0.0",
        "PyYAML>=6.0",
        "python-frontmatter>=1.0.0",
        "Markdown>=3.4.0",
        "watchdog>=3.0.0",
        "defusedxml>=0.7.1",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.11.1",
            "pytest-timeout>=2.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "zaphod=zaphod.cli:cli",
        ],
    },
    python_requires=">=3.9",
)
