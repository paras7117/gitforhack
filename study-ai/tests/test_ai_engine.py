"""
Tests for AIResolutionEngine (Deterministic AST rules, Prompt construction, Fallbacks).
"""

from git_provenance.core.ai_engine import AIResolutionEngine
from git_provenance.core.provenance import (
    ConflictHunk,
    HunkProvenanceContext,
    CommitProvenance,
    ResolutionStrategy,
    EnvironmentStatus,
    TestStatus,
    TestAttestation,
)


def test_production_dominance_rule():
    engine = AIResolutionEngine()

    hunk = ConflictHunk(
        hunk_index=0,
        start_line=10,
        end_line=15,
        header_ours="HEAD",
        header_theirs="feature/unverified",
        lines_ours=["    # Production Bugfix (Tested)\n    timeout = 30\n"],
        lines_theirs=["    # Experimental change\n    timeout = None\n"],
    )

    prov_ours = CommitProvenance(
        commit_hash="1111111111111111111111111111111111111111",
        short_hash="1111111",
        author_name="Alice",
        author_email="alice@company.com",
        date="2026-10-30",
        message="Fix connection leak in production",
        environment=EnvironmentStatus.PRODUCTION,
        test_attestation=TestAttestation(status=TestStatus.PASSED, suite_name="pytest", coverage_pct=95.0),
    )

    prov_theirs = CommitProvenance(
        commit_hash="2222222222222222222222222222222222222222",
        short_hash="2222222",
        author_name="Bob",
        author_email="bob@company.com",
        date="2026-10-31",
        message="Disable timeout for testing",
        environment=EnvironmentStatus.UNVERIFIED,
        test_attestation=TestAttestation(status=TestStatus.UNTESTED),
    )

    ctx = HunkProvenanceContext(
        hunk=hunk,
        file_path="network/client.py",
        provenance_ours=prov_ours,
        provenance_theirs=prov_theirs,
    )

    strat, code, conf, rationale, model = engine.synthesize_resolution(ctx)

    assert strat == ResolutionStrategy.OURS
    assert "timeout = 30" in code
    assert conf >= 0.90
    assert "PRODUCTION" in rationale


def test_ast_import_merging():
    engine = AIResolutionEngine()

    hunk = ConflictHunk(
        hunk_index=0,
        start_line=1,
        end_line=5,
        header_ours="HEAD",
        header_theirs="incoming",
        lines_ours=["import os\n", "import sys\n"],
        lines_theirs=["import sys\n", "import json\n", "from pathlib import Path\n"],
    )

    ctx = HunkProvenanceContext(
        hunk=hunk,
        file_path="main.py",
    )

    strat, code, conf, rationale, model = engine.synthesize_resolution(ctx)

    assert strat == ResolutionStrategy.UNION
    assert "import os" in code
    assert "import sys" in code
    assert "import json" in code
    assert "from pathlib import Path" in code


def test_prompt_construction():
    engine = AIResolutionEngine()
    hunk = ConflictHunk(
        hunk_index=0,
        start_line=1,
        end_line=3,
        header_ours="HEAD",
        header_theirs="patch",
        lines_ours=["x = 1\n"],
        lines_theirs=["x = 2\n"],
    )
    ctx = HunkProvenanceContext(hunk=hunk, file_path="script.py")
    prompt = engine._construct_prompt(ctx)
    assert "OUR SIDE" in prompt
    assert "THEIR SIDE" in prompt
    assert "script.py" in prompt


def test_openai_model_detection():
    engine_openai = AIResolutionEngine(model_name="gpt-4o-mini", api_key="sk-mock-key-123")
    assert engine_openai.is_openai_model() is True
    assert engine_openai.is_ai_available() is True

    engine_default = AIResolutionEngine(model_name="gpt-4o")
    assert engine_default.is_openai_model() is True
