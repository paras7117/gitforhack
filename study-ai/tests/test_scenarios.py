"""
End-to-End Conflict Resolution and Git Provenance Scenarios.
"""

import subprocess
from git_provenance.core.git_wrapper import GitWrapper
from git_provenance.core.resolver import ConflictResolver
from git_provenance.core.testing_store import TestingStore
from git_provenance.core.provenance import TestStatus, EnvironmentStatus


def test_e2e_production_hotfix_vs_dev_conflict(temp_git_repo):
    git = GitWrapper(temp_git_repo)
    testing_store = TestingStore(git)

    # 1. Base commit: create a service file
    svc_file = temp_git_repo / "auth_service.py"
    svc_file.write_text(
        "def authenticate(user, password):\n"
        "    # Base implementation\n"
        "    if not user:\n"
        "        return False\n"
        "    return check_db(user, password)\n"
    )
    git.run(["add", "auth_service.py"])
    base_commit = git.create_commit("Add initial auth service")

    # 2. Branch: 'production' - add production security fix with test attestation
    git.run(["checkout", "-b", "production"])
    svc_file.write_text(
        "def authenticate(user, password):\n"
        "    # PRODUCTION FIX: Mitigate timing attacks (CVE-2026-999)\n"
        "    if not user or not password:\n"
        "        return False\n"
        "    return constant_time_compare(user, password)\n"
    )
    git.run(["add", "auth_service.py"])
    prod_commit = git.create_commit("Production fix: Use constant time compare")
    testing_store.record_attestation(
        commit_hash=prod_commit,
        status=TestStatus.PASSED,
        suite_name="security-test-suite",
        coverage_pct=100.0,
        environment=EnvironmentStatus.PRODUCTION,
    )

    # 3. Branch: 'feature-dev' - from base, add unverified cosmetic refactoring
    git.run(["checkout", "-b", "feature-dev", base_commit])
    svc_file.write_text(
        "def authenticate(user, password):\n"
        "    # DEV TWEAK: Unverified logger\n"
        "    logger.debug('Authenticating %s', user)\n"
        "    return check_db(user, password)\n"
    )
    git.run(["add", "auth_service.py"])
    dev_commit = git.create_commit("Dev tweak: Add debug logger")

    # 4. Trigger merge conflict: merge production into feature-dev
    git.run(["merge", "production"], check=False)
    conflicted = git.get_conflicted_files()
    assert "auth_service.py" in conflicted

    # 5. Run ConflictResolver
    resolver = ConflictResolver(repo_path=str(temp_git_repo))
    summary = resolver.resolve_file("auth_service.py", apply=True, stage=True)

    assert summary.total_hunks == 1
    ctx = summary.hunk_contexts[0]
    # Should recommend preserving the production-tested fix
    assert "constant_time_compare" in summary.resolved_content
    assert "<<<<<<<" not in summary.resolved_content

    # 6. Finalize with standard git commit
    new_commit = git.create_commit("Merge branch 'production' with git-provenance resolution")
    assert new_commit is not None
    assert len(git.get_conflicted_files()) == 0
