"""
Tests for oracle._oracle_has_theory_error and oracle._extract_session_imports.

These regex-based parsers are critical:  _oracle_has_theory_error is the ground-truth
detector — a wrong match here silently makes the oracle agree or disagree with the server
when it shouldn't.
"""

from oracle import _oracle_has_theory_error, _extract_session_imports


# _oracle_has_theory_error

class TestOracleErrorDetection:
    def test_clean_output_has_no_error(self):
        has_error, lines = _oracle_has_theory_error("", "Test")
        assert not has_error
        assert lines == []

    def test_success_message_not_an_error(self):
        output = "Finished HOL-Combinatorics (0:03:12 elapsed time)"
        has_error, _ = _oracle_has_theory_error(output, "Test")
        assert not has_error

    def test_at_command_detected(self):
        output = 'At command "by" (line 10 of "Test.thy")'
        has_error, lines = _oracle_has_theory_error(output, "Test")
        assert has_error
        assert lines == [10]

    def test_at_command_with_absolute_path(self):
        """Isabelle often prints full paths; they must still be matched."""
        output = 'At command "apply" (line 8 of "/home/user/project/Test.thy")'
        has_error, lines = _oracle_has_theory_error(output, "Test")
        assert has_error
        assert lines == [8]

    def test_at_command_case_insensitive(self):
        output = 'AT COMMAND "by" (line 3 of "Test.thy")'
        has_error, lines = _oracle_has_theory_error(output, "Test")
        assert has_error
        assert lines == [3]

    def test_failed_proof_detected(self):
        output = 'Failed to finish proof (line 5 of "Test.thy")'
        has_error, lines = _oracle_has_theory_error(output, "Test")
        assert has_error
        assert lines == [5]

    def test_library_error_ignored(self):
        """Errors from HOL standard library must not pollute results."""
        output = 'At command "by" (line 306 of "~~/src/HOL/Library/FuncSet.thy")'
        has_error, lines = _oracle_has_theory_error(output, "Test")
        assert not has_error
        assert lines == []

    def test_other_theory_file_ignored(self):
        output = 'At command "by" (line 5 of "OtherTheory.thy")'
        has_error, lines = _oracle_has_theory_error(output, "Test")
        assert not has_error

    def test_theory_name_not_matched_as_prefix(self):
        """'Test' must not match 'Test_0.thy' — worker suffixes exist."""
        output = 'At command "by" (line 12 of "Test_0.thy")'
        has_error, _ = _oracle_has_theory_error(output, "Test")
        assert not has_error

    def test_worker_theory_name_matched(self):
        output = 'At command "by" (line 12 of "Test_0.thy")'
        has_error, lines = _oracle_has_theory_error(output, "Test_0")
        assert has_error
        assert lines == [12]

    def test_multiple_lines_sorted_ascending(self):
        output = (
            'At command "by" (line 15 of "Test.thy")\n'
            'At command "apply" (line 7 of "Test.thy")'
        )
        has_error, lines = _oracle_has_theory_error(output, "Test")
        assert lines == [7, 15]

    def test_duplicate_lines_deduplicated(self):
        """Same line appearing in both patterns should appear only once."""
        output = (
            'At command "by" (line 3 of "Test.thy")\n'
            'Failed to finish proof (line 3 of "Test.thy")'
        )
        has_error, lines = _oracle_has_theory_error(output, "Test")
        assert lines == [3]

    def test_mixed_own_and_library_errors(self):
        """Library errors must be stripped even when own errors are present."""
        output = (
            'At command "by" (line 306 of "~~/src/HOL/Library/FuncSet.thy")\n'
            'At command "apply" (line 7 of "Test.thy")'
        )
        has_error, lines = _oracle_has_theory_error(output, "Test")
        assert has_error
        assert lines == [7]


# _extract_session_imports

class TestExtractSessionImports:
    def test_qualified_import_extracts_prefix(self, tmp_path):
        thy = tmp_path / "Test.thy"
        thy.write_text('theory Test imports "HOL-Algebra.Ring" begin end')
        assert _extract_session_imports(thy) == ["HOL-Algebra"]

    def test_multiple_imports_all_extracted(self, tmp_path):
        thy = tmp_path / "Test.thy"
        thy.write_text(
            'theory Test imports "HOL-Algebra.Ring" "HOL-Number_Theory.Primes" begin end'
        )
        sessions = _extract_session_imports(thy)
        assert "HOL-Algebra" in sessions
        assert "HOL-Number_Theory" in sessions

    def test_unqualified_import_excluded(self, tmp_path):
        """Plain 'Main' has no dot, so no session prefix to extract."""
        thy = tmp_path / "Test.thy"
        thy.write_text("theory Test imports Main begin end")
        assert _extract_session_imports(thy) == []

    def test_home_path_import_excluded(self, tmp_path):
        """~~/... paths are local directory references, not session names."""
        thy = tmp_path / "Test.thy"
        thy.write_text('theory Test imports "~~/src/HOL/Library/Multiset" begin end')
        assert _extract_session_imports(thy) == []

    def test_duplicates_deduplicated_and_ordered(self, tmp_path):
        thy = tmp_path / "Test.thy"
        thy.write_text(
            'theory Test imports "HOL-Algebra.Ring" "HOL-Algebra.Group" begin end'
        )
        sessions = _extract_session_imports(thy)
        assert sessions.count("HOL-Algebra") == 1

    def test_no_imports_keyword_returns_empty(self, tmp_path):
        """Theory with no 'imports … begin' block yields no sessions."""
        thy = tmp_path / "Test.thy"
        thy.write_text("-- a bare comment, no theory header")
        assert _extract_session_imports(thy) == []

    def test_missing_file_returns_empty_list(self, tmp_path):
        sessions = _extract_session_imports(tmp_path / "nonexistent.thy")
        assert sessions == []
