"""
Testing Provenance Storage and Attestation Ledger.
Manages Git Notes (refs/notes/test-provenance), commit trailers, and portable cache.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from git_provenance.core.git_wrapper import GitWrapper
from git_provenance.core.provenance import TestAttestation, TestStatus, EnvironmentStatus


class TestingStore:
    """Manages reading and writing testing provenance across Git Notes, Trailers, and Manifests."""
    __test__ = False

    NOTES_REF = "test-provenance"
    CI_NOTES_REF = "ci-attestation"
    CACHE_FILE = ".git-provenance.json"

    def __init__(self, git: Optional[GitWrapper] = None):
        self.git = git or GitWrapper()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_cache()

    def _get_cache_path(self) -> Path:
        return self.git.repo_path / self.CACHE_FILE

    def _load_cache(self) -> None:
        cache_path = self._get_cache_path()
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._cache = data
            except Exception:
                self._cache = {}

    def _save_cache(self) -> None:
        try:
            cache_path = self._get_cache_path()
            cache_path.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")
        except Exception:
            pass

    def record_attestation(
        self,
        commit_hash: str,
        status: TestStatus,
        suite_name: str = "pytest",
        ci_run_id: Optional[str] = None,
        ci_url: Optional[str] = None,
        coverage_pct: Optional[float] = None,
        environment: Optional[EnvironmentStatus] = None,
        signer: Optional[str] = None,
    ) -> TestAttestation:
        """
        Record testing attestation for a commit.
        Saves into:
        1. Git Notes (`refs/notes/test-provenance`)
        2. Portable `.git-provenance.json`
        """
        attestation = TestAttestation(
            status=status,
            suite_name=suite_name,
            ci_run_id=ci_run_id,
            ci_url=ci_url,
            coverage_pct=coverage_pct,
            timestamp=datetime.now(timezone.utc).isoformat(),
            signer=signer or "git-prov-attestor",
        )

        note_data = {
            "attestation": attestation.to_dict(),
            "environment": environment.value if environment else EnvironmentStatus.UNKNOWN.value,
            "recorded_at": attestation.timestamp,
        }

        # 1. Write to Git Notes
        json_str = json.dumps(note_data, indent=2)
        self.git.add_git_note(self.NOTES_REF, commit_hash, json_str)

        # 2. Update local cache
        self._cache[commit_hash] = note_data
        self._save_cache()

        return attestation

    def get_attestation(self, commit_hash: str) -> TestAttestation:
        """
        Retrieve testing attestation for a commit.
        Checks:
        1. Git Notes (refs/notes/test-provenance)
        2. Commit trailers (X-Test-Status, etc.)
        3. Local provenance manifest cache
        """
        if not commit_hash:
            return TestAttestation(status=TestStatus.UNKNOWN)

        # 1. Try Git Notes
        note_content = self.git.get_git_note(self.NOTES_REF, commit_hash)
        if note_content:
            try:
                data = json.loads(note_content)
                if "attestation" in data:
                    return TestAttestation.from_dict(data["attestation"])
                return TestAttestation.from_dict(data)
            except Exception:
                pass

        # 2. Try Commit Trailers (resilient when cloned without notes)
        trailers = self.git.get_commit_trailers(commit_hash)
        if "X-Test-Status" in trailers:
            t_status = trailers.get("X-Test-Status", "UNKNOWN").upper()
            try:
                status = TestStatus(t_status)
            except ValueError:
                status = TestStatus.UNKNOWN

            coverage = None
            if "X-Coverage" in trailers:
                try:
                    coverage = float(trailers["X-Coverage"].replace("%", ""))
                except Exception:
                    pass

            return TestAttestation(
                status=status,
                suite_name=trailers.get("X-Test-Suite", "ci"),
                ci_run_id=trailers.get("X-CI-Run"),
                coverage_pct=coverage,
            )

        # 3. Try Local Cache
        if commit_hash in self._cache:
            entry = self._cache[commit_hash]
            if "attestation" in entry:
                return TestAttestation.from_dict(entry["attestation"])
            return TestAttestation.from_dict(entry)

        return TestAttestation(status=TestStatus.UNTESTED)

    def fetch_remote_notes(self, remote: str = "origin") -> bool:
        """Fetch Git notes from remote repository so provenance is transferred upon clone."""
        try:
            self.git.run(
                ["fetch", remote, f"refs/notes/{self.NOTES_REF}:refs/notes/{self.NOTES_REF}"],
                check=False
            )
            return True
        except Exception:
            return False

    def push_notes(self, remote: str = "origin") -> bool:
        """Push Git notes to remote repository so downstream clones receive provenance."""
        try:
            self.git.run(["push", remote, f"refs/notes/{self.NOTES_REF}"], check=False)
            return True
        except Exception:
            return False
