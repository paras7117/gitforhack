"""
Tests for TestingStore (Git Notes, trailers, and clone fallback).
"""

from git_provenance.core.git_wrapper import GitWrapper
from git_provenance.core.testing_store import TestingStore
from git_provenance.core.provenance import TestStatus, EnvironmentStatus


def test_record_and_get_attestation(temp_git_repo):
    git = GitWrapper(temp_git_repo)
    store = TestingStore(git)

    head = git.get_head_commit()
    assert head is not None

    # Record attestation
    att = store.record_attestation(
        commit_hash=head,
        status=TestStatus.PASSED,
        suite_name="unit-tests",
        ci_run_id="run-456",
        coverage_pct=94.5,
        environment=EnvironmentStatus.PRODUCTION,
    )
    assert att.status == TestStatus.PASSED
    assert att.coverage_pct == 94.5

    # Retrieve from notes
    fetched = store.get_attestation(head)
    assert fetched.status == TestStatus.PASSED
    assert fetched.suite_name == "unit-tests"
    assert fetched.ci_run_id == "run-456"
    assert fetched.coverage_pct == 94.5


def test_trailer_fallback_when_no_notes(temp_git_repo):
    git = GitWrapper(temp_git_repo)
    test_file = temp_git_repo / "feature.py"
    test_file.write_text("x = 1\n")
    git.run(["add", "feature.py"])

    # Commit with Git trailers
    trailers = {
        "X-Test-Status": "PASSED",
        "X-Test-Suite": "regression-suite",
        "X-CI-Run": "CI-9988",
        "X-Coverage": "88.2%",
    }
    commit_sha = git.create_commit("Add feature with test trailers", trailers=trailers)

    store = TestingStore(git)
    att = store.get_attestation(commit_sha)

    assert att.status == TestStatus.PASSED
    assert att.suite_name == "regression-suite"
    assert att.ci_run_id == "CI-9988"
    assert att.coverage_pct == 88.2
