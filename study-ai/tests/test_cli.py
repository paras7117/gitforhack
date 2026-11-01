"""
Tests for Command-Line Interface.
"""

from git_provenance.cli import create_parser, main
import pytest


def test_parser_creation():
    parser = create_parser()
    args = parser.parse_args(["status", "--json"])
    assert args.subcommand == "status"
    assert args.json is True

    args_attest = parser.parse_args(["attest", "--status", "passed", "--env", "production"])
    assert args_attest.subcommand == "attest"
    assert args_attest.status == "passed"
    assert args_attest.env == "production"


def test_main_without_args(capsys):
    ret = main([])
    assert ret == 0
    captured = capsys.readouterr()
    assert "git-provenance" in captured.out
