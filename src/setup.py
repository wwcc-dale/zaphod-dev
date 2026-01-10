from setuptools import setup

setup(
    name='zaphod-cli',
    version='1.0.0',
    py_modules=['cli'],
    install_requires=[
        'click>=8.0',
    ],
    entry_points={
        'console_scripts': [
            'zaphod=cli:cli',
        ],
    },
)
