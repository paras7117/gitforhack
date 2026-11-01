"""
Pytest configuration and shared fixtures.
"""

import os
import shutil
import tempfile
import subprocess
from pathlib import Path
import pytest
from git_provenance.core.git_wrapper import GitWrapper


@pytest.fixture
def temp_git_repo():
    """Create a temporary initialized Git repository with initial commit."""
    temp_dir = tempfile.mkdtemp(prefix="git_prov_test_")
    repo_path = Path(temp_dir)

    def run_cmd(args):
        subprocess.run(["git"] + args, cwd=str(repo_path), check=True, capture_output=True, text=True)

    run_cmd(["init"])
    run_cmd(["config", "user.name", "Tester"])
    run_cmd(["config", "user.email", "tester@test.com"])

    # Create initial file & commit
    init_file = repo_path / "README.md"
    init_file.write_text("# Test Repo\n", encoding="utf-8")
    run_cmd(["add", "README.md"])
    run_cmd(["commit", "-m", "Initial commit"])

    yield repo_path

    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)
