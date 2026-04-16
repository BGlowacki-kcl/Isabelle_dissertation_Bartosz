"""
Tests for comparator.compare_outputs — the decision engine.

This function determines whether a test iteration is a BUG or a MATCH.
Getting it wrong means either missing real bugs (false negatives) or
generating noise (false positives), so the logic must be verified.
"""

import json
import pytest
import comparator
from comparator import compare_outputs


# Fixtures

@pytest.fixture
def no_disk(monkeypatch):
    """Suppress disk writes from _dump_raw_outputs.  Applied explicitly per-test."""
    monkeypatch.setattr(comparator, "_dump_raw_outputs", lambda *a, **kw: None)


# Canonical input builders

def oracle_pass():
    return ""

def oracle_fail(line):
    return f'At command "by" (line {line} of "Test.thy")'

def server_pass():
    return json.dumps({"ok": True, "errors": []})

def server_fail(line=10):
    return json.dumps({"ok": False, "errors": [
        {"kind": "error", "message": "proof error", "pos": {"file": "Test.thy", "line": line}},
    ]})

def server_fail_lines(*lines):
    return json.dumps({"ok": False, "errors": [
        {"kind": "error", "message": "e", "pos": {"file": "Test.thy", "line": l}}
        for l in lines
    ]})

def cmp(server_js, oracle_txt, **kw):
    return compare_outputs(server_js, oracle_txt, theory_name="Test", **kw)


# The four fundamental verdict cases

def test_both_pass_is_not_a_mismatch(no_disk):
    mismatch, reason, oracle_ok, server_ok, _ = cmp(server_pass(), oracle_pass())
    assert not mismatch
    assert reason == ""
    assert oracle_ok and server_ok


def test_both_fail_same_lines_is_not_a_mismatch(no_disk):
    mismatch, _, oracle_ok, server_ok, _ = cmp(server_fail(10), oracle_fail(10))
    assert not mismatch
    assert not oracle_ok and not server_ok


def test_server_fails_oracle_passes_is_mismatch(no_disk):
    """Server reports an error the oracle never sees — false positive or server bug."""
    mismatch, reason, oracle_ok, server_ok, _ = cmp(server_fail(10), oracle_pass())
    assert mismatch
    assert oracle_ok
    assert not server_ok
    assert reason


def test_oracle_fails_server_passes_is_mismatch(no_disk):
    """Oracle detected a proof failure the server missed — server missed a real bug."""
    mismatch, reason, oracle_ok, server_ok, _ = cmp(server_pass(), oracle_fail(10))
    assert mismatch
    assert not oracle_ok
    assert server_ok
    assert reason


def test_both_fail_different_lines_is_mismatch(no_disk):
    """Oracle flags line 5, server flags line 10 — they disagree on error location."""
    mismatch, reason, _, _, _ = cmp(server_fail(10), oracle_fail(5))
    assert mismatch
    assert "5" in reason or "10" in reason


# Server-more-verbose: NOT a bug

def test_server_more_verbose_is_not_a_mismatch(no_disk):
    """
    Oracle ⊆ server: oracle sees errors at {5}, server sees {5, 10}.
    The server being louder than the oracle is not a correctness violation —
    it just means PIDE is stricter.  This should be classified as INFO, not MISMATCH.
    """
    mismatch, _, _, _, _ = cmp(server_fail_lines(5, 10), oracle_fail(5))
    assert not mismatch


def test_server_superset_with_multiple_oracle_lines_not_a_mismatch(no_disk):
    oracle_txt = (
        'At command "by" (line 3 of "Test.thy")\n'
        'At command "apply" (line 7 of "Test.thy")'
    )
    server_js = server_fail_lines(3, 7, 12)
    mismatch, _, _, _, _ = cmp(server_js, oracle_txt)
    assert not mismatch


def test_server_misses_one_oracle_line_is_mismatch(no_disk):
    """Oracle sees {3, 7}, server only sees {3} — a missed error is a bug."""
    oracle_txt = (
        'At command "by" (line 3 of "Test.thy")\n'
        'At command "apply" (line 7 of "Test.thy")'
    )
    server_js = server_fail(3)
    mismatch, _, _, _, _ = cmp(server_js, oracle_txt)
    assert mismatch


# Invalid / malformed JSON

def test_invalid_json_is_mismatch(no_disk):
    """Unparseable JSON (starts with '{') must count as a crash / mismatch."""
    mismatch, reason, _, _, _ = cmp("{this is not JSON}", oracle_pass())
    assert mismatch
    assert "JSON" in reason


# Detail dict structure

def test_detail_contains_required_keys(no_disk):
    _, _, _, _, detail = cmp(server_pass(), oracle_pass())
    required = {"server_error_lines", "server_errors", "oracle_error_lines",
                "oracle_pass", "server_pass"}
    assert required <= detail.keys()


def test_detail_reflects_extracted_lines(no_disk):
    _, _, _, _, detail = cmp(server_fail(7), oracle_fail(7))
    assert 7 in detail["server_error_lines"]
    assert 7 in detail["oracle_error_lines"]
    assert not detail["oracle_pass"]
    assert not detail["server_pass"]


def test_detail_pass_flags_correct_on_pass(no_disk):
    _, _, _, _, detail = cmp(server_pass(), oracle_pass())
    assert detail["oracle_pass"]
    assert detail["server_pass"]


# Bytes inputs (defensive)

def test_none_inputs_treated_as_empty(no_disk):
    mismatch, _, oracle_ok, server_ok, _ = cmp(None, None)
    assert not mismatch


# _dump_raw_outputs — writes debugging artefacts to disk

def test_dump_raw_outputs_creates_files():
    """_dump_raw_outputs writes oracle and server text to disk beside comparator.py."""
    import comparator as cmp_mod
    from pathlib import Path
    base = Path(cmp_mod.__file__).parent
    wid = "cov_test"
    try:
        cmp_mod._dump_raw_outputs("server content", "oracle content", worker_id=wid)
        assert (base / f"oracle_output_{wid}.txt").read_text() == "oracle content"
        assert (base / f"server_output_{wid}.txt").read_text() == "server content"
    finally:
        for name in [f"oracle_output_{wid}.txt", f"server_output_{wid}.txt"]:
            (base / name).unlink(missing_ok=True)


def test_dump_raw_outputs_no_suffix_when_worker_none():
    import comparator as cmp_mod
    from pathlib import Path
    base = Path(cmp_mod.__file__).parent
    try:
        cmp_mod._dump_raw_outputs("s", "o", worker_id=None)
        assert (base / "oracle_output.txt").exists()
        assert (base / "server_output.txt").exists()
    finally:
        for name in ["oracle_output.txt", "server_output.txt"]:
            (base / name).unlink(missing_ok=True)
