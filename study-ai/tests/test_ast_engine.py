"""
Tests for Python AST Semantic Resolver Engine.
"""

from git_provenance.core.ast_engine import ASTSemanticEngine


def test_merge_ast_imports():
    ours = """
import sys
from os import path
"""
    theirs = """
import json
from os import getcwd
"""
    merged = ASTSemanticEngine.merge_ast_imports(ours, theirs)
    assert merged is not None
    assert "import json" in merged
    assert "import sys" in merged
    assert "from os import getcwd, path" in merged


def test_merge_disjoint_functions():
    ours = """
def fetch_user_data(user_id):
    return {"id": user_id, "active": True}
"""
    theirs = """
def log_audit_event(event_type, details):
    logger.info("AuditEvent: %s - %s", event_type, details)
"""
    merged = ASTSemanticEngine.merge_disjoint_ast_declarations(ours, theirs)
    assert merged is not None
    assert "def fetch_user_data(user_id):" in merged
    assert "def log_audit_event(event_type, details):" in merged


def test_merge_function_signatures():
    # Ours has bugfix in body with original signature
    ours = """
def process_order(order_id, user_id):
    # Bugfix: validate user before processing
    if not user_id:
        raise ValueError("Invalid user")
    return db.process(order_id)
"""
    # Theirs extended signature with optional retry_limit
    theirs = """
def process_order(order_id, user_id, retry_limit=3):
    return db.process(order_id)
"""
    merged = ASTSemanticEngine.merge_function_signatures(ours, theirs)
    assert merged is not None
    # Signature should have retry_limit=3 and body should have the bugfix!
    assert "retry_limit=3" in merged
    assert "raise ValueError" in merged
    assert "Invalid user" in merged
