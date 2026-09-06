from setuptools import setup, find_packages
import os

readme_path = os.path.join(os.path.dirname(__file__), "README.md")
if not os.path.exists(readme_path):
    readme_path = os.path.join(os.path.dirname(__file__), "..", "..", "README.md")

long_description = ""
if os.path.exists(readme_path):
    with open(readme_path, encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="proximity-lock-system",
    version="2.1.0",
    packages=find_packages(),
    install_requires=[
        "bleak>=0.21.0",
        "rumps>=0.4.0",
    ],
    entry_points={
        "console_scripts": [
            "proximity-lock=proximity_lock_system.cli:main",
            "proximity-lock-bar=proximity_lock_system.menubar:main",
        ],
    },
    author="Akarsh Jha",
    description=(
        "Security-style CLI that locks your Mac when your phone "
        "leaves Bluetooth (BLE) range."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Akarshjha03/ProximityLockSystem",
    python_requires=">=3.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: MacOS :: MacOS X",
        "Environment :: Console",
        "Topic :: Security",
    ],
)
