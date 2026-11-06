"""Tests for the rung 2b changelog handoff in tools/publish.py.

The runbook requires the changelog handoff before the staging leg, waivable only
in writing, with the waiver recorded in the ledger row. These tests pin the
publish side of that contract with zero network:

- a handoff reference is recorded in the publish commit message;
- a waiver is recorded too, and must name what was not captured;
- neither one refuses the publish, so the skip can never be silent;
- both at once is refused, because the record would be ambiguous;
- the refusal names the lieutenant, the flag and the waiver path, so the next
  person does not have to read publish.py to clear it.
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import publish


def test_handoff_reference_is_recorded():
    line = publish.resolve_changelog_handoff(
        "psp-wiki 5a0df03, entry + 3 captures", None)
    assert line == "Changelog handoff (rung 2b): psp-wiki 5a0df03, entry + 3 captures"


def test_waiver_is_recorded_and_must_name_what_was_missed():
    line = publish.resolve_changelog_handoff(
        None, "lieutenant unavailable; no capture set for press.html this cycle")
    assert line.startswith("Changelog handoff waived (rung 2b): ")
    assert "no capture set for press.html" in line

    with pytest.raises(SystemExit) as loud:
        publish.resolve_changelog_handoff(None, "busy")
    assert "name what was not captured" in str(loud.value)


def test_neither_is_refused_loudly():
    for empty in (None, "", "   "):
        with pytest.raises(SystemExit) as loud:
            publish.resolve_changelog_handoff(empty, empty)
        msg = str(loud.value)
        assert "rung 2b" in msg
        assert "thr_6sf5hk9f4m" in msg, "the refusal must name the lieutenant"
        assert "--changelog-handoff" in msg
        assert "--changelog-waiver" in msg


def test_both_at_once_is_refused():
    with pytest.raises(SystemExit) as loud:
        publish.resolve_changelog_handoff(
            "psp-wiki 5a0df03", "could not reach the lieutenant")
    assert "not both" in str(loud.value)


def test_parser_carries_both_flags():
    parser = publish.build_parser()
    args = parser.parse_args(["--gate-report", "x.json",
                              "--changelog-handoff", "psp-wiki abc1234"])
    assert args.changelog_handoff == "psp-wiki abc1234"
    assert args.changelog_waiver is None
