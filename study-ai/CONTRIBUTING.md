# Contributing to git-provenance

Thank you for your interest in contributing to **`git-provenance`**! We welcome contributions from developers, open-source maintainers, and security researchers.

---

## 1. Code of Conduct
This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## 2. Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/hacktoberfest2026/git-provenance.git
   cd git-provenance
   ```

2. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. Run the test suite:
   ```bash
   pytest tests/ -v
   ```

4. Execute evaluation scenarios:
   ```bash
   python examples/django_backport_scenario/run_scenario.py
   python examples/cpython_backport_scenario/run_scenario.py
   python examples/multi_branch_enterprise/run_scenario.py
   ```

---

## 3. Pull Request Guidelines

Every pull request must:
- Include unit tests for any new features or bug fixes under `tests/`.
- Maintain standard Git compatibility (do not introduce custom binary formats or history rewriting).
- Follow the pull request template at `.github/pull_request_template.md`.
- Explicitly declare any open-weight AI models integrated or used.
