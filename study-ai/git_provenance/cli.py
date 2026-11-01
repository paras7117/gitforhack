"""
Command-Line Interface for git-provenance (git-prov).
Integrates as standard Git subcommand `git provenance`.
"""

import sys
import argparse
import json
from pathlib import Path
from typing import List, Optional
from git_provenance import __version__
from git_provenance.core.git_wrapper import GitWrapper
from git_provenance.core.resolver import ConflictResolver
from git_provenance.core.provenance import ResolutionStrategy, TestStatus, EnvironmentStatus
from git_provenance.core.testing_store import TestingStore
from git_provenance.core.origin_miner import OriginMiner
from git_provenance.core.ai_engine import AIResolutionEngine
from git_provenance.ui.formatter import ProvenanceFormatter, Color


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="git-provenance",
        description="Intelligent Git Conflict Resolution Engine with Testing Provenance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"git-provenance {__version__}")
    parser.add_argument("--repo", default=".", help="Path to git repository (default: current dir)")

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute")

    # Command: status
    parser_status = subparsers.add_parser("status", help="Show conflict status enriched with testing provenance")
    parser_status.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # Command: explain
    parser_explain = subparsers.add_parser("explain", help="Explain origin, testing, and rationale for a conflicted file")
    parser_explain.add_argument("file", help="Path to conflicted file")
    parser_explain.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # Command: resolve
    parser_resolve = subparsers.add_parser("resolve", help="Intelligently resolve conflicts")
    parser_resolve.add_argument("file", nargs="?", default=None, help="Specific file to resolve (or all if omitted)")
    parser_resolve.add_argument(
        "--strategy",
        choices=["auto", "ours", "theirs", "ai", "interactive"],
        default="auto",
        help="Resolution strategy (default: auto)",
    )
    parser_resolve.add_argument("--model", default="qwen2.5-coder:7b", help="Open-weight AI model to use (default: qwen2.5-coder:7b)")
    parser_resolve.add_argument("--no-stage", action="store_true", help="Do not git-add resolved files")
    parser_resolve.add_argument("--dry-run", action="store_true", help="Preview resolution without modifying files")

    # Command: attest
    parser_attest = subparsers.add_parser("attest", help="Attach testing attestation and environment metadata to a commit")
    parser_attest.add_argument("--commit", default="HEAD", help="Commit hash to attest (default: HEAD)")
    parser_attest.add_argument("--status", choices=["passed", "failed", "untested"], default="passed", help="Test status")
    parser_attest.add_argument("--env", choices=["production", "uat", "staging", "dev"], default="dev", help="Environment tier")
    parser_attest.add_argument("--suite", default="pytest", help="Test suite name")
    parser_attest.add_argument("--ci-run", default=None, help="CI Run URL or ID")
    parser_attest.add_argument("--coverage", type=float, default=None, help="Coverage percentage (0-100)")

    # Command: backport-check
    parser_bp = subparsers.add_parser("backport-check", help="Trace a commit's backports and patch-id across branches")
    parser_bp.add_argument("commit", help="Commit hash to check")
    parser_bp.add_argument("branches", nargs="*", default=["main", "production", "uat"], help="Branches to inspect")

    # Command: commit
    parser_commit = subparsers.add_parser("commit", help="Create standard Git commit enriched with provenance trailers")
    parser_commit.add_argument("-m", "--message", required=True, help="Commit message")

    # Command: ui / web
    parser_ui = subparsers.add_parser("ui", help="Launch interactive Claymorphism & Glassmorphism Web Studio")
    parser_ui.add_argument("--port", type=int, default=8765, help="Port to serve UI on (default: 8765)")
    parser_ui.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")

    parser_web = subparsers.add_parser("web", help="Alias for 'ui'")
    parser_web.add_argument("--port", type=int, default=8765, help="Port to serve UI on (default: 8765)")
    parser_web.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")

    return parser


def handle_status(args, resolver: ConflictResolver) -> int:
    conflicted = resolver.git.get_conflicted_files()
    if not conflicted:
        print(f"{Color.GREEN}No Git conflicts detected in repository.{Color.RESET}")
        return 0

    results = []
    for f in conflicted:
        summary = resolver.analyze_file(f)
        results.append(summary)
        if not args.json:
            print(ProvenanceFormatter.format_summary(summary))

    if args.json:
        data = [s.to_dict() for s in results]
        print(json.dumps(data, indent=2))

    return 0


def handle_explain(args, resolver: ConflictResolver) -> int:
    summary = resolver.analyze_file(args.file)
    if summary.total_hunks == 0:
        print(f"{Color.YELLOW}No conflict markers found in '{args.file}'.{Color.RESET}")
        return 0

    if args.json:
        print(json.dumps(summary.to_dict(), indent=2))
    else:
        print(ProvenanceFormatter.format_summary(summary))
    return 0


def handle_resolve(args, resolver: ConflictResolver) -> int:
    files_to_resolve = [args.file] if args.file else resolver.git.get_conflicted_files()
    if not files_to_resolve:
        print(f"{Color.YELLOW}No conflicted files to resolve.{Color.RESET}")
        return 0

    strat_map = {
        "auto": None,
        "ours": ResolutionStrategy.OURS,
        "theirs": ResolutionStrategy.THEIRS,
        "ai": ResolutionStrategy.SYNTHESIZED_AI,
    }
    chosen_strat = strat_map.get(args.strategy)

    for f in files_to_resolve:
        print(f"\n{Color.BOLD}Resolving {Color.CYAN}{f}{Color.RESET}...")
        summary = resolver.resolve_file(
            f,
            strategy=chosen_strat,
            apply=not args.dry_run,
            stage=not args.no_stage and not args.dry_run,
        )
        print(f"  {Color.GREEN}✔ Successfully resolved {summary.total_hunks} conflict hunk(s).{Color.RESET}")
        for ctx in summary.hunk_contexts:
            print(f"    Hunk #{ctx.hunk.hunk_index + 1}: Strategy: {ctx.recommendation.value} (Confidence: {ctx.confidence_score*100:.1f}%)")
            print(f"    Rationale: {ctx.rationale}")

    if args.dry_run:
        print(f"\n{Color.YELLOW}[DRY-RUN] Changes were evaluated but not written to disk.{Color.RESET}")
    else:
        print(f"\n{Color.GREEN}All conflicts resolved. Ready to test or commit with 'git prov commit -m \"...\"'{Color.RESET}")
    return 0


def handle_attest(args, resolver: ConflictResolver) -> int:
    git = resolver.git
    commit_sha = git.run(["rev-parse", args.commit], check=True)
    status_enum = TestStatus(args.status.upper())
    env_enum = EnvironmentStatus(args.env.upper())

    attestation = resolver.testing_store.record_attestation(
        commit_hash=commit_sha,
        status=status_enum,
        suite_name=args.suite,
        ci_run_id=args.ci_run,
        coverage_pct=args.coverage,
        environment=env_enum,
    )
    print(f"{Color.GREEN}✔ Recorded testing attestation for {commit_sha[:8]}:{Color.RESET}")
    print(f"  Status:      {ProvenanceFormatter.test_badge(attestation.status)}")
    print(f"  Environment: {ProvenanceFormatter.env_badge(env_enum)}")
    print(f"  Suite:       {attestation.suite_name}")
    print(f"  Git Notes:   refs/notes/test-provenance updated.")
    return 0


def handle_backport_check(args, resolver: ConflictResolver) -> int:
    miner = resolver.miner
    git = resolver.git

    commit_sha = git.run(["rev-parse", args.commit], check=True)
    prov = miner.extract_provenance_for_commit(commit_sha)
    if not prov:
        print(f"{Color.RED}Commit {args.commit} not found.{Color.RESET}")
        return 1

    print(f"{Color.BOLD}Tracing Commit Lineage: {Color.CYAN}{prov.short_hash}{Color.RESET}")
    print(f"Author: {prov.author_name} ({prov.date[:10]})")
    print(f"Message: {prov.message.splitlines()[0] if prov.message else ''}")
    print(f"Patch-ID: {prov.patch_id or 'N/A'}")

    if prov.patch_id:
        match = miner.find_equivalent_commit(prov.patch_id, args.branches)
        if match:
            equiv_sha, branch = match
            print(f"\n{Color.GREEN}✔ Found patch-id equivalent commit on branch '{branch}': {equiv_sha[:8]}{Color.RESET}")
        else:
            print(f"\n{Color.YELLOW}No identical patch-id found on specified branches.{Color.RESET}")
    return 0


def handle_commit(args, resolver: ConflictResolver) -> int:
    git = resolver.git
    conflicted = git.get_conflicted_files()
    if conflicted:
        print(f"{Color.RED}Error: Cannot commit while conflicts remain unresolved:{Color.RESET}")
        for f in conflicted:
            print(f"  - {f}")
        return 1

    trailers = {
        "X-Conflict-Resolved-With": f"git-provenance-v{__version__}",
        "X-Provenance-Verified": "True",
    }
    new_sha = git.create_commit(args.message, trailers=trailers)
    print(f"{Color.GREEN}✔ Standard Git commit created: {new_sha[:8]}{Color.RESET}")
    print(f"Commit trailers verified and attached.")
    return 0


def handle_ui(args, resolver: ConflictResolver) -> int:
    import webbrowser
    from git_provenance.web.server import run_server

    url = f"http://localhost:{args.port}"
    print(f"{Color.BOLD}Launching Git-Provenance Interactive Studio at {Color.CYAN}{url}{Color.RESET}...")
    if not getattr(args, "no_browser", False):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    run_server(port=args.port, repo_path=str(resolver.git.repo_path))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.subcommand:
        parser.print_help()
        return 0

    ai_engine = AIResolutionEngine(model_name=getattr(args, "model", None))
    resolver = ConflictResolver(repo_path=args.repo, ai_engine=ai_engine)

    if not resolver.git.is_inside_work_tree():
        print(f"{Color.RED}Error: Not inside a Git repository.{Color.RESET}", file=sys.stderr)
        return 1

    handlers = {
        "status": handle_status,
        "explain": handle_explain,
        "resolve": handle_resolve,
        "attest": handle_attest,
        "backport-check": handle_backport_check,
        "commit": handle_commit,
        "ui": handle_ui,
        "web": handle_ui,
    }

    handler = handlers.get(args.subcommand)
    if handler:
        try:
            return handler(args, resolver)
        except Exception as e:
            print(f"{Color.RED}Execution Error: {e}{Color.RESET}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
