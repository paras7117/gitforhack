"""
Conflict Resolution Orchestrator.
Combines Git origin mining, testing store, environment detector, and AI synthesizer.
"""

from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from git_provenance.core.git_wrapper import GitWrapper
from git_provenance.core.conflict_parser import ConflictParser
from git_provenance.core.origin_miner import OriginMiner
from git_provenance.core.testing_store import TestingStore
from git_provenance.core.env_detector import EnvironmentDetector
from git_provenance.core.ai_engine import AIResolutionEngine
from git_provenance.core.provenance import (
    ConflictHunk,
    HunkProvenanceContext,
    FileConflictSummary,
    ResolutionStrategy,
    CommitProvenance,
)


class ConflictResolver:
    """Orchestrates end-to-end conflict resolution with testing provenance."""

    def __init__(
        self,
        repo_path: Optional[str] = None,
        ai_engine: Optional[AIResolutionEngine] = None,
    ):
        self.git = GitWrapper(repo_path)
        self.miner = OriginMiner(self.git)
        self.testing_store = TestingStore(self.git)
        self.env_detector = EnvironmentDetector(self.git)
        self.ai = ai_engine or AIResolutionEngine()

    def analyze_file(self, relative_path: str) -> FileConflictSummary:
        """Analyze a conflicted file and construct full provenance context for every hunk."""
        full_path = self.git.repo_path / relative_path
        if not full_path.exists():
            return FileConflictSummary(file_path=relative_path, total_hunks=0)

        content = full_path.read_text(encoding="utf-8", errors="replace")
        hunks = ConflictParser.parse_content(content)
        if not hunks:
            return FileConflictSummary(file_path=relative_path, total_hunks=0)

        # Detect heads
        heads = self.git.get_merge_heads()
        head_ours = heads.get("ours")
        head_theirs = heads.get("theirs")

        hunk_contexts: List[HunkProvenanceContext] = []

        for hunk in hunks:
            # 1. Mine provenance for OURS
            prov_ours = None
            if head_ours:
                prov_ours = self.miner.extract_provenance_for_commit(head_ours)
            if not prov_ours:
                prov_ours = self.miner.trace_hunk_origin(relative_path, hunk.lines_ours, "HEAD")

            if prov_ours:
                prov_ours.test_attestation = self.testing_store.get_attestation(prov_ours.commit_hash)
                prov_ours.environment = self.env_detector.detect_environment(
                    prov_ours.commit_hash, prov_ours.branches
                )

            # 2. Mine provenance for THEIRS
            prov_theirs = None
            if head_theirs:
                prov_theirs = self.miner.extract_provenance_for_commit(head_theirs)
            if not prov_theirs:
                prov_theirs = self.miner.trace_hunk_origin(relative_path, hunk.lines_theirs, "MERGE_HEAD")

            if prov_theirs:
                prov_theirs.test_attestation = self.testing_store.get_attestation(prov_theirs.commit_hash)
                prov_theirs.environment = self.env_detector.detect_environment(
                    prov_theirs.commit_hash, prov_theirs.branches
                )

            ctx = HunkProvenanceContext(
                hunk=hunk,
                file_path=relative_path,
                provenance_ours=prov_ours,
                provenance_theirs=prov_theirs,
            )

            # Synthesize recommended resolution
            strat, code, conf, rationale, model_name = self.ai.synthesize_resolution(ctx)
            ctx.recommendation = strat
            ctx.recommended_code = code
            ctx.confidence_score = conf
            ctx.rationale = rationale
            ctx.ai_model_used = model_name

            hunk_contexts.append(ctx)

        return FileConflictSummary(
            file_path=relative_path,
            total_hunks=len(hunks),
            hunk_contexts=hunk_contexts,
        )

    def resolve_file(
        self,
        relative_path: str,
        strategy: Optional[ResolutionStrategy] = None,
        apply: bool = True,
        stage: bool = True,
    ) -> FileConflictSummary:
        """Resolve all conflicts in a file and optionally apply and stage the changes."""
        summary = self.analyze_file(relative_path)
        if summary.total_hunks == 0:
            return summary

        full_path = self.git.repo_path / relative_path
        content = full_path.read_text(encoding="utf-8", errors="replace")

        resolutions: List[Tuple[int, str]] = []
        for ctx in summary.hunk_contexts:
            if strategy == ResolutionStrategy.OURS:
                code = ctx.hunk.text_ours
            elif strategy == ResolutionStrategy.THEIRS:
                code = ctx.hunk.text_theirs
            else:
                code = ctx.recommended_code or ctx.hunk.text_ours

            resolutions.append((ctx.hunk.hunk_index, code))

        resolved_content = ConflictParser.apply_resolutions(content, resolutions)
        summary.resolved_content = resolved_content
        summary.is_fully_resolved = True

        if apply:
            full_path.write_text(resolved_content, encoding="utf-8")
            if stage:
                self.git.stage_file(relative_path)

        return summary

    def resolve_all(
        self,
        strategy: Optional[ResolutionStrategy] = None,
        apply: bool = True,
        stage: bool = True,
    ) -> List[FileConflictSummary]:
        """Resolve all currently conflicted files in the repository."""
        conflicted_files = self.git.get_conflicted_files()
        summaries = []
        for f in conflicted_files:
            s = self.resolve_file(f, strategy=strategy, apply=apply, stage=stage)
            summaries.append(s)
        return summaries
