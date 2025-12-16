from setuptools import setup, find_packages

setup(
    name="proximity-lock-system",
    version="2.1.0",
    packages=find_packages(),
    install_requires=[
        "pybluez"
    ],
    entry_points={
        "console_scripts": [
            "proximity-lock=proximity_lock_system.cli:main",
        ],
    },
    author="Akarsh Jha",
    description="Security-style CLI that locks your system when your phone leaves Bluetooth range.",
    long_description=open("README.md", encoding="utf-8").read() if True else "",
    long_description_content_type="text/markdown",
    url="https://github.com/Akarshjha03/ProximityLockSystem",
    python_requires=">=3.8",
)
