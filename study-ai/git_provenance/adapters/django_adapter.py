"""
Django Backport Lineage Adapter.
Parses Django repository commit message conventions, Trac ticket references, and branch backports.
"""

import re
from typing import Optional, Dict, Any


class DjangoBackportAdapter:
    """Specialized adapter for Django backport commit semantics."""

    # Examples:
    # [4.2.x] Fixed #34567 -- Resolved database connection pool exhaustion.
    # Backport of 5a89dfc from main.
    BRANCH_FIX_PATTERN = re.compile(r"\[([\d\.x]+)\]\s+Fixed\s+#(\d+)\s*--\s*(.*)", re.IGNORECASE | re.MULTILINE)
    BACKPORT_OF_PATTERN = re.compile(r"Backport\s+of\s+([0-9a-fA-F]{7,40})\s+from\s+([a-zA-Z0-9_\-\./]+)", re.IGNORECASE | re.MULTILINE)
    TRAC_TICKET_PATTERN = re.compile(r"(?:Fixed|Refs|Closes)\s+#(\d+)", re.IGNORECASE)

    @classmethod
    def parse_commit_metadata(cls, commit_message: str) -> Dict[str, Any]:
        """Extract structured Django backport information from commit message."""
        info: Dict[str, Any] = {
            "is_django_backport": False,
            "target_branch": None,
            "ticket_id": None,
            "summary": None,
            "upstream_commit": None,
            "upstream_branch": None,
        }

        # Check [X.Y.x] Fixed #12345
        match_branch = cls.BRANCH_FIX_PATTERN.search(commit_message)
        if match_branch:
            info["is_django_backport"] = True
            info["target_branch"] = match_branch.group(1)
            info["ticket_id"] = match_branch.group(2)
            info["summary"] = match_branch.group(3).strip()

        # Check Backport of <sha> from <branch>
        match_backport = cls.BACKPORT_OF_PATTERN.search(commit_message)
        if match_backport:
            info["is_django_backport"] = True
            info["upstream_commit"] = match_backport.group(1)
            info["upstream_branch"] = match_backport.group(2).rstrip(".")

        # Fallback Trac ticket check
        if not info["ticket_id"]:
            match_ticket = cls.TRAC_TICKET_PATTERN.search(commit_message)
            if match_ticket:
                info["ticket_id"] = match_ticket.group(1)

        return info
