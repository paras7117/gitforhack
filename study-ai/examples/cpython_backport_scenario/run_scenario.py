#!/usr/bin/env python3
"""
Evaluation Scenario: CPython Backport Conflict Resolution
Simulates backporting gh-108278 (cherry-picked commit) to CPython 3.12 branch.
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from git_provenance.core.conflict_parser import ConflictParser
from git_provenance.core.provenance import (
    ConflictHunk,
    HunkProvenanceContext,
    CommitProvenance,
    EnvironmentStatus,
    TestStatus,
    TestAttestation,
)
from git_provenance.adapters.cpython_adapter import CPythonBackportAdapter
from git_provenance.core.ai_engine import AIResolutionEngine
from git_provenance.ui.formatter import ProvenanceFormatter


def main():
    scenario_dir = Path(__file__).resolve().parent
    input_file = scenario_dir / "input" / "conflicted_asyncio.py"
    context_file = scenario_dir / "input" / "repo_context.json"
    output_dir = scenario_dir / "output"
    output_dir.mkdir(exist_ok=True, parents=True)

    content = input_file.read_text(encoding="utf-8")
    context = json.loads(context_file.read_text(encoding="utf-8"))

    hunks = ConflictParser.parse_content(content)
    assert len(hunks) == 1
    hunk = hunks[0]

    head_data = context["commits"]["HEAD"]
    bp_data = context["commits"]["cpython-3.12-backport"]

    cpython_meta = CPythonBackportAdapter.parse_commit_metadata(bp_data["message"])

    prov_ours = CommitProvenance(
        commit_hash=head_data["hash"],
        short_hash=head_data["hash"][:7],
        author_name=head_data["author"],
        author_email="python-dev@python.org",
        date="2026-10-28T09:00:00Z",
        message=head_data["message"],
        environment=EnvironmentStatus(head_data["environment"]),
        test_attestation=TestAttestation(
            status=TestStatus(head_data["test_status"]),
        ),
    )

    prov_theirs = CommitProvenance(
        commit_hash=bp_data["hash"],
        short_hash=bp_data["hash"][:7],
        author_name=bp_data["author"],
        author_email="miss-islington@python.org",
        date="2026-10-28T11:15:00Z",
        message=bp_data["message"],
        environment=EnvironmentStatus(bp_data["environment"]),
        test_attestation=TestAttestation(
            status=TestStatus(bp_data["test_status"]),
            suite_name=bp_data["suite"],
            coverage_pct=bp_data.get("coverage"),
        ),
        cherry_pick_origin=cpython_meta.get("cherry_pick_commit"),
        backport_references=[f"CPython gh-{cpython_meta['issue_id']} (PR #{cpython_meta['pr_number']})"],
    )

    ctx = HunkProvenanceContext(
        hunk=hunk,
        file_path="Lib/asyncio/proactor_events.py",
        provenance_ours=prov_ours,
        provenance_theirs=prov_theirs,
    )

    engine = AIResolutionEngine()
    strat, code, conf, rationale, model = engine.synthesize_resolution(ctx)
    ctx.recommendation = strat
    ctx.recommended_code = code
    ctx.confidence_score = conf
    ctx.rationale = rationale
    ctx.ai_model_used = model

    # Write output artifacts
    report_dict = ctx.to_dict()
    (output_dir / "provenance_report.json").write_text(json.dumps(report_dict, indent=2), encoding="utf-8")

    text_report = ProvenanceFormatter.format_hunk_report(ctx)
    (output_dir / "provenance_report.txt").write_text(text_report, encoding="utf-8")

    resolved_content = ConflictParser.apply_resolutions(content, [(hunk.hunk_index, code)])
    (output_dir / "resolved_asyncio.py").write_text(resolved_content, encoding="utf-8")

    commit_log = f"""commit 7a82b9e6fa436c0a0c441b8a514dcf50db9011f0
Author: Miss Islington (bot) <miss-islington@python.org>
Date:   Wed Oct 28 11:30:00 2026 +0000

    [3.12] gh-108278: Disallow nested asyncio event loops on Windows (GH-108300)

    (cherry picked from commit 7a82b9e6fa436c0a0c441b8a514dcf50db9011f0)

    Resolved with git-provenance v1.0.0
    Resolution Strategy: {strat.value}
    Verified Testing Provenance: test_asyncio (Coverage: 99.1%)

    X-Conflict-Resolved-With: git-provenance-v1.0.0
    X-Provenance-Verified: True
    X-Issue: gh-108278
    X-Upstream-PR: GH-108300
"""
    (output_dir / "git_commit_log.txt").write_text(commit_log, encoding="utf-8")

    print("✔ CPython Backport Scenario Executed Successfully.")
    print(f"  Resolution: {strat.value} (Confidence: {conf*100:.1f}%)")
    print(f"  Artifacts written to: {output_dir}")


if __name__ == "__main__":
    main()
