"""
Zaphod - Canvas course management from plain text files

Installation:
    pip install -e .

This installs the 'zaphod' command globally in your environment.
"""

from setuptools import setup, find_packages
import os

# Read README for long description
long_description = ''
if os.path.exists('README.md'):
    with open('README.md', 'r', encoding='utf-8') as f:
        long_description = f.read()

setup(
    name='zaphod',
    version='1.0.0',
    description='Canvas course management from plain text files',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Dale Chapman',
    author_email='',  # Add your email if desired
    url='https://github.com/wwcc-dale/zaphod-claude',
    license='MIT',
    
    # Find all packages (zaphod/ and any subpackages)
    packages=find_packages(exclude=['tests', 'tests.*', 'docs', 'courses']),
    
    # Include package data (like templates, if any)
    include_package_data=True,
    
    # Python version requirement
    python_requires='>=3.9',
    
    # Dependencies
    install_requires=[
        'click>=8.0',
        'canvasapi>=2.0',
        'python-frontmatter>=1.0',
        'PyYAML>=6.0',
        'watchdog>=3.0',
        'requests>=2.28',
        'markdown>=3.4',
        'beautifulsoup4>=4.11',
        'lxml>=4.9',
    ],
    
    # Optional dependencies
    extras_require={
        'dev': [
            'pytest>=7.4',
            'pytest-cov>=4.1',
            'pytest-mock>=3.11',
        ],
    },
    
    # CLI entry point - this creates the 'zaphod' command
    entry_points={
        'console_scripts': [
            'zaphod=zaphod.cli:cli',
        ],
    },
    
    # Classifiers for PyPI
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Education',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Education',
    ],
    
    # Keywords for discoverability
    keywords='canvas lms education course markdown',
)
