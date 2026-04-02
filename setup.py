from setuptools import setup, find_packages

setup(
    name="united-masters",
    version="1.4.0",
    description="Local-first music release workbench: mastering, encoding, QC, and delivery.",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0",
        "flask>=2.0",
        "mutagen>=1.45",
        "pillow>=9.0",
        "numpy>=1.21",
        "scipy>=1.7",
        "pydub>=0.25",
    ],
    entry_points={
        "console_scripts": [
            "united-masters=united_masters.cli:cli",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
