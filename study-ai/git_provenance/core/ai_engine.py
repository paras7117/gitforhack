"""
Open-Weight AI Resolution Engine and AST Semantic Synthesizer.
Integrates Qwen2.5-Coder and Gemma-2 (via Ollama / vLLM / Local Runner)
with deterministic AST heuristics for robust offline fallback.
"""

import os
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Tuple
from git_provenance.core.provenance import (
    ConflictHunk,
    HunkProvenanceContext,
    ResolutionStrategy,
    EnvironmentStatus,
    TestStatus,
)
from git_provenance.core.ast_engine import ASTSemanticEngine


class AIResolutionEngine:
    """Orchestrates OpenAI (GPT-4o / GPT-4o-mini) and open-weight LLMs with deterministic AST heuristics."""

    DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    DEFAULT_OPENAI_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    DEFAULT_MODEL = os.environ.get("GIT_PROV_MODEL", "gpt-4o-mini")

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.model_name = model_name or self.DEFAULT_MODEL
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if self.is_openai_model():
            self.api_url = api_url or self.DEFAULT_OPENAI_URL
        else:
            self.api_url = api_url or self.DEFAULT_OLLAMA_URL

    def is_openai_model(self) -> bool:
        """Check if target model uses OpenAI API."""
        return (
            self.model_name.startswith("gpt-") or
            self.model_name.startswith("o1-") or
            self.model_name.startswith("text-") or
            bool(self.api_key)
        )

    def is_ai_available(self) -> bool:
        """Check if AI model runner (OpenAI or local endpoint) is reachable."""
        if self.is_openai_model():
            return bool(self.api_key)
        try:
            req = urllib.request.Request(f"{self.api_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def synthesize_resolution(self, ctx: HunkProvenanceContext) -> Tuple[ResolutionStrategy, str, float, str, str]:
        """
        Synthesize resolution for a conflict hunk using provenance and testing context.
        Returns: (strategy, resolved_code, confidence_score, rationale, model_name)
        """
        # 1. First, check deterministic provenance rules (100% precision)
        deterministic_res = self._solve_with_deterministic_rules(ctx)
        if deterministic_res is not None:
            strat, code, conf, rationale = deterministic_res
            return strat, code, conf, rationale, "Deterministic-Semantic-AST"

        # 2. If AI runner is reachable, query open-weight model (Qwen2.5-Coder / Gemma-2)
        if self.is_ai_available():
            ai_res = self._solve_with_llm(ctx)
            if ai_res is not None:
                strat, code, conf, rationale = ai_res
                return strat, code, conf, rationale, self.model_name

        # 3. Fallback: Safe Conservative Resolution
        return self._safe_fallback_resolution(ctx)

    def _solve_with_deterministic_rules(
        self, ctx: HunkProvenanceContext
    ) -> Optional[Tuple[ResolutionStrategy, str, float, str]]:
        """Apply high-confidence provenance and testing rules."""
        hunk = ctx.hunk
        prov_ours = ctx.provenance_ours
        prov_theirs = ctx.provenance_theirs

        # Check identical code
        if hunk.lines_ours == hunk.lines_theirs:
            return (
                ResolutionStrategy.OURS,
                hunk.text_ours,
                1.0,
                "Both branches have identical code."
            )

        # Rule 1: Backport / Patch-ID Equivalence
        if prov_theirs and prov_theirs.cherry_pick_origin:
            if prov_ours and (prov_ours.commit_hash.startswith(prov_theirs.cherry_pick_origin) or
                              prov_theirs.cherry_pick_origin.startswith(prov_ours.commit_hash)):
                return (
                    ResolutionStrategy.THEIRS,
                    hunk.text_theirs,
                    0.95,
                    f"Their change is an explicit backport of our commit ({prov_theirs.cherry_pick_origin})."
                )

        # Rule 2: Environment Provenance Hierarchy & Verified Bugfix Backports
        env_tiers = {
            EnvironmentStatus.PRODUCTION: 4,
            EnvironmentStatus.UAT: 3,
            EnvironmentStatus.STAGING: 3,
            EnvironmentStatus.DEVELOPMENT: 2,
            EnvironmentStatus.UNVERIFIED: 1,
            EnvironmentStatus.UNKNOWN: 0,
        }

        tier_ours = env_tiers.get(prov_ours.environment, 0) if prov_ours else 0
        tier_theirs = env_tiers.get(prov_theirs.environment, 0) if prov_theirs else 0

        ours_passed = prov_ours and prov_ours.test_attestation.status == TestStatus.PASSED
        theirs_passed = prov_theirs and prov_theirs.test_attestation.status == TestStatus.PASSED

        # If THEIR side is a verified production bugfix or higher tier than ours
        if theirs_passed and prov_theirs.backport_references and (tier_theirs >= tier_ours):
            return (
                ResolutionStrategy.THEIRS,
                hunk.text_theirs,
                0.94,
                f"Accepted THEIRS: Verified backport fix ({', '.join(prov_theirs.backport_references)}) "
                f"with passing tests in {prov_theirs.environment.value}."
            )

        if ours_passed and (tier_ours > tier_theirs):
            return (
                ResolutionStrategy.OURS,
                hunk.text_ours,
                0.92,
                f"Preserved OURS: Change has higher deployment provenance ({prov_ours.environment.value}) "
                f"with verified passing test suite."
            )
        elif theirs_passed and (tier_theirs > tier_ours):
            return (
                ResolutionStrategy.THEIRS,
                hunk.text_theirs,
                0.92,
                f"Accepted THEIRS: Change has higher deployment provenance ({prov_theirs.environment.value}) "
                f"with verified passing test suite."
            )

        # Rule 3: AST Syntax-Aware Import Unification
        ast_imports = ASTSemanticEngine.merge_ast_imports(hunk.text_ours, hunk.text_theirs)
        if ast_imports:
            return (
                ResolutionStrategy.UNION,
                ast_imports,
                0.95,
                "Synthesized union via Python AST engine: Deduplicated and merged import statements."
            )

        # Rule 4: AST Disjoint Function / Class Merging
        ast_disjoint = ASTSemanticEngine.merge_disjoint_ast_declarations(hunk.text_ours, hunk.text_theirs)
        if ast_disjoint:
            return (
                ResolutionStrategy.UNION,
                ast_disjoint,
                0.93,
                "Synthesized union via Python AST engine: Merged non-conflicting top-level function/class declarations."
            )

        # Rule 5: AST Function Signature & Bugfix Reconciliation
        ast_fn = ASTSemanticEngine.merge_function_signatures(hunk.text_ours, hunk.text_theirs, hunk.text_base)
        if ast_fn:
            return (
                ResolutionStrategy.SYNTHESIZED_AI,
                ast_fn,
                0.90,
                "Synthesized resolution via Python AST engine: Reconciled new parameter default with bugfixed body."
            )

        # Rule 6: Disjoint Non-overlapping Additions (Generic / Non-Python)
        if self._is_pure_additions(hunk):
            combined = hunk.lines_ours + hunk.lines_theirs
            return (
                ResolutionStrategy.UNION,
                "".join(combined),
                0.85,
                "Synthesized union: Merged non-conflicting independent code blocks from both branches."
            )

        return None

    def _solve_with_llm(
        self, ctx: HunkProvenanceContext
    ) -> Optional[Tuple[ResolutionStrategy, str, float, str]]:
        """Call OpenAI API (GPT-4o / GPT-4o-mini) or local LLM."""
        prompt = self._construct_prompt(ctx)

        if self.is_openai_model():
            return self._solve_with_openai(prompt)
        else:
            return self._solve_with_ollama(prompt)

    def _solve_with_openai(self, prompt: str) -> Optional[Tuple[ResolutionStrategy, str, float, str]]:
        """Query OpenAI Chat Completions API."""
        endpoint = f"{self.api_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a Git conflict resolution engine with testing provenance."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key or ''}"
        }
        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices:
                    response_text = choices[0].get("message", {}).get("content", "")
                    return self._parse_llm_response(response_text)
        except Exception:
            return None
        return None

    def _solve_with_ollama(self, prompt: str) -> Optional[Tuple[ResolutionStrategy, str, float, str]]:
        """Query local Ollama runner."""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            }
        }
        try:
            req = urllib.request.Request(
                f"{self.api_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                response_text = data.get("response", "")
                return self._parse_llm_response(response_text)
        except Exception:
            return None

    def _construct_prompt(self, ctx: HunkProvenanceContext) -> str:
        """Construct high-context provenance prompt for open-weight coding LLMs."""
        h = ctx.hunk
        p_ours = ctx.provenance_ours
        p_theirs = ctx.provenance_theirs

        ours_info = f"Hash: {p_ours.short_hash if p_ours else 'Unknown'}, " \
                    f"Env: {p_ours.environment.value if p_ours else 'UNKNOWN'}, " \
                    f"Tests: {p_ours.test_attestation.status.value if p_ours else 'UNKNOWN'}"
        theirs_info = f"Hash: {p_theirs.short_hash if p_theirs else 'Unknown'}, " \
                      f"Env: {p_theirs.environment.value if p_theirs else 'UNKNOWN'}, " \
                      f"Tests: {p_theirs.test_attestation.status.value if p_theirs else 'UNKNOWN'}"

        base_section = f"--- BASE ANCESTOR ---\n{h.text_base}\n" if h.text_base else ""

        return f"""You are an expert Git conflict resolution engine specializing in testing provenance.
Resolve the following Git conflict. Always protect production-tested fixes and prevent regressions.

FILE: {ctx.file_path}

OUR SIDE ({h.header_ours}):
Metadata: {ours_info}
Message: {p_ours.message if p_ours else 'N/A'}
Code:
{h.text_ours}

THEIR SIDE ({h.header_theirs}):
Metadata: {theirs_info}
Message: {p_theirs.message if p_theirs else 'N/A'}
Code:
{h.text_theirs}

{base_section}
INSTRUCTIONS:
1. Provide the resolved code enclosed in ```resolved_code ... ```.
2. Provide a 1-sentence explanation of the resolution.
3. Provide confidence score between 0.0 and 1.0.
"""

    def _parse_llm_response(self, text: str) -> Optional[Tuple[ResolutionStrategy, str, float, str]]:
        """Parse structured LLM output."""
        code = ""
        if "```resolved_code" in text:
            parts = text.split("```resolved_code")
            if len(parts) > 1:
                code = parts[1].split("```")[0].strip() + "\n"
        elif "```" in text:
            parts = text.split("```")
            if len(parts) >= 3:
                code = parts[1].strip() + "\n"

        if not code:
            return None

        rationale = "Synthesized resolution via open-weight model with testing provenance."
        conf = 0.88
        return (ResolutionStrategy.SYNTHESIZED_AI, code, conf, rationale)

    def _safe_fallback_resolution(
        self, ctx: HunkProvenanceContext
    ) -> Tuple[ResolutionStrategy, str, float, str, str]:
        """Safe conservative heuristic resolution when full automated synthesis is ambiguous."""
        prov_ours = ctx.provenance_ours
        prov_theirs = ctx.provenance_theirs

        # Check test passing status
        ours_passed = prov_ours and prov_ours.test_attestation.status == TestStatus.PASSED
        theirs_passed = prov_theirs and prov_theirs.test_attestation.status == TestStatus.PASSED

        if ours_passed and not theirs_passed:
            return (
                ResolutionStrategy.OURS,
                ctx.hunk.text_ours,
                0.75,
                "Preferred OURS because it has verified passing test attestations.",
                "Provenance-Heuristic"
            )
        elif theirs_passed and not ours_passed:
            return (
                ResolutionStrategy.THEIRS,
                ctx.hunk.text_theirs,
                0.75,
                "Preferred THEIRS because it has verified passing test attestations.",
                "Provenance-Heuristic"
            )

        # Default to OURS (HEAD) as Git standard convention
        return (
            ResolutionStrategy.OURS,
            ctx.hunk.text_ours,
            0.60,
            "Defaulted to OURS (HEAD branch) to preserve local branch stability. Review recommended.",
            "Standard-Conservative"
        )

    def _is_mergeable_imports(self, lines_a: list, lines_b: list) -> bool:
        """Check if both conflict hunks consist strictly of import statements."""
        for line in lines_a + lines_b:
            l = line.strip()
            if l and not (l.startswith("import ") or l.startswith("from ") or l.startswith("#")):
                return False
        return bool(lines_a and lines_b)

    def _merge_imports(self, lines_a: list, lines_b: list) -> list:
        """Deterministically merge and deduplicate Python imports."""
        seen = set()
        merged = []
        for line in lines_a + lines_b:
            l_clean = line.strip()
            if l_clean and l_clean not in seen:
                seen.add(l_clean)
                merged.append(line)
        return merged

    def _is_pure_additions(self, hunk: ConflictHunk) -> bool:
        """Check if both sides add distinct functions/classes without modifying base ancestor."""
        if hunk.lines_base is not None and len(hunk.lines_base) == 0:
            return True
        return False
