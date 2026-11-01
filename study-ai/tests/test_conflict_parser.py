"""
Tests for ConflictParser (2-way, 3-way/diff3, reassembly).
"""

from git_provenance.core.conflict_parser import ConflictParser


def test_has_conflicts():
    clean = "def foo():\n    return 42\n"
    conflicted = "<<<<<<< HEAD\nfoo\n=======\nbar\n>>>>>>> branch\n"
    assert not ConflictParser.has_conflicts(clean)
    assert ConflictParser.has_conflicts(conflicted)


def test_parse_two_way_conflict():
    content = """def calculate():
<<<<<<< HEAD
    return 10 * 2
=======
    return 10 * 3
>>>>>>> feature-x
    print('done')
"""
    hunks = ConflictParser.parse_content(content)
    assert len(hunks) == 1
    h = hunks[0]
    assert h.hunk_index == 0
    assert h.header_ours == "HEAD"
    assert h.header_theirs == "feature-x"
    assert h.lines_ours == ["    return 10 * 2\n"]
    assert h.lines_theirs == ["    return 10 * 3\n"]
    assert h.lines_base is None


def test_parse_three_way_diff3_conflict():
    content = """def process():
<<<<<<< HEAD
    mode = "production_secure"
||||||| merged common ancestors
    mode = "dev_default"
=======
    mode = "uat_preview"
>>>>>>> release/2.0
"""
    hunks = ConflictParser.parse_content(content)
    assert len(hunks) == 1
    h = hunks[0]
    assert h.lines_ours == ["    mode = \"production_secure\"\n"]
    assert h.lines_base == ["    mode = \"dev_default\"\n"]
    assert h.lines_theirs == ["    mode = \"uat_preview\"\n"]


def test_apply_resolutions():
    content = """start
<<<<<<< HEAD
line A
=======
line B
>>>>>>> branch
middle
<<<<<<< HEAD
code 1
=======
code 2
>>>>>>> branch
end
"""
    resolutions = [
        (0, "line RESOLVED A+B\n"),
        (1, "code RESOLVED 1+2\n"),
    ]
    resolved = ConflictParser.apply_resolutions(content, resolutions)
    assert "start" in resolved
    assert "line RESOLVED A+B" in resolved
    assert "middle" in resolved
    assert "code RESOLVED 1+2" in resolved
    assert "end" in resolved
    assert "<<<<<<<" not in resolved
