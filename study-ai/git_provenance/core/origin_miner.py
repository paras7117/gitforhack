"""
Origin and Lineage Miner for Git Conflicts.
Identifies original commits, cherry-pick ancestry, backport references, and patch-id equivalences.
"""

import re
from typing import Optional, List, Dict, Tuple
from git_provenance.core.git_wrapper import GitWrapper
from git_provenance.core.provenance import CommitProvenance, EnvironmentStatus, TestAttestation


class OriginMiner:
    """Mines the provenance, backport lineage, and patch equivalence of conflicting code."""

    # Patterns for cherry-pick -x and backport references
    CHERRY_PICK_PATTERN = re.compile(
        r"\(cherry\s+picked\s+from\s+commit\s+([0-9a-fA-F]{7,40})\)",
        re.IGNORECASE
    )
    BACKPORT_PR_PATTERN = re.compile(
        r"(?:backport\s+of\s+#?|backport\s+from\s+|cherry-pick\s+of\s+#?|backported\s+from\s+commit\s+)([0-9a-fA-F]{7,40}|#\d+)",
        re.IGNORECASE
    )
    DJANGO_FIX_PATTERN = re.compile(r"\[([\d\.]+x?)\]\s+Fixed\s+#(\d+)", re.IGNORECASE)
    CPYTHON_GH_PATTERN = re.compile(r"(?:gh-|python/cpython#)(\d+)", re.IGNORECASE)

    def __init__(self, git: Optional[GitWrapper] = None):
        self.git = git or GitWrapper()
        self._commit_cache: Dict[str, CommitProvenance] = {}
        self._patch_id_cache: Dict[str, str] = {}

    def extract_provenance_for_commit(self, commit_hash: str) -> Optional[CommitProvenance]:
        """Extract rich provenance for a commit hash."""
        if not commit_hash:
            return None

        if commit_hash in self._commit_cache:
            return self._commit_cache[commit_hash]

        details = self.git.get_commit_details(commit_hash)
        if not details:
            return None

        full_hash = details["commit_hash"]
        short_hash = details["short_hash"]
        msg = details["message"]
        author_name = details["author_name"]
        author_email = details["author_email"]
        date = details["date"]

        # 1. Cherry-pick -x origin
        cherry_origin = None
        cp_match = self.CHERRY_PICK_PATTERN.search(msg)
        if cp_match:
            cherry_origin = cp_match.group(1)

        # 2. Backport references
        backport_refs: List[str] = []
        for match in self.BACKPORT_PR_PATTERN.finditer(msg):
            backport_refs.append(match.group(0).strip())

        for match in self.DJANGO_FIX_PATTERN.finditer(msg):
            backport_refs.append(f"Django Fixed #{match.group(2)} on branch {match.group(1)}")

        for match in self.CPYTHON_GH_PATTERN.finditer(msg):
            backport_refs.append(f"CPython Issue #{match.group(1)}")

        # 3. Patch-ID computation
        patch_id = self.git.get_commit_patch_id(full_hash)
        if patch_id:
            self._patch_id_cache[full_hash] = patch_id

        # 4. Containing branches
        branches = self.git.get_branches_containing(full_hash)

        # Build initial provenance object
        prov = CommitProvenance(
            commit_hash=full_hash,
            short_hash=short_hash,
            author_name=author_name,
            author_email=author_email,
            date=date,
            message=msg,
            branches=branches,
            cherry_pick_origin=cherry_origin,
            backport_references=backport_refs,
            patch_id=patch_id,
        )

        self._commit_cache[commit_hash] = prov
        self._commit_cache[full_hash] = prov
        self._commit_cache[short_hash] = prov
        return prov

    def find_equivalent_commit(self, patch_id: str, candidate_branches: List[str]) -> Optional[Tuple[str, str]]:
        """
        Scan candidate branches for a commit with the identical patch-id.
        Returns (commit_hash, branch_name) if found.
        This answers: 'How can the system identify identical changes when their code has been modified?'
        """
        if not patch_id:
            return None

        for branch in candidate_branches:
            try:
                log_out = self.git.run(["log", "--format=%H", "-n", "30", branch], check=False)
                for c in log_out.splitlines():
                    c_clean = c.strip()
                    if not c_clean:
                        continue
                    c_patch_id = self._patch_id_cache.get(c_clean)
                    if not c_patch_id:
                        c_patch_id = self.git.get_commit_patch_id(c_clean)
                        if c_patch_id:
                            self._patch_id_cache[c_clean] = c_patch_id

                    if c_patch_id == patch_id:
                        return (c_clean, branch)
            except Exception:
                continue

        return None

    def trace_hunk_origin(self, file_path: str, lines: List[str], rev: str) -> Optional[CommitProvenance]:
        """
        Use git log/blame to find the exact commit that introduced the hunk in `rev`.
        """
        if not lines:
            return None

        # Look through git log for the most recent commit touching the file in rev
        try:
            log_out = self.git.run(["log", "-1", "--format=%H", rev, "--", file_path], check=False)
            if log_out:
                commit_hash = log_out.strip()
                return self.extract_provenance_for_commit(commit_hash)
        except Exception:
            pass

        return None
