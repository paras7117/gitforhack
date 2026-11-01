"""
Environment status detector and branch topology analyzer.
Distinguishes production-tested code from UAT, staging, and unverified feature branches.
"""

import json
from typing import Optional, List
from git_provenance.core.git_wrapper import GitWrapper
from git_provenance.core.provenance import EnvironmentStatus


class EnvironmentDetector:
    """Analyzes branch topology, commit trailers, and Git Notes to deduce environment status."""

    PROD_BRANCH_NAMES = {"production", "prod", "origin/production", "origin/prod", "release", "master"}
    UAT_BRANCH_NAMES = {"uat", "origin/uat", "acceptance", "origin/acceptance", "qa", "origin/qa"}
    STAGING_BRANCH_NAMES = {"staging", "origin/staging", "preprod", "origin/preprod"}
    DEV_BRANCH_NAMES = {"development", "dev", "develop", "origin/dev", "origin/develop"}

    def __init__(self, git: Optional[GitWrapper] = None):
        self.git = git or GitWrapper()

    def detect_environment(self, commit_hash: str, containing_branches: Optional[List[str]] = None) -> EnvironmentStatus:
        """
        Determine the deployment/testing tier of a given commit.
        Priority:
        1. Explicit Git Notes environment
        2. Git commit trailer (X-Environment)
        3. Branch topology membership
        """
        if not commit_hash:
            return EnvironmentStatus.UNKNOWN

        # 1. Check Git Notes
        note = self.git.get_git_note("test-provenance", commit_hash)
        if note:
            try:
                data = json.loads(note)
                env_str = data.get("environment")
                if env_str:
                    try:
                        return EnvironmentStatus(env_str.upper())
                    except ValueError:
                        pass
            except Exception:
                pass

        # 2. Check Git Commit Trailers
        trailers = self.git.get_commit_trailers(commit_hash)
        if "X-Environment" in trailers:
            env_str = trailers["X-Environment"].upper()
            try:
                return EnvironmentStatus(env_str)
            except ValueError:
                pass

        # 3. Branch topology
        branches = containing_branches
        if branches is None:
            branches = self.git.get_branches_containing(commit_hash)

        branch_set = set()
        for b in branches:
            clean = b.strip().lower()
            branch_set.add(clean)
            if clean.startswith("remotes/"):
                branch_set.add(clean.replace("remotes/", ""))

        # Check for production / release branches
        for b in branch_set:
            if b in self.PROD_BRANCH_NAMES or b.startswith("release/") or b.startswith("origin/release/"):
                return EnvironmentStatus.PRODUCTION

        # Check for UAT
        for b in branch_set:
            if b in self.UAT_BRANCH_NAMES:
                return EnvironmentStatus.UAT

        # Check for Staging
        for b in branch_set:
            if b in self.STAGING_BRANCH_NAMES:
                return EnvironmentStatus.STAGING

        # Check for Dev
        for b in branch_set:
            if b in self.DEV_BRANCH_NAMES:
                return EnvironmentStatus.DEVELOPMENT

        # If it only exists on an unmerged feature branch
        if branch_set:
            return EnvironmentStatus.UNVERIFIED

        return EnvironmentStatus.UNKNOWN
