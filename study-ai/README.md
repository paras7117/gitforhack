# git-provenance (`git-prov`)

> **Intelligent Git Conflict Resolution Engine with Testing Provenance and Cross-Branch Lineage**  
> *Built for Hacktoberfest 2026 – Hack Day Sonipat | Problem 01: Version Control & Developer Productivity*

[![CI](https://github.com/hacktoberfest2026/git-provenance/actions/workflows/ci.yml/badge.svg)](https://github.com/hacktoberfest2026/git-provenance/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

---

## 1. Executive Summary & The Problem

Software engineering teams frequently maintain multiple long-lived branches (`main`, `development`, `uat`, `staging`, `production`, and `release/*`). When features and bug fixes are backported or promoted across these branches, merge and rebase conflicts frequently arise.

Traditional Git conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) present developers with isolated lines of code in a vacuum, providing **zero context** about:
1. **Origin & Ancestry:** Who authored each block, which upstream PR/issue introduced it, and whether it was cherry-picked.
2. **Testing History:** Did this block pass CI unit tests, integration tests, or security regression suites?
3. **Environment Status:** Is this code running in production right now, or is it an unverified experimental tweak on a feature branch?

As a result, developers are forced into high-risk manual guesswork, accidentally overwriting production-tested security fixes with unverified changes or introducing subtle regressions.

**`git-provenance`** transforms conflict resolution from blind text splicing into an **evidence-based decision process**. It inspects Git commit ancestry, `git patch-id`, Git Notes, and CI attestations to present full contextual provenance and synthesize verified resolutions using open-weight AI models (`Qwen2.5-Coder`, `Gemma-2`) and AST heuristics—all while producing **standard, 100% backward-compatible Git commits**.

---

## 2. Key Architecture & Technical Innovations

```
                       ┌──────────────────────────────────────────────┐
                       │          Git Repository In Conflict          │
                       │ (MERGE_HEAD / REBASE_HEAD / CHERRY_PICK_HEAD)│
                       └──────────────────────┬───────────────────────┘
                                              │
                    ┌─────────────────────────┴────────────────────────┐
                    ▼                                                  ▼
      ┌───────────────────────────┐                      ┌───────────────────────────┐
      │     OUR SIDE (HEAD)       │                      │   THEIR SIDE (Incoming)   │
      └─────────────┬─────────────┘                      └─────────────┬─────────────┘
                    │                                                  │
                    ├────────────► Origin Miner (git blame/log/cherry) ◄┤
                    ├────────────► Patch-ID Equivalence Scanner        ◄┤
                    ├────────────► Branch Topology / Env Detector      ◄┤
                    └────────────► Testing Store (refs/notes/trailers) ◄┘
                                              │
                                              ▼
                             ┌──────────────────────────────────┐
                             │    Hunk Provenance Context       │
                             │  • Environment: PROD vs UNVERIF  │
                             │  • Testing: PASSED vs UNTESTED   │
                             │  • Lineage: Backport #34567      │
                             └────────────────┬─────────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         ┌─────────────────────────┐                     ┌─────────────────────────┐
         │ Open-Weight AI Engine   │                     │ Deterministic AST Rules │
         │ (Qwen2.5-Coder / Gemma) │                     │ (Zero-dependency offline)│
         └────────────┬────────────┘                     └────────────┬────────────┘
                      │                                               │
                      └───────────────────────┬───────────────────────┘
                                              ▼
                                 ┌─────────────────────────┐
                                 │ Synthesized Resolution  │
                                 │   + Confidence Score    │
                                 │   + Human Rationale     │
                                 └────────────┬────────────┘
                                              │
                                              ▼
                                 ┌─────────────────────────┐
                                 │   Standard Git Commit   │
                                 │  (Trailers + Git Notes) │
                                 └─────────────────────────┘
```

---

## 3. Key Technical Considerations Addressed

### A. How can the system identify identical changes when their code has been modified during conflict resolution?
1. **`git patch-id --stable` Engine:** Computes a normalized cryptographic hash of diff hunks that ignores line numbers, leading whitespace, and formatting variations.
2. **Cherry-Pick Lineage Extraction:** Parses `(cherry picked from commit <hash>)` and commit references (`Backport of #...`, `Fixes #...`).
3. **`git cherry` Equivalence:** Evaluates patch equivalence across branch forks to determine if a logical change has already landed upstream or downstream.

### B. How should testing provenance be stored and transferred?
`git-provenance` uses a **dual-layer storage strategy**:
- **Layer 1: Native Git Notes (`refs/notes/test-provenance`):**
  - Completely non-invasive: does NOT modify commit hashes or rewrite Git history.
  - Standard Git push/fetch compatible:
    ```bash
    git push origin "refs/notes/*"
    git fetch origin "refs/notes/*:refs/notes/*"
    ```
- **Layer 2: Standard Git Commit Trailers:**
  - Embeds standard key-value trailers (`X-Test-Status: PASSED`, `X-CI-Run: 8921`, `X-Environment: production`, `X-Coverage: 98%`).
  - Automatically travels with cherry-picks and rebases across any standard Git client.
- **Layer 3: Portable Attestation Manifest (`.git-provenance.json`):**
  - Provides local caching and CI pipeline export capabilities.

### C. What happens when a repository is cloned without additional metadata?
- The tool gracefully falls back:
  1. Inspects permanent **Git Commit Trailers** in commit objects.
  2. Analyzes **Branch Topology** (`git branch -a --contains <sha>`) to determine if a commit is an ancestor of `production`, `main`, or `release/*`.
  3. Identifies backport lineage from standard commit message annotations.
  4. Automatically tags unverified code as `UNVERIFIED` and `UNTESTED`, giving developers actionable risk alerts before merging.

### D. How does the final output remain compatible with standard Git?
- Produces ordinary standard Git trees and commits.
- Uses standard Git trailers parsed by GitHub, GitLab, and `git interpret-trailers`.
- No proprietary daemon, custom merge driver requirement, or repository lock-in.

---

## 4. AI Model & Assistant Integration

`git-provenance` natively integrates OpenAI and local deterministic AST architectures:

| Model / System | Provider / Platform | Primary Responsibility |
|---|---|---|
| **`OpenAI GPT-4o-mini / GPT-4o`** | OpenAI API (`https://api.openai.com/v1`) | 3-way AST merge synthesis, preserving semantic intent and syntax validity. |
| **`Deterministic Semantic AST Engine`** | Built-in Pure Python | Offline-first, millisecond-latency resolution for imports, identical patches, and production dominance rules. |

### AI Coding Assistant Attribution
In compliance with Hackathon guidelines, the development of this codebase was assisted using:
- **OpenAI ChatGPT** & **GitHub Copilot** (powered by OpenAI).

The tool automatically supports `OPENAI_API_KEY` for live cloud synthesis. If offline or in isolated CI environments, it seamlessly utilizes the built-in deterministic AST engine with zero test flakiness.

---

## 5. Installation & Setup

### Prerequisites
- Python 3.9+
- Git 2.25+
- (Optional for AI synthesis) [Ollama](https://ollama.ai) with `qwen2.5-coder:7b` or `gemma2:9b`

### Install Locally
```bash
git clone https://github.com/hacktoberfest2026/git-provenance.git
cd git-provenance
pip install -e .
```

Once installed, `git-provenance` works seamlessly as a native Git subcommand:
```bash
git provenance --help
# Or shorthand:
git prov --help
```

---

## 6. CLI Command Reference & Workflow

### 1. Inspect Conflicts with Provenance (`git prov status`)
Displays all conflicted files with visual badges indicating environment tier (`[PROD]`, `[UAT]`, `[DEV]`, `[UNVERIFIED]`) and test status (`✔ PASSED`, `✘ FAILED`):
```bash
git prov status
```

### 2. Deep-Dive Contextual Explanation (`git prov explain <file>`)
Explains the origin commit, author, PR, test coverage, and why a specific resolution is recommended:
```bash
git prov explain myapp/views.py
```

### 3. Intelligently Resolve Conflicts (`git prov resolve`)
Resolves conflicts using provenance-first rules or AI synthesis, writes the clean file, and stages it:
```bash
# Auto-resolve with provenance hierarchy:
git prov resolve

# Or resolve a specific file using Qwen2.5-Coder:
git prov resolve myapp/views.py --strategy auto --model qwen2.5-coder:7b

# Dry-run preview:
git prov resolve --dry-run
```

### 4. Attest Testing Provenance (`git prov attest`)
Records test suite execution and environment status onto Git Notes and trailers:
```bash
git prov attest --commit HEAD --status passed --env production --suite pytest --coverage 98.5
```

### 5. Check Backport Equivalence (`git prov backport-check`)
Scans other branches for equivalent changes using `git patch-id` and `git cherry`:
```bash
git prov backport-check 6e1a49f main stable/4.2.x production
```

### 6. Create Standard Enriched Commit (`git prov commit`)
Finalizes the merge and generates a standard Git commit with verified provenance trailers:
```bash
git prov commit -m "Merge backport of PR #34567 into stable/4.2.x"
```

---

## 7. Evaluation Scenarios

See the [`examples/`](examples/) directory for full runnable scenarios, inputs, and generated artifacts:
1. **Django Backport Scenario:** Upstream ORM bugfix backported to `stable/4.2.x`. Demonstrates Trac ticket extraction and production test preservation.
2. **CPython Backport Scenario:** Asyncio Windows loop fix backported to Python `3.12`. Demonstrates cherry-pick bot extraction and patch-id matching.
3. **Multi-Branch Enterprise Scenario:** Production hotfix (100% PCI test coverage) vs unverified feature branch. Demonstrates production-tested dominance.

Run all scenarios with:
```bash
python examples/django_backport_scenario/run_scenario.py
python examples/cpython_backport_scenario/run_scenario.py
python examples/multi_branch_enterprise/run_scenario.py
```

---

## 8. Continuous Integration & Quality Assurance

Our test suite covers unit tests, AST parsers, Git Notes stores, and end-to-end multi-branch conflict resolution:
```bash
pytest tests/ -v
```

CI workflow is configured at [`.github/workflows/ci.yml`](.github/workflows/ci.yml) and runs on all pull requests and pushes across Python 3.10–3.13.

---

## 9. License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
