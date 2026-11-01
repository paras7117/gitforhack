"""
Conflict file parser supporting standard 2-way, diff3, and zdiff3 conflict formats.
"""

import re
from pathlib import Path
from typing import List, Tuple, Optional
from git_provenance.core.provenance import ConflictHunk


class ConflictParseError(Exception):
    """Raised when a conflict marker structure is malformed."""
    pass


class ConflictParser:
    """Parses files with git conflict markers into structured ConflictHunk objects."""

    MARKER_START = re.compile(r"^<{7}\s*(.*)$", re.MULTILINE)
    MARKER_BASE = re.compile(r"^\|{7}\s*(.*)$", re.MULTILINE)
    MARKER_DIVIDER = re.compile(r"^={7}\s*$", re.MULTILINE)
    MARKER_END = re.compile(r"^>{7}\s*(.*)$", re.MULTILINE)

    @classmethod
    def has_conflicts(cls, content: str) -> bool:
        """Check if the content contains git conflict markers."""
        return bool(cls.MARKER_START.search(content) and cls.MARKER_END.search(content))

    @classmethod
    def parse_file(cls, file_path: Path) -> List[ConflictHunk]:
        """Read and parse a file from disk."""
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return cls.parse_content(content)

    @classmethod
    def parse_content(cls, content: str) -> List[ConflictHunk]:
        """Parse string content into a list of ConflictHunks."""
        lines = content.splitlines(keepends=True)
        hunks: List[ConflictHunk] = []

        in_conflict = False
        in_base = False
        in_theirs = False

        start_line = 0
        header_ours = ""
        header_base: Optional[str] = None
        header_theirs = ""

        lines_ours: List[str] = []
        lines_base: Optional[List[str]] = None
        lines_theirs: List[str] = []

        hunk_index = 0

        for idx, line in enumerate(lines, start=1):
            start_match = cls.MARKER_START.match(line)
            base_match = cls.MARKER_BASE.match(line)
            div_match = cls.MARKER_DIVIDER.match(line)
            end_match = cls.MARKER_END.match(line)

            if start_match and not in_conflict:
                in_conflict = True
                in_base = False
                in_theirs = False
                start_line = idx
                header_ours = start_match.group(1).strip()
                header_base = None
                lines_ours = []
                lines_base = None
                lines_theirs = []
            elif base_match and in_conflict and not in_theirs:
                in_base = True
                header_base = base_match.group(1).strip()
                lines_base = []
            elif div_match and in_conflict:
                in_base = False
                in_theirs = True
            elif end_match and in_conflict:
                in_conflict = False
                in_theirs = False
                header_theirs = end_match.group(1).strip()

                hunks.append(
                    ConflictHunk(
                        hunk_index=hunk_index,
                        start_line=start_line,
                        end_line=idx,
                        header_ours=header_ours,
                        header_theirs=header_theirs,
                        header_base=header_base,
                        lines_ours=lines_ours,
                        lines_theirs=lines_theirs,
                        lines_base=lines_base,
                    )
                )
                hunk_index += 1
            else:
                if in_conflict:
                    if in_theirs:
                        lines_theirs.append(line)
                    elif in_base:
                        if lines_base is not None:
                            lines_base.append(line)
                    else:
                        lines_ours.append(line)

        return hunks

    @classmethod
    def apply_resolutions(cls, original_content: str, resolutions: List[Tuple[int, str]]) -> str:
        """
        Replaces each conflict hunk in the original content with the chosen resolution.
        resolutions is a list of tuples: (hunk_index, replacement_code).
        """
        hunks = cls.parse_content(original_content)
        res_map = dict(resolutions)

        lines = original_content.splitlines(keepends=True)
        result_lines: List[str] = []

        # Track which line numbers in original_content correspond to hunks
        hunk_ranges = {h.hunk_index: (h.start_line - 1, h.end_line) for h in hunks}

        current_line = 0
        num_lines = len(lines)

        while current_line < num_lines:
            matched_hunk = None
            for h_idx, (s_idx, e_idx) in hunk_ranges.items():
                if current_line == s_idx:
                    matched_hunk = (h_idx, s_idx, e_idx)
                    break

            if matched_hunk:
                h_idx, s_idx, e_idx = matched_hunk
                replacement = res_map.get(h_idx)
                if replacement is not None:
                    # Append replacement text (ensuring proper trailing newline if original had it)
                    if replacement and not replacement.endswith("\n"):
                        replacement += "\n"
                    result_lines.append(replacement)
                else:
                    # Leave original hunk untouched
                    result_lines.extend(lines[s_idx:e_idx])
                current_line = e_idx
            else:
                result_lines.append(lines[current_line])
                current_line += 1

        return "".join(result_lines)
