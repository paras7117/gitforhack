"""
Data models and representations for Git Conflict Provenance and Testing Attestations.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any


class EnvironmentStatus(str, Enum):
    PRODUCTION = "PRODUCTION"
    UAT = "UAT"
    STAGING = "STAGING"
    DEVELOPMENT = "DEVELOPMENT"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"


class TestStatus(str, Enum):
    __test__ = False
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    UNTESTED = "UNTESTED"
    UNKNOWN = "UNKNOWN"


class ResolutionStrategy(str, Enum):
    OURS = "ours"
    THEIRS = "theirs"
    UNION = "union"
    SYNTHESIZED_AI = "synthesized_ai"
    HEURISTIC_PRESERVATION = "heuristic_preservation"
    MANUAL = "manual"


@dataclass
class TestAttestation:
    """Represents testing verification attached to a commit or patch."""
    __test__ = False
    status: TestStatus = TestStatus.UNKNOWN
    suite_name: str = "default"
    ci_run_id: Optional[str] = None
    ci_url: Optional[str] = None
    coverage_pct: Optional[float] = None
    passed_tests: int = 0
    failed_tests: int = 0
    timestamp: Optional[str] = None
    signer: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestAttestation":
        if not data:
            return cls()
        status_val = data.get("status", "UNKNOWN")
        try:
            status = TestStatus(status_val)
        except ValueError:
            status = TestStatus.UNKNOWN
        return cls(
            status=status,
            suite_name=data.get("suite_name", "default"),
            ci_run_id=data.get("ci_run_id"),
            ci_url=data.get("ci_url"),
            coverage_pct=data.get("coverage_pct"),
            passed_tests=data.get("passed_tests", 0),
            failed_tests=data.get("failed_tests", 0),
            timestamp=data.get("timestamp"),
            signer=data.get("signer"),
        )


@dataclass
class CommitProvenance:
    """Historical context and lineage of a commit introducing code."""
    commit_hash: str
    short_hash: str
    author_name: str
    author_email: str
    date: str
    message: str
    branches: List[str] = field(default_factory=list)
    environment: EnvironmentStatus = EnvironmentStatus.UNKNOWN
    test_attestation: TestAttestation = field(default_factory=TestAttestation)
    patch_id: Optional[str] = None
    cherry_pick_origin: Optional[str] = None  # e.g., original commit hash from cherry-pick -x
    backport_references: List[str] = field(default_factory=list)  # e.g., PRs, issues, Django/CPython links
    is_production_tested: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["environment"] = self.environment.value
        d["test_attestation"] = self.test_attestation.to_dict()
        return d


@dataclass
class ConflictHunk:
    """A single conflict region inside a file."""
    hunk_index: int
    start_line: int
    end_line: int
    header_ours: str
    header_theirs: str
    header_base: Optional[str] = None
    lines_ours: List[str] = field(default_factory=list)
    lines_theirs: List[str] = field(default_factory=list)
    lines_base: Optional[List[str]] = None  # Available when diff3 or zdiff3 is enabled

    @property
    def text_ours(self) -> str:
        return "".join(self.lines_ours)

    @property
    def text_theirs(self) -> str:
        return "".join(self.lines_theirs)

    @property
    def text_base(self) -> Optional[str]:
        return "".join(self.lines_base) if self.lines_base is not None else None


@dataclass
class HunkProvenanceContext:
    """Full provenance context surrounding a single conflict hunk."""
    hunk: ConflictHunk
    file_path: str
    provenance_ours: Optional[CommitProvenance] = None
    provenance_theirs: Optional[CommitProvenance] = None
    provenance_base: Optional[CommitProvenance] = None
    recommendation: ResolutionStrategy = ResolutionStrategy.MANUAL
    recommended_code: Optional[str] = None
    confidence_score: float = 0.0
    rationale: str = ""
    ai_model_used: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "hunk_index": self.hunk.hunk_index,
            "start_line": self.hunk.start_line,
            "end_line": self.hunk.end_line,
            "provenance_ours": self.provenance_ours.to_dict() if self.provenance_ours else None,
            "provenance_theirs": self.provenance_theirs.to_dict() if self.provenance_theirs else None,
            "recommendation": self.recommendation.value,
            "confidence_score": self.confidence_score,
            "rationale": self.rationale,
            "ai_model_used": self.ai_model_used,
        }


@dataclass
class FileConflictSummary:
    """Summary of all conflicts and resolution status for a single file."""
    file_path: str
    total_hunks: int
    hunk_contexts: List[HunkProvenanceContext] = field(default_factory=list)
    is_fully_resolved: bool = False
    resolved_content: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "total_hunks": self.total_hunks,
            "is_fully_resolved": self.is_fully_resolved,
            "hunk_contexts": [h.to_dict() for h in self.hunk_contexts],
        }
