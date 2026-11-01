"""
CPython Backport Lineage Adapter.
Parses CPython commit patterns, GitHub issue references, and cherry-pick bot metadata.
"""

import re
from typing import Optional, Dict, Any


class CPythonBackportAdapter:
    """Specialized adapter for CPython backport commit semantics."""

    # Examples:
    # [3.12] gh-108278: Disallow nested asyncio event loops on Windows (GH-108300)
    # (cherry picked from commit 7a82b9e6fa436c0a0c441b8a514dcf50db9011f0)
    BRANCH_GH_PATTERN = re.compile(
        r"^\[([\d\.]+)\]\s+(?:gh-|bpo-)(\d+):\s*(.*?)(?:\s*\((?:GH-|#)(\d+)\))?$",
        re.MULTILINE | re.IGNORECASE
    )
    CHERRY_PICK_PATTERN = re.compile(
        r"\(cherry\s+picked\s+from\s+commit\s+([0-9a-fA-F]{7,40})\)",
        re.IGNORECASE
    )

    @classmethod
    def parse_commit_metadata(cls, commit_message: str) -> Dict[str, Any]:
        """Extract structured CPython backport information."""
        info: Dict[str, Any] = {
            "is_cpython_backport": False,
            "target_branch": None,
            "issue_id": None,
            "summary": None,
            "pr_number": None,
            "cherry_pick_commit": None,
        }

        match_branch = cls.BRANCH_GH_PATTERN.search(commit_message)
        if match_branch:
            info["is_cpython_backport"] = True
            info["target_branch"] = match_branch.group(1)
            info["issue_id"] = match_branch.group(2)
            info["summary"] = match_branch.group(3).strip()
            info["pr_number"] = match_branch.group(4)

        match_cp = cls.CHERRY_PICK_PATTERN.search(commit_message)
        if match_cp:
            info["is_cpython_backport"] = True
            info["cherry_pick_commit"] = match_cp.group(1)

        return info
