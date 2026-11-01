"""
Lightweight Web API Server and Static File Handler for git-provenance UI.
Provides REST API endpoints for conflict inspection, live resolution, and test attestation.
"""

import os
import json
import mimetypes
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from typing import Optional, Dict, Any

from git_provenance.core.git_wrapper import GitWrapper
from git_provenance.core.resolver import ConflictResolver
from git_provenance.core.provenance import ResolutionStrategy, TestStatus, EnvironmentStatus
from git_provenance.core.testing_store import TestingStore
from git_provenance.core.origin_miner import OriginMiner
from git_provenance.core.ai_engine import AIResolutionEngine
from git_provenance.core.conflict_parser import ConflictParser


STATIC_DIR = Path(__file__).resolve().parent / "static"


class GitProvenanceAPIHandler(SimpleHTTPRequestHandler):
    """Handles REST API queries and serves the rich claymorphic/glassmorphic UI."""

    def __init__(self, *args, repo_path: Optional[str] = None, **kwargs):
        self.repo_path = repo_path or os.getcwd()
        self.git = GitWrapper(self.repo_path)
        self.ai = AIResolutionEngine()
        self.resolver = ConflictResolver(self.repo_path, ai_engine=self.ai)
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/api/status":
            conflicted = self.git.get_conflicted_files()
            heads = self.git.get_merge_heads()
            self._send_json({
                "repo_path": str(self.git.repo_path),
                "is_inside_work_tree": self.git.is_inside_work_tree(),
                "head_commit": self.git.get_head_commit(),
                "merge_heads": heads,
                "conflicted_files": conflicted,
                "total_conflicts": len(conflicted),
            })
            return

        elif path == "/api/file":
            file_path = query.get("path", [""])[0]
            if not file_path:
                self._send_json({"error": "Missing 'path' query parameter"}, status=400)
                return

            full_path = self.git.repo_path / file_path
            if not full_path.exists():
                self._send_json({"error": f"File '{file_path}' not found"}, status=404)
                return

            summary = self.resolver.analyze_file(file_path)
            content = full_path.read_text(encoding="utf-8", errors="replace")
            data = summary.to_dict()
            data["raw_content"] = content
            self._send_json(data)
            return

        elif path == "/api/scenarios":
            # List available preset evaluation scenarios
            scenarios = [
                {
                    "id": "django",
                    "title": "Django ORM Security Backport (#34567)",
                    "description": "Backport of query compiler fix from main to stable/4.2.x with conflicting outer joins.",
                    "base_branch": "stable/4.2.x",
                    "incoming_branch": "main",
                    "sample_path": "examples/django_backport_scenario/input/conflicted_views.py"
                },
                {
                    "id": "cpython",
                    "title": "CPython Asyncio Event Loop (gh-108278)",
                    "description": "Cherry-pick backport to 3.12 with Miss Islington bot metadata and patch-id matching.",
                    "base_branch": "3.12",
                    "incoming_branch": "main",
                    "sample_path": "examples/cpython_backport_scenario/input/conflicted_asyncio.py"
                },
                {
                    "id": "enterprise",
                    "title": "FinTech Multi-Branch Payment Gateway",
                    "description": "Production PCI hotfix (100% test coverage) vs unverified feature branch.",
                    "base_branch": "production",
                    "incoming_branch": "feature/async-webhooks",
                    "sample_path": "examples/multi_branch_enterprise/input/conflicted_payment_service.py"
                }
            ]
            self._send_json(scenarios)
            return

        elif path == "/api/load-scenario":
            scenario_id = query.get("id", ["django"])[0]
            root = Path(self.repo_path)
            scenario_map = {
                "django": (root / "examples/django_backport_scenario/input/conflicted_views.py", "myapp/views.py"),
                "cpython": (root / "examples/cpython_backport_scenario/input/conflicted_asyncio.py", "Lib/asyncio/proactor_events.py"),
                "enterprise": (root / "examples/multi_branch_enterprise/input/conflicted_payment_service.py", "services/payment.py"),
            }
            if scenario_id not in scenario_map:
                self._send_json({"error": "Unknown scenario"}, status=400)
                return

            file_on_disk, rel_name = scenario_map[scenario_id]
            if not file_on_disk.exists():
                self._send_json({"error": "Scenario input file not found on disk"}, status=404)
                return

            raw_text = file_on_disk.read_text(encoding="utf-8")
            hunks = ConflictParser.parse_content(raw_text)
            
            # Synthesize provenance for scenario
            from git_provenance.core.provenance import (
                ConflictHunk, HunkProvenanceContext, CommitProvenance, EnvironmentStatus, TestStatus, TestAttestation
            )
            hunk_contexts = []
            for h in hunks:
                if scenario_id == "django":
                    p_ours = CommitProvenance(
                        commit_hash="c4b12e891234567890abcdef1234567890abcdef",
                        short_hash="c4b12e8",
                        author_name="Django Maintainer",
                        author_email="core@djangoproject.com",
                        date="2026-10-25",
                        message="[4.2.x] Hotfix: Preserve fast indexed lookup for stable release",
                        environment=EnvironmentStatus.UAT,
                        test_attestation=TestAttestation(status=TestStatus.PASSED, suite_name="django-tests")
                    )
                    p_theirs = CommitProvenance(
                        commit_hash="6e1a49f82d3b567890abcdef1234567890abcdef",
                        short_hash="6e1a49f",
                        author_name="Django Security ORM Team",
                        author_email="orm@djangoproject.com",
                        date="2026-10-26",
                        message="[4.2.x] Fixed #34567 -- Corrected outer join order in ORM query compiler.\nBackport of 6e1a49f from main.",
                        environment=EnvironmentStatus.PRODUCTION,
                        test_attestation=TestAttestation(status=TestStatus.PASSED, suite_name="django-tests-full", coverage_pct=98.4),
                        backport_references=["Django #34567 (Upstream 6e1a49f)"]
                    )
                elif scenario_id == "cpython":
                    p_ours = CommitProvenance(
                        commit_hash="8f12c9a10123456789abcdef123456789abcdef0",
                        short_hash="8f12c9a",
                        author_name="CPython Core Dev",
                        author_email="python-dev@python.org",
                        date="2026-10-28",
                        message="Update 3.12 proactor internal flags",
                        environment=EnvironmentStatus.DEVELOPMENT,
                        test_attestation=TestAttestation(status=TestStatus.UNTESTED)
                    )
                    p_theirs = CommitProvenance(
                        commit_hash="7a82b9e6fa436c0a0c441b8a514dcf50db9011f0",
                        short_hash="7a82b9e",
                        author_name="Miss Islington (bot)",
                        author_email="miss-islington@python.org",
                        date="2026-10-28",
                        message="[3.12] gh-108278: Disallow nested asyncio event loops on Windows (GH-108300)\n\n(cherry picked from commit 7a82b9e6fa436c0a0c441b8a514dcf50db9011f0)",
                        environment=EnvironmentStatus.PRODUCTION,
                        test_attestation=TestAttestation(status=TestStatus.PASSED, suite_name="test_asyncio", coverage_pct=99.1),
                        cherry_pick_origin="7a82b9e6fa436c0a0c441b8a514dcf50db9011f0",
                        backport_references=["CPython gh-108278 (PR #108300)"]
                    )
                else: # enterprise
                    p_ours = CommitProvenance(
                        commit_hash="1f8e3a2b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f",
                        short_hash="1f8e3a2",
                        author_name="SecOps Engineer",
                        author_email="security@fintech.io",
                        date="2026-10-31",
                        message="fix(pci): Idempotent exponential retry for timeout failures",
                        environment=EnvironmentStatus.PRODUCTION,
                        test_attestation=TestAttestation(status=TestStatus.PASSED, suite_name="pci-compliance-e2e", coverage_pct=100.0, ci_run_id="8921")
                    )
                    p_theirs = CommitProvenance(
                        commit_hash="9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d",
                        short_hash="9e8d7c6",
                        author_name="Junior Dev",
                        author_email="intern@fintech.io",
                        date="2026-10-31",
                        message="feat(payments): Draft async webhook queue",
                        environment=EnvironmentStatus.UNVERIFIED,
                        test_attestation=TestAttestation(status=TestStatus.UNTESTED)
                    )

                ctx = HunkProvenanceContext(
                    hunk=h,
                    file_path=rel_name,
                    provenance_ours=p_ours,
                    provenance_theirs=p_theirs
                )
                strat, code, conf, rationale, model = self.ai.synthesize_resolution(ctx)
                ctx.recommendation = strat
                ctx.recommended_code = code
                ctx.confidence_score = conf
                ctx.rationale = rationale
                ctx.ai_model_used = model
                hunk_contexts.append(ctx)

            self._send_json({
                "file_path": rel_name,
                "total_hunks": len(hunks),
                "raw_content": raw_text,
                "hunk_contexts": [c.to_dict() for c in hunk_contexts]
            })
            return

        # Fallback to serving static assets
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path == "/api/resolve-hunk":
            hunk_raw = payload.get("hunk", {})
            hunk = ConflictHunk(
                hunk_index=hunk_raw.get("hunk_index", 0),
                start_line=hunk_raw.get("start_line", 1),
                end_line=hunk_raw.get("end_line", 5),
                header_ours=hunk_raw.get("header_ours", "HEAD"),
                header_theirs=hunk_raw.get("header_theirs", "THEIRS"),
                header_base=hunk_raw.get("header_base"),
                lines_ours=[line + "\n" if not line.endswith("\n") else line for line in hunk_raw.get("lines_ours", [])],
                lines_theirs=[line + "\n" if not line.endswith("\n") else line for line in hunk_raw.get("lines_theirs", [])],
                lines_base=[line + "\n" if not line.endswith("\n") else line for line in hunk_raw.get("lines_base", [])] if "lines_base" in hunk_raw and hunk_raw["lines_base"] is not None else None,
            )
            ctx = HunkProvenanceContext(
                hunk=hunk,
                file_path=payload.get("file_path", "sample.py"),
            )
            strat, code, conf, rationale, model = self.ai.synthesize_resolution(ctx)
            self._send_json({
                "strategy": strat.value,
                "resolved_code": code,
                "confidence_score": conf,
                "rationale": rationale,
                "model_used": model,
            })
            return

        elif path == "/api/attest":
            commit = payload.get("commit", "HEAD")
            status = payload.get("status", "passed").upper()
            env = payload.get("env", "dev").upper()
            suite = payload.get("suite", "pytest")
            coverage = payload.get("coverage")
            ci_run = payload.get("ci_run")

            try:
                commit_sha = self.git.run(["rev-parse", commit], check=True)
            except Exception:
                commit_sha = "1a2b3c4d5e6f7890"

            testing_store = TestingStore(self.git)
            att = testing_store.record_attestation(
                commit_hash=commit_sha,
                status=TestStatus(status),
                suite_name=suite,
                ci_run_id=ci_run,
                coverage_pct=float(coverage) if coverage is not None else None,
                environment=EnvironmentStatus(env),
            )
            self._send_json({
                "success": True,
                "commit_hash": commit_sha,
                "attestation": att.to_dict(),
            })
            return

        self._send_json({"error": "Unknown POST endpoint"}, status=404)


def run_server(port: int = 8765, repo_path: Optional[str] = None):
    """Start local web UI server."""
    server_address = ("", port)
    handler = lambda *args, **kwargs: GitProvenanceAPIHandler(*args, repo_path=repo_path, **kwargs)
    httpd = HTTPServer(server_address, handler)
    print(f"Git-Provenance UI running at http://localhost:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()
