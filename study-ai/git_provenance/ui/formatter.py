"""
Terminal formatting and visual diff presentation for conflict provenance.
Supports colored ANSI badges, markdown tables, and JSON export.
"""

import sys
import json
from typing import List, Dict, Any, Optional
from git_provenance.core.provenance import (
    HunkProvenanceContext,
    FileConflictSummary,
    EnvironmentStatus,
    TestStatus,
    CommitProvenance,
)


class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


class ProvenanceFormatter:
    """Formats conflict provenance reports for console and programmatic output."""

    @classmethod
    def env_badge(cls, env: EnvironmentStatus) -> str:
        if env == EnvironmentStatus.PRODUCTION:
            return f"{Color.BOLD}{Color.BG_GREEN}{Color.WHITE} PROD {Color.RESET}"
        elif env == EnvironmentStatus.UAT:
            return f"{Color.BOLD}{Color.BG_BLUE}{Color.WHITE} UAT {Color.RESET}"
        elif env == EnvironmentStatus.STAGING:
            return f"{Color.BOLD}{Color.CYAN} STAGING {Color.RESET}"
        elif env == EnvironmentStatus.DEVELOPMENT:
            return f"{Color.YELLOW} DEV {Color.RESET}"
        elif env == EnvironmentStatus.UNVERIFIED:
            return f"{Color.BOLD}{Color.BG_RED}{Color.WHITE} UNVERIFIED {Color.RESET}"
        return f"{Color.DIM} UNKNOWN {Color.RESET}"

    @classmethod
    def test_badge(cls, test_status: TestStatus) -> str:
        if test_status == TestStatus.PASSED:
            return f"{Color.GREEN}✔ PASSED{Color.RESET}"
        elif test_status == TestStatus.FAILED:
            return f"{Color.RED}✘ FAILED{Color.RESET}"
        elif test_status == TestStatus.UNTESTED:
            return f"{Color.YELLOW}⚠ UNTESTED{Color.RESET}"
        return f"{Color.DIM}? UNKNOWN{Color.RESET}"

    @classmethod
    def format_commit_card(cls, label: str, prov: Optional[CommitProvenance]) -> str:
        lines = [f"{Color.BOLD}{label}{Color.RESET}"]
        if not prov:
            lines.append("  Commit: (uncommitted / untracked)")
            lines.append(f"  Testing: {cls.test_badge(TestStatus.UNTESTED)}")
            lines.append(f"  Environment: {cls.env_badge(EnvironmentStatus.UNVERIFIED)}")
            return "\n".join(lines)

        lines.append(f"  Commit:      {Color.CYAN}{prov.short_hash}{Color.RESET} ({prov.author_name}) - {prov.date[:10]}")
        lines.append(f"  Environment: {cls.env_badge(prov.environment)}")
        
        t = prov.test_attestation
        t_info = f"{cls.test_badge(t.status)} (Suite: {t.suite_name}"
        if t.ci_run_id:
            t_info += f", CI: #{t.ci_run_id}"
        if t.coverage_pct is not None:
            t_info += f", Cov: {t.coverage_pct:.1f}%"
        t_info += ")"
        lines.append(f"  Testing:     {t_info}")

        if prov.cherry_pick_origin:
            lines.append(f"  Origin:      Cherry-picked from {Color.MAGENTA}{prov.cherry_pick_origin[:8]}{Color.RESET}")

        if prov.backport_references:
            refs = ", ".join(prov.backport_references)
            lines.append(f"  Backport:    {Color.YELLOW}{refs}{Color.RESET}")

        if prov.patch_id:
            lines.append(f"  Patch-ID:    {prov.patch_id[:12]}")

        lines.append(f"  Message:     {Color.DIM}{prov.message.splitlines()[0] if prov.message else ''}{Color.RESET}")
        return "\n".join(lines)

    @classmethod
    def format_hunk_report(cls, ctx: HunkProvenanceContext) -> str:
        h = ctx.hunk
        lines = [
            f"{Color.BOLD}{'=' * 78}{Color.RESET}",
            f"{Color.BOLD}Conflict #{h.hunk_index + 1} in {Color.CYAN}{ctx.file_path}{Color.RESET} (Lines {h.start_line}-{h.end_line})",
            f"{Color.BOLD}{'=' * 78}{Color.RESET}",
            "",
            cls.format_commit_card("OURS (Current Branch / HEAD):", ctx.provenance_ours),
            "",
            cls.format_commit_card("THEIRS (Incoming Branch):", ctx.provenance_theirs),
            "",
            f"{Color.BOLD}Intelligent Provenance Recommendation:{Color.RESET}",
            f"  Strategy:    {Color.GREEN}{ctx.recommendation.value.upper()}{Color.RESET}",
            f"  Confidence:  {Color.BOLD}{ctx.confidence_score * 100:.1f}%{Color.RESET}",
            f"  Engine:      {ctx.ai_model_used or 'Heuristic-Engine'}",
            f"  Rationale:   {ctx.rationale}",
            "",
        ]
        return "\n".join(lines)

    @classmethod
    def format_summary(cls, summary: FileConflictSummary) -> str:
        out = [
            f"\n{Color.BOLD}File:{Color.RESET} {summary.file_path}",
            f"Total Conflicts: {summary.total_hunks}",
        ]
        for ctx in summary.hunk_contexts:
            out.append(cls.format_hunk_report(ctx))
        return "\n".join(out)
