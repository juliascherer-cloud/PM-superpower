from setuptools import setup, find_packages

setup(
    name="pm-superpower",
    version="0.1.0",
    description="AI-powered PM assistant using Claude agent teams",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "anthropic>=0.51.0",
        "rich>=13.7.0",
        "python-dotenv>=1.0.0",
        "httpx>=0.27.0",
        "click>=8.1.0",
    ],
    entry_points={
        "console_scripts": [
            "pm=pm_superpower.cli:cli",
        ],
    },
)
