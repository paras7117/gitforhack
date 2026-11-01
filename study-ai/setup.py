from setuptools import setup, find_packages

setup(
    name="git-provenance",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "git-provenance = git_provenance.cli:main",
            "git-prov = git_provenance.cli:main",
        ],
    },
)
