"""
Tests for comparator._extract_server_errors.

The Isabelle PIDE server sends JSON in two different shapes:
  1. A dict with top-level "ok" and "errors" fields.
  2. A list of node objects, each with "node_name", "status", and "messages".
Both formats must be parsed correctly.
"""

import json
from comparator import _extract_server_errors


# Fixture builders

def dict_json(line, msg="Error", file="Test.thy", kind="error", ok=False):
    """Build a dict-format server response."""
    return json.dumps({
        "ok": ok,
        "errors": [{"kind": kind, "message": msg, "pos": {"file": file, "line": line}}],
    })


def node_json(line, msg="Error", file="Test.thy", kind="error",
              node_name="Test.thy", ok=False):
    """Build a list/node-format server response."""
    return json.dumps([{
        "node_name": node_name,
        "status": {"ok": ok},
        "messages": [{"kind": kind, "message": msg, "pos": {"file": file, "line": line}}],
    }])


# Dict format

class TestDictFormat:
    def test_extracts_error_at_correct_line(self):
        errors = _extract_server_errors(dict_json(10), "Test")
        assert (10, "Error") in errors

    def test_warning_not_counted_as_error(self):
        errors = _extract_server_errors(dict_json(10, kind="warning", ok=True), "Test")
        assert errors == []

    def test_error_from_other_file_filtered(self):
        errors = _extract_server_errors(dict_json(10, file="Library.thy", ok=True), "Test")
        assert errors == []

    def test_ok_true_no_errors_is_empty(self):
        js = json.dumps({"ok": True, "errors": []})
        assert _extract_server_errors(js, "Test") == []

    def test_ok_false_empty_errors_yields_sentinel(self):
        """Server said ok=False but gave no structured details — we need a marker."""
        js = json.dumps({"ok": False, "errors": []})
        errors = _extract_server_errors(js, "Test")
        assert any(line is None for line, _ in errors)

    def test_error_with_full_path_matched(self):
        """Isabelle sometimes emits an absolute filesystem path."""
        js = dict_json(3, file="/home/user/project/Test.thy")
        errors = _extract_server_errors(js, "Test")
        assert any(line == 3 for line, _ in errors)


# List / node format

class TestNodeListFormat:
    def test_extracts_error_from_matching_node(self):
        errors = _extract_server_errors(node_json(5), "Test")
        assert any(line == 5 for line, _ in errors)

    def test_non_matching_node_ignored(self):
        js = node_json(5, node_name="OtherTheory.thy")
        errors = _extract_server_errors(js, "Test")
        assert errors == []

    def test_warning_in_node_not_counted(self):
        js = node_json(5, kind="warning")
        errors = _extract_server_errors(js, "Test")
        assert errors == []

    def test_ok_node_produces_no_errors(self):
        js = node_json(5, ok=True)
        errors = _extract_server_errors(js, "Test")
        assert errors == []


# Edge / boundary cases

class TestEdgeCases:
    def test_empty_string_returns_empty(self):
        assert _extract_server_errors("", "Test") == []

    def test_whitespace_only_returns_empty(self):
        assert _extract_server_errors("   \n  ", "Test") == []

    def test_finished_prefix_stripped(self):
        """Real server output begins with 'FINISHED ' — must still parse."""
        payload = dict_json(7)
        errors = _extract_server_errors("FINISHED " + payload, "Test")
        assert any(line == 7 for line, _ in errors)

    def test_theory_name_used_for_file_filtering(self):
        """Errors for Test_1.thy must not bleed into results for Test.thy."""
        js = dict_json(9, file="Test_1.thy", ok=True)
        errors = _extract_server_errors(js, "Test")
        assert errors == []

    def test_multiple_errors_all_extracted(self):
        js = json.dumps({"ok": False, "errors": [
            {"kind": "error", "message": "e1", "pos": {"file": "Test.thy", "line": 3}},
            {"kind": "error", "message": "e2", "pos": {"file": "Test.thy", "line": 7}},
        ]})
        errors = _extract_server_errors(js, "Test")
        lines = [l for l, _ in errors]
        assert 3 in lines and 7 in lines


# Less used JSON shapes (dict-with-nodes fallback, status field)

class TestRareJsonShapes:
    def test_dict_nodes_skips_non_matching_node(self):
        """Nodes with a different name are skipped; the matching one is processed."""
        js = json.dumps({
            "ok": False,
            "errors": [],
            "nodes": [
                { # Ignored: non-matching
                    "node_name": "Other.thy",
                    "status": {"ok": False},
                    "messages": [{"kind": "error", "pos": {"file": "Other.thy", "line": 99}, "message": "x"}],
                },
                {
                    "node_name": "Test.thy",
                    "status": {"ok": False},
                    "messages": [{"kind": "error", "pos": {"file": "Test.thy", "line": 5}, "message": "e"}],
                },
            ],
        })
        errors = _extract_server_errors(js, "Test")
        lines = [l for l, _ in errors]
        assert 5 in lines
        assert 99 not in lines

    def test_dict_with_status_field(self):
        """Top-level 'status' dict (yet another Isabelle response variant)."""
        js = json.dumps({
            "status": {"ok": False},
            "messages": [
                {"kind": "error", "pos": {"file": "Test.thy", "line": 9}, "message": "e"},
            ],
        })
        errors = _extract_server_errors(js, "Test")
        assert any(line == 9 for line, _ in errors)

    def test_collect_from_messages_file_filter(self):
        """Messages with a non-matching file path are silently dropped."""
        js = json.dumps([{
            "node_name": "Test.thy",
            "status": {"ok": False},
            "messages": [
                {"kind": "error", "pos": {"file": "Other.thy", "line": 7}, "message": "wrong"},
                {"kind": "error", "pos": {"file": "Test.thy",  "line": 3}, "message": "right"},
            ],
        }])
        errors = _extract_server_errors(js, "Test")
        lines = [l for l, _ in errors]
        assert 3 in lines
        assert 7 not in lines