#!/usr/bin/env python3
"""
Evaluation Scenario: Multi-Branch Enterprise Conflict Resolution
Simulates conflict between Production-Tested Hotfix and Unverified Feature Branch.
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
from git_provenance.core.ai_engine import AIResolutionEngine
from git_provenance.ui.formatter import ProvenanceFormatter


def main():
    scenario_dir = Path(__file__).resolve().parent
    input_file = scenario_dir / "input" / "conflicted_payment_service.py"
    context_file = scenario_dir / "input" / "repo_context.json"
    output_dir = scenario_dir / "output"
    output_dir.mkdir(exist_ok=True, parents=True)

    content = input_file.read_text(encoding="utf-8")
    context = json.loads(context_file.read_text(encoding="utf-8"))

    hunks = ConflictParser.parse_content(content)
    assert len(hunks) == 1
    hunk = hunks[0]

    head_data = context["commits"]["HEAD"]
    dev_data = context["commits"]["feature/async-webhooks"]

    prov_ours = CommitProvenance(
        commit_hash=head_data["hash"],
        short_hash=head_data["hash"][:7],
        author_name=head_data["author"],
        author_email="security@fintech.io",
        date="2026-10-31T08:00:00Z",
        message=head_data["message"],
        environment=EnvironmentStatus(head_data["environment"]),
        test_attestation=TestAttestation(
            status=TestStatus(head_data["test_status"]),
            suite_name=head_data["suite"],
            ci_run_id=head_data.get("ci_run"),
            coverage_pct=head_data.get("coverage"),
        ),
    )

    prov_theirs = CommitProvenance(
        commit_hash=dev_data["hash"],
        short_hash=dev_data["hash"][:7],
        author_name=dev_data["author"],
        author_email="intern@fintech.io",
        date="2026-10-31T10:30:00Z",
        message=dev_data["message"],
        environment=EnvironmentStatus(dev_data["environment"]),
        test_attestation=TestAttestation(
            status=TestStatus(dev_data["test_status"]),
        ),
    )

    ctx = HunkProvenanceContext(
        hunk=hunk,
        file_path="services/payment_service.py",
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
    (output_dir / "resolved_payment_service.py").write_text(resolved_content, encoding="utf-8")

    commit_log = f"""commit 4d7a8e2b9c1f
Author: DevOps Release Engineer <release@fintech.io>
Date:   Sat Oct 31 11:00:00 2026 +0000

    Merge branch 'feature/async-webhooks' into uat

    Resolved using git-provenance v1.0.0
    Preserved Production Hotfix (Tested in Production, 100% PCI Coverage)
    Resolution Strategy: {strat.value}

    X-Conflict-Resolved-With: git-provenance-v1.0.0
    X-Provenance-Verified: True
    X-Test-Status: PASSED
    X-CI-Run: 8921
    X-Environment: production
"""
    (output_dir / "git_commit_log.txt").write_text(commit_log, encoding="utf-8")

    print("✔ Multi-Branch Enterprise Scenario Executed Successfully.")
    print(f"  Resolution: {strat.value} (Confidence: {conf*100:.1f}%)")
    print(f"  Artifacts written to: {output_dir}")


if __name__ == "__main__":
    main()
