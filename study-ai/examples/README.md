# Evaluation Scenarios & Examples

This directory contains representative evaluation scenarios demonstrating the **`git-provenance`** conflict resolution engine in action, as required by Section 4.5 and Evaluation Scenarios.

---

## 1. Django Backport Conflict Scenario (`django_backport_scenario/`)
- **Context:** Simulates backporting an upstream ORM bugfix (PR `#34567`) from Django's `main` branch to the `stable/4.2.x` branch.
- **Challenge:** Both branches introduced conflicting modifications to `myapp/views.py`.
- **Provenance Resolution:**
  - `git-provenance` detects the Django-style commit message `[4.2.x] Fixed #34567 -- Corrected outer join order in ORM query compiler. Backport of 6e1a49f from main.`
  - Extracts the testing attestation from the production-tested upstream branch (`django-tests-full`, 98.4% coverage).
  - Recognizes that the incoming side is an attested bugfix and automatically recommends accepting **THEIRS** with **94.0% confidence**, preventing an accidental regression on the stable branch.
- **Artifacts:**
  - Input: [`input/conflicted_views.py`](./django_backport_scenario/input/conflicted_views.py), [`input/repo_context.json`](./django_backport_scenario/input/repo_context.json)
  - Output: [`output/provenance_report.json`](./django_backport_scenario/output/provenance_report.json), [`output/provenance_report.txt`](./django_backport_scenario/output/provenance_report.txt), [`output/resolved_views.py`](./django_backport_scenario/output/resolved_views.py), [`output/git_commit_log.txt`](./django_backport_scenario/output/git_commit_log.txt)
- **Run Locally:**
  ```bash
  python examples/django_backport_scenario/run_scenario.py
  ```

---

## 2. CPython Backport Conflict Scenario (`cpython_backport_scenario/`)
- **Context:** Simulates cherry-picking an asyncio race-condition fix from Python 3.13 (`main`) to branch `3.12`.
- **Challenge:** Conflicting proactor loop initialization flags in `Lib/asyncio/proactor_events.py`.
- **Provenance Resolution:**
  - Extracts CPython cherry-pick bot metadata: `[3.12] gh-108278: Disallow nested asyncio event loops on Windows (GH-108300)` and `(cherry picked from commit 7a82b9e6fa436...)`.
  - Computes `git patch-id` and verifies that the incoming change is backed by verified tests in `test_asyncio` (99.1% coverage) in production.
  - Resolves conflict with **94.0% confidence** prioritizing the verified backport.
- **Artifacts:**
  - Input: [`input/conflicted_asyncio.py`](./cpython_backport_scenario/input/conflicted_asyncio.py), [`input/repo_context.json`](./cpython_backport_scenario/input/repo_context.json)
  - Output: [`output/provenance_report.json`](./cpython_backport_scenario/output/provenance_report.json), [`output/provenance_report.txt`](./cpython_backport_scenario/output/provenance_report.txt), [`output/resolved_asyncio.py`](./cpython_backport_scenario/output/resolved_asyncio.py), [`output/git_commit_log.txt`](./cpython_backport_scenario/output/git_commit_log.txt)
- **Run Locally:**
  ```bash
  python examples/cpython_backport_scenario/run_scenario.py
  ```

---

## 3. Multi-Branch Enterprise Scenario (`multi_branch_enterprise/`)
- **Context:** A fintech organization maintains `production`, `uat`, and `development` branches.
- **Challenge:** A high-severity security hotfix running in `production` (idempotent payment retries with 100% PCI test coverage) is merged into `uat`, where an intern's experimental feature branch (`feature/async-webhooks`) touched the same payment function without passing tests.
- **Provenance Resolution:**
  - Compares deployment tiers: `HEAD` has `PRODUCTION` deployment status with `PASSED` status in `pci-compliance-e2e`. The incoming branch is `UNVERIFIED` and `UNTESTED`.
  - High-confidence protection rule activates: preserves the production hotfix (**OURS**, **92.0% confidence**) and attaches standard Git trailers to the resulting commit.
- **Artifacts:**
  - Input: [`input/conflicted_payment_service.py`](./multi_branch_enterprise/input/conflicted_payment_service.py), [`input/repo_context.json`](./multi_branch_enterprise/input/repo_context.json)
  - Output: [`output/provenance_report.json`](./multi_branch_enterprise/output/provenance_report.json), [`output/provenance_report.txt`](./multi_branch_enterprise/output/provenance_report.txt), [`output/resolved_payment_service.py`](./multi_branch_enterprise/output/resolved_payment_service.py), [`output/git_commit_log.txt`](./multi_branch_enterprise/output/git_commit_log.txt)
- **Run Locally:**
  ```bash
  python examples/multi_branch_enterprise/run_scenario.py
  ```
