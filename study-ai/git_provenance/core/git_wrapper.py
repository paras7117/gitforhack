"""
Git wrapper utilities for extracting commit metadata, patch-ids, notes, and trailers.
"""

import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any


class GitExecutionError(Exception):
    """Exception raised when a git command fails."""
    pass


class GitWrapper:
    """Robust interface for interacting with local Git repositories."""

    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = Path(repo_path).resolve() if repo_path else Path.cwd()
        self.git_bin = shutil.which("git") or "git"

    def run(self, args: List[str], check: bool = True, input_str: Optional[str] = None) -> str:
        """Run a git command in the repository directory."""
        cmd = [self.git_bin] + args
        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.repo_path),
                input=input_str,
                text=True,
                capture_output=True,
                check=check
            )
            return res.stdout.strip()
        except subprocess.CalledProcessError as e:
            if check:
                raise GitExecutionError(f"Git command failed: {' '.join(cmd)}\nStderr: {e.stderr.strip()}") from e
            return e.stdout.strip()

    def is_inside_work_tree(self) -> bool:
        """Check if current directory is a valid git repository."""
        try:
            out = self.run(["rev-parse", "--is-inside-work-tree"], check=False)
            return out == "true"
        except Exception:
            return False

    def get_repo_root(self) -> Path:
        """Get the root path of the git repository."""
        out = self.run(["rev-parse", "--show-toplevel"])
        return Path(out)

    def get_head_commit(self) -> Optional[str]:
        """Get current HEAD commit hash."""
        try:
            return self.run(["rev-parse", "HEAD"], check=False) or None
        except Exception:
            return None

    def get_conflicted_files(self) -> List[str]:
        """List files currently in conflict state (unmerged)."""
        try:
            out = self.run(["diff", "--name-only", "--diff-filter=U"], check=False)
            if not out:
                return []
            return [line.strip() for line in out.splitlines() if line.strip()]
        except Exception:
            return []

    def get_merge_heads(self) -> Dict[str, Optional[str]]:
        """
        Identify what operation is in progress (MERGE, REBASE, CHERRY-PICK)
        and find the commit hashes of OURS and THEIRS.
        """
        heads = {"ours": None, "theirs": None, "operation": "UNKNOWN"}
        try:
            heads["ours"] = self.get_head_commit()
        except Exception:
            pass

        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            try:
                git_dir = Path(self.run(["rev-parse", "--git-dir"]))
            except Exception:
                pass

        if (git_dir / "MERGE_HEAD").exists():
            heads["operation"] = "MERGE"
            try:
                heads["theirs"] = (git_dir / "MERGE_HEAD").read_text().strip().splitlines()[0]
            except Exception:
                pass
        elif (git_dir / "CHERRY_PICK_HEAD").exists():
            heads["operation"] = "CHERRY-PICK"
            try:
                heads["theirs"] = (git_dir / "CHERRY_PICK_HEAD").read_text().strip().splitlines()[0]
            except Exception:
                pass
        elif (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
            heads["operation"] = "REBASE"
            for candidate in ["stopped-sha", "original-commit"]:
                rebase_dir = git_dir / "rebase-merge"
                if not rebase_dir.exists():
                    rebase_dir = git_dir / "rebase-apply"
                target_file = rebase_dir / candidate
                if target_file.exists():
                    heads["theirs"] = target_file.read_text().strip()
                    break

        return heads

    def calculate_patch_id(self, patch_diff: str) -> Optional[str]:
        """
        Compute git patch-id for a given unified diff text.
        git patch-id produces a stable SHA1 that ignores whitespace and line numbers!
        """
        if not patch_diff or not patch_diff.strip():
            return None
        try:
            out = self.run(["patch-id", "--stable"], check=False, input_str=patch_diff)
            if out:
                parts = out.strip().split()
                if parts:
                    return parts[0]
            return None
        except Exception:
            return None

    def get_commit_patch_id(self, commit_hash: str) -> Optional[str]:
        """Get git patch-id for a single commit."""
        try:
            diff_text = self.run(["show", commit_hash, "--format="], check=False)
            if diff_text:
                return self.calculate_patch_id(diff_text)
            return None
        except Exception:
            return None

    def get_cherry_status(self, upstream: str, head: str = "HEAD") -> List[Tuple[str, str]]:
        """
        Run `git cherry <upstream> <head>` to see which commits from <head>
        are equivalent to commits in <upstream>.
        Returns list of (status, commit_hash) where status is '+' (unapplied) or '-' (applied).
        """
        try:
            out = self.run(["cherry", upstream, head], check=False)
            results = []
            for line in out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    results.append((parts[0], parts[1]))
            return results
        except Exception:
            return []

    def get_commit_details(self, commit_hash: str) -> Optional[Dict[str, Any]]:
        """Extract comprehensive commit metadata: author, date, message, trailers."""
        try:
            # Format: Hash %H | Author %an <%ae> | Date %aI | Subject %s | Body %b
            fmt = "%H%x00%h%x00%an%x00%ae%x00%aI%x00%s%x00%B"
            out = self.run(["show", "-s", f"--format={fmt}", commit_hash], check=False)
            if not out:
                return None
            fields = out.split("\x00")
            if len(fields) < 7:
                return None

            full_hash, short_hash, author_name, author_email, date, subject, body = fields[:7]
            trailers = self.get_commit_trailers(commit_hash)

            return {
                "commit_hash": full_hash,
                "short_hash": short_hash,
                "author_name": author_name,
                "author_email": author_email,
                "date": date,
                "subject": subject,
                "message": body.strip(),
                "trailers": trailers,
            }
        except Exception:
            return None

    def get_commit_trailers(self, commit_hash: str) -> Dict[str, str]:
        """Extract Git commit trailers (e.g., X-Test-Status, Cherry-picked-from)."""
        try:
            out = self.run(["log", "-1", "--format=%(trailers:keyonly,separator=%x00)", commit_hash], check=False)
            keys = [k.strip() for k in out.split("\x00") if k.strip()]
            trailers = {}
            for k in keys:
                val = self.run(["log", "-1", f"--format=%(trailers:key={k},valueonly)", commit_hash], check=False)
                trailers[k] = val.strip()
            return trailers
        except Exception:
            return {}

    def get_branches_containing(self, commit_hash: str) -> List[str]:
        """List all branches (local and remote) containing the specified commit."""
        try:
            out = self.run(["branch", "-a", "--contains", commit_hash], check=False)
            branches = []
            for line in out.splitlines():
                cleaned = line.replace("*", "").strip()
                if "->" in cleaned:
                    continue
                if cleaned:
                    branches.append(cleaned)
            return branches
        except Exception:
            return []

    def get_git_note(self, ref_note: str, commit_hash: str) -> Optional[str]:
        """Read a git note attached to a commit under a specific notes ref."""
        try:
            out = self.run(["notes", f"--ref={ref_note}", "show", commit_hash], check=False)
            return out.strip() if out else None
        except Exception:
            return None

    def add_git_note(self, ref_note: str, commit_hash: str, note_content: str, force: bool = True) -> bool:
        """Attach a git note to a commit."""
        args = ["notes", f"--ref={ref_note}", "add"]
        if force:
            args.append("-f")
        args.extend(["-m", note_content, commit_hash])
        try:
            self.run(args, check=True)
            return True
        except Exception:
            return False

    def get_merge_base(self, commit1: str, commit2: str) -> Optional[str]:
        """Find common ancestor merge-base between two commits."""
        try:
            out = self.run(["merge-base", commit1, commit2], check=False)
            return out.strip() or None
        except Exception:
            return None

    def blame_line_commit(self, file_path: str, line_no: int, rev: str = "HEAD") -> Optional[str]:
        """Identify which commit touched a specific line in a revision."""
        try:
            out = self.run(["blame", f"-L{line_no},{line_no}", "-s", "-l", rev, "--", file_path], check=False)
            if out:
                commit_hash = out.split()[0].replace("^", "")
                return commit_hash
            return None
        except Exception:
            return None

    def stage_file(self, file_path: str) -> bool:
        """Stage a resolved file."""
        try:
            self.run(["add", file_path], check=True)
            return True
        except Exception:
            return False

    def create_commit(self, message: str, trailers: Optional[Dict[str, str]] = None) -> str:
        """
        Create a standard Git commit enriched with provenance trailers.
        Trailers remain 100% compliant with standard Git trailer conventions.
        """
        commit_msg = message.strip()
        if trailers:
            commit_msg += "\n\n"
            for key, val in trailers.items():
                commit_msg += f"{key}: {val}\n"

        self.run(["commit", "-m", commit_msg], check=True)
        return self.get_head_commit() or ""
