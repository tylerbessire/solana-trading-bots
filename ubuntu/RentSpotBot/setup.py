from setuptools import setup, find_packages

setup(
    name="rentspotbot",
    version="0.1",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "websockets",
        "pytest",
        "pytest-asyncio"
    ]
)
