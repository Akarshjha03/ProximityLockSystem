from setuptools import setup, find_packages

setup(
    name="proximity-lock-system",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["pybluez"],
    entry_points={
        "console_scripts": [
            "proximity-lock=proximity_lock_system.cli:main",
        ],
    },
    author="Akarsh Jha",
    description="A CLI tool that automatically locks or sleeps your laptop when your phone goes out of Bluetooth range.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Akarshjha03/ProximityLockSystem",
    python_requires=">=3.8",
)
