# Hacktoberfest 2026 – Hack Day Sonipat: Hackathon Submission

## 1. Team Information
- **Team Name:** GitVeritas
- **Team Members:**
  - Paras Choudhary (Lead Systems & Git Engineer)

---

## 2. Selected Problem Statement
**Problem 01:** Intelligent Git Conflict Resolution with Testing Provenance  
**Category:** Developer Productivity | Git Engineering | Version Control

### Challenge Summary:
Software development teams frequently maintain multiple long-lived branches (e.g., `development`, `uat`, `staging`, `production`, and `release/*`). When bug fixes and features are backported or promoted across branches, merge and rebase conflicts frequently arise. Traditional Git presents isolated conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) with zero context regarding the testing history, deployment status, or original intent of each conflicting side. This leads to accidental regressions, unverified code overwriting production-tested fixes, and tedious manual archeology.

Our solution, **`git-provenance` (`git-prov`)**, is an intelligent Git-integrated engine and CLI that identifies the true origin of conflicting changes, tracks test and CI provenance, distinguishes production-verified code from experimental branches, and synthesizes conflict resolutions while producing standard, backward-compatible Git commits.

---

## 3. AI Models Used & Selection Justification

### 1. `OpenAI GPT-4o-mini / GPT-4o` (OpenAI API / OpenAI-Compatible Architecture)
- **Role:** Code Synthesis & Semantic Conflict Resolution
- **Reason for Selection:** 
  - Industry-leading code reasoning, AST understanding, and syntax structure preservation.
  - Understands 3-way Git merge contexts (Base ancestor, Ours, Theirs) simultaneously without hallucinatory syntax breaks or missing imports.
  - Accessible via standard OpenAI API protocols and fast inference endpoints.

### 2. `Deterministic Python AST & Patch-ID Semantic Rule Engine` (Built-in Pure Python Engine)
- **Role:** Offline-First Deterministic Resolution & Provenance Mining
- **Reason for Selection:**
  - Guarantees 100% reproducible, millisecond-latency resolution for standard cases (e.g., independent additions, formatting variations, known backport cherry-picks identified via `git patch-id` and `git cherry`).
  - Operates fully offline with zero external dependencies, providing a robust fallback whenever remote API connections are unavailable.

---

## 4. AI Coding Assistants Used
- **Tool:** OpenAI ChatGPT & GitHub Copilot (Powered by OpenAI)
- **Role:** Assisted in drafting unit tests, structuring Git CLI wrappers, and optimizing AST unification algorithms.

---

## 5. Repository Submission
- **Deadline:** 8:30 PM, 31 October 2026
- **Repository Standard:** Clean initial commit containing only `HACKATHON.md`, followed by pull-request based workflow and automated CI.
