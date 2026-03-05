from setuptools import setup, find_packages

setup(
    name="synthetic-data-kit",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "wtforms",
        "flask-wtf",
        "validators",
        "rich",
        "pillow",
        "typer",
    ],
    entry_points={
        "console_scripts": [
            "synthetic-data-kit=synthetic_data_kit.cli:main",
        ],
    },
)
