"""
Tests for Web API Server endpoints.
"""

import json
from git_provenance.web.server import GitProvenanceAPIHandler
from git_provenance.core.provenance import ConflictHunk


class MockRequest:
    def __init__(self, raw_bytes=b""):
        self.raw_bytes = raw_bytes

    def makefile(self, *args, **kwargs):
        import io
        return io.BytesIO(self.raw_bytes)


def test_api_scenarios_listing(temp_git_repo):
    handler = GitProvenanceAPIHandler.__new__(GitProvenanceAPIHandler)
    handler.repo_path = str(temp_git_repo)
    from git_provenance.core.git_wrapper import GitWrapper
    from git_provenance.core.resolver import ConflictResolver
    from git_provenance.core.ai_engine import AIResolutionEngine
    handler.git = GitWrapper(temp_git_repo)
    handler.ai = AIResolutionEngine()
    handler.resolver = ConflictResolver(temp_git_repo, ai_engine=handler.ai)

    # Test status endpoint
    conflicted = handler.git.get_conflicted_files()
    assert isinstance(conflicted, list)


def test_resolve_hunk_api(temp_git_repo):
    from git_provenance.core.ai_engine import AIResolutionEngine
    from git_provenance.core.provenance import HunkProvenanceContext

    engine = AIResolutionEngine()
    hunk = ConflictHunk(
        hunk_index=0,
        start_line=1,
        end_line=5,
        header_ours="HEAD",
        header_theirs="feature",
        lines_ours=["import sys\n"],
        lines_theirs=["import os\n"],
    )
    ctx = HunkProvenanceContext(hunk=hunk, file_path="main.py")
    strat, code, conf, rationale, model = engine.synthesize_resolution(ctx)

    assert "import" in code
    assert conf >= 0.85
