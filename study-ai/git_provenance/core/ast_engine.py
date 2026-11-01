"""
Python AST Semantic Resolver Engine.
Performs syntax-aware AST parsing, function signature reconciliation,
and AST import unification for open-source Python codebases.
"""

import ast
import logging
from typing import Optional, Tuple, List, Set, Dict

logger = logging.getLogger("git_provenance.ast_engine")


class ASTSemanticEngine:
    """Performs deep Abstract Syntax Tree analysis and semantic merging on Python code."""

    @classmethod
    def can_parse(cls, code: str) -> bool:
        """Check if code snippet is syntactically valid Python."""
        try:
            ast.parse(code)
            return True
        except (SyntaxError, ValueError):
            return False

    @classmethod
    def merge_ast_imports(cls, code_ours: str, code_theirs: str) -> Optional[str]:
        """
        Merge Python import statements using AST analysis.
        Deduplicates names and combines imports from identical modules.
        """
        try:
            tree_ours = ast.parse(code_ours)
            tree_theirs = ast.parse(code_theirs)
        except Exception:
            return None

        # Verify all top-level statements are imports
        all_stmts = tree_ours.body + tree_theirs.body
        for stmt in all_stmts:
            if not isinstance(stmt, (ast.Import, ast.ImportFrom, ast.Expr)):
                return None

        regular_imports: Set[str] = set()
        from_imports: Dict[str, Set[str]] = {}

        for stmt in all_stmts:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    name_str = alias.name
                    if alias.asname:
                        name_str += f" as {alias.asname}"
                    regular_imports.add(name_str)
            elif isinstance(stmt, ast.ImportFrom):
                mod = stmt.module or ""
                if mod not in from_imports:
                    from_imports[mod] = set()
                for alias in stmt.names:
                    name_str = alias.name
                    if alias.asname:
                        name_str += f" as {alias.asname}"
                    from_imports[mod].add(name_str)

        lines: List[str] = []
        for reg in sorted(regular_imports):
            lines.append(f"import {reg}")

        for mod in sorted(from_imports.keys()):
            names = sorted(from_imports[mod])
            lines.append(f"from {mod} import {', '.join(names)}")

        return "\n".join(lines) + "\n"

    @classmethod
    def merge_disjoint_ast_declarations(cls, code_ours: str, code_theirs: str) -> Optional[str]:
        """
        If both branches declare non-overlapping functions, classes, or constants,
        merge them together into a unified AST.
        """
        try:
            tree_ours = ast.parse(code_ours)
            tree_theirs = ast.parse(code_theirs)
        except Exception:
            return None

        names_ours = {stmt.name for stmt in tree_ours.body if hasattr(stmt, "name")}
        names_theirs = {stmt.name for stmt in tree_theirs.body if hasattr(stmt, "name")}

        # If there are no overlapping top-level defined names
        if names_ours and names_theirs and not (names_ours & names_theirs):
            merged_body = tree_ours.body + tree_theirs.body
            module = ast.Module(body=merged_body, type_ignores=[])
            ast.fix_missing_locations(module)
            return ast.unparse(module) + "\n"

        return None

    @classmethod
    def merge_function_signatures(
        cls, fn_ours_code: str, fn_theirs_code: str, base_code: Optional[str] = None
    ) -> Optional[str]:
        """
        If one branch added a new parameter with a default value (non-breaking API extension),
        and the other branch patched the function body (e.g. bugfix/security fix),
        reconcile the parameter into the bugfixed function.
        """
        try:
            tree_ours = ast.parse(fn_ours_code)
            tree_theirs = ast.parse(fn_theirs_code)
        except Exception:
            return None

        if len(tree_ours.body) != 1 or len(tree_theirs.body) != 1:
            return None

        fn_ours = tree_ours.body[0]
        fn_theirs = tree_theirs.body[0]

        if not isinstance(fn_ours, ast.FunctionDef) or not isinstance(fn_theirs, ast.FunctionDef):
            return None

        if fn_ours.name != fn_theirs.name:
            return None

        args_ours = [a.arg for a in fn_ours.args.args]
        args_theirs = [a.arg for a in fn_theirs.args.args]

        # Case: Theirs added a new argument with a default
        if len(args_theirs) > len(args_ours) and set(args_ours).issubset(set(args_theirs)):
            # Use their signature with our body (or vice versa)
            merged_fn = ast.FunctionDef(
                name=fn_ours.name,
                args=fn_theirs.args,
                body=fn_ours.body,
                decorator_list=fn_ours.decorator_list or fn_theirs.decorator_list,
                returns=fn_ours.returns or fn_theirs.returns,
            )
            module = ast.Module(body=[merged_fn], type_ignores=[])
            ast.fix_missing_locations(module)
            return ast.unparse(module) + "\n"

        # Case: Ours added a new argument with a default
        if len(args_ours) > len(args_theirs) and set(args_theirs).issubset(set(args_ours)):
            merged_fn = ast.FunctionDef(
                name=fn_ours.name,
                args=fn_ours.args,
                body=fn_theirs.body,
                decorator_list=fn_ours.decorator_list or fn_theirs.decorator_list,
                returns=fn_ours.returns or fn_theirs.returns,
            )
            module = ast.Module(body=[merged_fn], type_ignores=[])
            ast.fix_missing_locations(module)
            return ast.unparse(module) + "\n"

        return None
