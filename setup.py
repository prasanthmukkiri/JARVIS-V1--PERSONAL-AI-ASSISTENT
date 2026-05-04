from setuptools import setup, find_packages

# Package metadata is defined in pyproject.toml
# This setup.py exists for backwards compatibility
setup(
    packages=find_packages(exclude=["tests*", "docs*"]),
)

