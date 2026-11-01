"""
Tests for OriginMiner and backport adapters (Django, CPython, patch-id).
"""

from git_provenance.core.origin_miner import OriginMiner
from git_provenance.adapters.django_adapter import DjangoBackportAdapter
from git_provenance.adapters.cpython_adapter import CPythonBackportAdapter


def test_django_adapter_parsing():
    msg = """[4.2.x] Fixed #34567 -- Corrected outer join order in ORM query compiler.
Backport of 6e1a49f82d3b from main.
"""
    info = DjangoBackportAdapter.parse_commit_metadata(msg)
    assert info["is_django_backport"] is True
    assert info["target_branch"] == "4.2.x"
    assert info["ticket_id"] == "34567"
    assert info["upstream_commit"] == "6e1a49f82d3b"
    assert info["upstream_branch"] == "main"


def test_cpython_adapter_parsing():
    msg = """[3.12] gh-108278: Disallow nested asyncio event loops on Windows (GH-108300)

(cherry picked from commit 7a82b9e6fa436c0a0c441b8a514dcf50db9011f0)
"""
    info = CPythonBackportAdapter.parse_commit_metadata(msg)
    assert info["is_cpython_backport"] is True
    assert info["target_branch"] == "3.12"
    assert info["issue_id"] == "108278"
    assert info["pr_number"] == "108300"
    assert info["cherry_pick_commit"] == "7a82b9e6fa436c0a0c441b8a514dcf50db9011f0"


def test_cherry_pick_origin_extraction(temp_git_repo):
    miner = OriginMiner()
    text = "Fix bug\n\n(cherry picked from commit 1234567890abcdef1234567890abcdef12345678)\n"
    match = miner.CHERRY_PICK_PATTERN.search(text)
    assert match is not None
    assert match.group(1) == "1234567890abcdef1234567890abcdef12345678"
