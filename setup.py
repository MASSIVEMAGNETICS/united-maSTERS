from setuptools import setup, find_packages

setup(
    name="united-masters",
    version="1.4.0",
    description="Local-first music release workbench: mastering, encoding, QC, and delivery.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="MASSIVEMAGNETICS",
    url="https://github.com/MASSIVEMAGNETICS/united-maSTERS",
    project_urls={
        "Bug Tracker": "https://github.com/MASSIVEMAGNETICS/united-maSTERS/issues",
    },
    packages=find_packages(),
    package_data={
        "united_masters": ["py.typed"],
        "vos_core": ["py.typed"],
    },
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
    extras_require={
        "gpu": ["torch>=2.1.0"],
        "loudnorm": ["pyloudnorm>=0.1.1"],
        "dev": ["pytest>=7.0", "pytest-cov>=4.0", "mypy>=1.0"],
    },
    entry_points={
        "console_scripts": [
            "united-masters=united_masters.cli:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Sound/Audio",
        "Typing :: Typed",
    ],
)
