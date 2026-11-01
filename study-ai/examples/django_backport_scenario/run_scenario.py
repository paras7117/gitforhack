#!/usr/bin/env python3
"""
Evaluation Scenario: Django Backport Conflict Resolution
Simulates backporting upstream bugfix PR #34567 to Django stable/4.2.x.
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
    ResolutionStrategy,
)
from git_provenance.adapters.django_adapter import DjangoBackportAdapter
from git_provenance.core.ai_engine import AIResolutionEngine
from git_provenance.ui.formatter import ProvenanceFormatter


def main():
    scenario_dir = Path(__file__).resolve().parent
    input_file = scenario_dir / "input" / "conflicted_views.py"
    context_file = scenario_dir / "input" / "repo_context.json"
    output_dir = scenario_dir / "output"
    output_dir.mkdir(exist_ok=True, parents=True)

    content = input_file.read_text(encoding="utf-8")
    context = json.loads(context_file.read_text(encoding="utf-8"))

    hunks = ConflictParser.parse_content(content)
    assert len(hunks) == 1
    hunk = hunks[0]

    head_data = context["commits"]["HEAD"]
    bp_data = context["commits"]["main-backport"]

    django_meta = DjangoBackportAdapter.parse_commit_metadata(bp_data["message"])

    prov_ours = CommitProvenance(
        commit_hash=head_data["hash"],
        short_hash=head_data["hash"][:7],
        author_name=head_data["author"],
        author_email="core@djangoproject.com",
        date="2026-10-25T12:00:00Z",
        message=head_data["message"],
        environment=EnvironmentStatus(head_data["environment"]),
        test_attestation=TestAttestation(
            status=TestStatus(head_data["test_status"]),
            suite_name=head_data["suite"],
        ),
    )

    prov_theirs = CommitProvenance(
        commit_hash=bp_data["hash"],
        short_hash=bp_data["hash"][:7],
        author_name=bp_data["author"],
        author_email="orm@djangoproject.com",
        date="2026-10-26T14:30:00Z",
        message=bp_data["message"],
        environment=EnvironmentStatus(bp_data["environment"]),
        test_attestation=TestAttestation(
            status=TestStatus(bp_data["test_status"]),
            suite_name=bp_data["suite"],
            coverage_pct=bp_data.get("coverage"),
        ),
        backport_references=[f"Django #{django_meta['ticket_id']} (Upstream: {django_meta['upstream_commit']})"],
    )

    ctx = HunkProvenanceContext(
        hunk=hunk,
        file_path="myapp/views.py",
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

    # Write output files
    report_dict = ctx.to_dict()
    (output_dir / "provenance_report.json").write_text(json.dumps(report_dict, indent=2), encoding="utf-8")

    text_report = ProvenanceFormatter.format_hunk_report(ctx)
    (output_dir / "provenance_report.txt").write_text(text_report, encoding="utf-8")

    resolved_content = ConflictParser.apply_resolutions(content, [(hunk.hunk_index, code)])
    (output_dir / "resolved_views.py").write_text(resolved_content, encoding="utf-8")

    commit_log = f"""commit 9a8f112e4b6c
Author: Django Release Bot <bot@djangoproject.com>
Date:   Mon Oct 26 15:00:00 2026 +0000

    Merge backport of #34567 into stable/4.2.x

    Resolved with git-provenance v1.0.0
    Resolution Strategy: {strat.value}
    Verified Testing Provenance: django-tests-full (Coverage: 98.4%)

    X-Conflict-Resolved-With: git-provenance-v1.0.0
    X-Provenance-Verified: True
    X-Original-Ticket: Django #34567
    X-Upstream-Commit: 6e1a49f
"""
    (output_dir / "git_commit_log.txt").write_text(commit_log, encoding="utf-8")

    print("✔ Django Backport Scenario Executed Successfully.")
    print(f"  Resolution: {strat.value} (Confidence: {conf*100:.1f}%)")
    print(f"  Artifacts written to: {output_dir}")


if __name__ == "__main__":
    main()
