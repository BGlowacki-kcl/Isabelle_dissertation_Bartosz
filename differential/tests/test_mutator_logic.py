"""
Tests for mutator.py — theory loading, naming helpers, and _mutate_content.

The central invariant of _mutate_content is the begin/end protection: mutations
must never touch the theory header (lines up to and including 'begin') or the
closing 'end'.  Violating this produces broken theories that fail for structural 
reasons rather than proof reasons, making both oracle and server
fail fast and always agree.
"""

import random
import pytest
from mutator import (
    _mutate_content,
    load_new_theory,
    mutate,
    theory_name_for,
    _theory_file_for,
    _mutations_log_for,
)


THEORY = (
    "theory Test\n"
    "  imports Main\n"
    "begin\n"
    "\n"
    'lemma foo: "P ∧ Q"\n'
    "  by simp\n"
    "\n"
    "end\n"
)


# Naming helpers

class TestNamingHelpers:
    def test_no_worker_gives_base_names(self):
        assert theory_name_for(None) == "Test"
        assert _theory_file_for(None) == "Test.thy"
        assert _mutations_log_for(None) == "mutations.txt"

    def test_worker_id_appended(self):
        assert theory_name_for(0)  == "Test_0"
        assert theory_name_for(3)  == "Test_3"
        assert _theory_file_for(7) == "Test_7.thy"
        assert _mutations_log_for(2) == "mutations_2.txt"


# _mutate_content: structural invariants

class TestMutateContentBoundaries:
    def test_theory_header_preserved(self):
        """Lines before (and including) 'begin' must survive every mutation."""
        for seed in range(40):
            random.seed(seed)
            result, _ = _mutate_content(THEORY)
            assert result.startswith("theory Test\n  imports Main\nbegin"), \
                f"seed {seed}: header corrupted"

    def test_end_footer_preserved(self):
        """The final 'end' must survive every mutation."""
        for seed in range(40):
            random.seed(seed)
            result, _ = _mutate_content(THEORY)
            assert result.rstrip().endswith("end"), \
                f"seed {seed}: footer corrupted"

    def test_description_always_nonempty_string(self):
        for seed in range(20):
            random.seed(seed)
            _, desc = _mutate_content(THEORY)
            assert isinstance(desc, str) and desc

    def test_result_always_string(self):
        for seed in range(20):
            random.seed(seed)
            result, _ = _mutate_content(THEORY)
            assert isinstance(result, str)


class TestMutateContentNoopCases:
    def test_missing_begin_marker_is_noop(self):
        """Content without 'begin' has no safe mutable region."""
        content = "lemma foo: True\n  by simp"
        result, desc = _mutate_content(content)
        assert result == content
        assert "No-op" in desc

    def test_missing_end_marker_is_noop(self):
        content = "theory T\nbegin\nlemma foo: True"
        result, desc = _mutate_content(content)
        assert result == content
        assert "No-op" in desc

    def test_adjacent_begin_end_is_noop(self):
        """theory T\nbegin\nend has zero mutable lines."""
        content = "theory T\nbegin\nend"
        result, desc = _mutate_content(content)
        assert "No-op" in desc


# load_new_theory — reads from input/, writes Test[_N].thy + mutations log

SOURCE_THEORY = (
    "theory Source\n"
    "  imports Main\n"
    "begin\n"
    "\n"
    'lemma bar: "P ∧ Q"\n'
    "  by simp\n"
    "\n"
    "end\n"
)


@pytest.fixture
def input_dir(tmp_path):
    """Create a minimal input/ directory inside tmp_path."""
    d = tmp_path / "input"
    d.mkdir()
    (d / "Source.thy").write_text(SOURCE_THEORY)
    return tmp_path


class TestLoadNewTheory:
    def test_creates_theory_file(self, input_dir, monkeypatch):
        monkeypatch.chdir(input_dir)
        load_new_theory(worker_id=0)
        assert (input_dir / "Test_0.thy").exists()

    def test_renames_theory_header(self, input_dir, monkeypatch):
        monkeypatch.chdir(input_dir)
        load_new_theory(worker_id=0)
        content = (input_dir / "Test_0.thy").read_text()
        assert content.startswith("theory Test_0")

    def test_creates_mutations_log(self, input_dir, monkeypatch):
        monkeypatch.chdir(input_dir)
        load_new_theory(worker_id=3)
        assert (input_dir / "mutations_3.txt").exists()

    def test_mutations_log_records_source_file(self, input_dir, monkeypatch):
        monkeypatch.chdir(input_dir)
        load_new_theory(worker_id=0)
        log = (input_dir / "mutations_0.txt").read_text()
        assert "Source file:" in log

    def test_raises_when_no_input_files(self, tmp_path, monkeypatch):
        (tmp_path / "input").mkdir()
        monkeypatch.chdir(tmp_path)
        with pytest.raises(FileNotFoundError):
            load_new_theory(worker_id=0)


# mutate — applies one in-place mutation and appends to the log

class TestMutate:
    def _setup(self, tmp_path):
        """Write a theory file and empty mutations log, return path root."""
        thy = tmp_path / "Test_0.thy"
        thy.write_text(THEORY)
        (tmp_path / "mutations_0.txt").write_text("")
        return tmp_path

    def test_returns_description_string(self, tmp_path, monkeypatch):
        self._setup(tmp_path)
        monkeypatch.chdir(tmp_path)
        desc = mutate(worker_id=0)
        assert isinstance(desc, str) and desc

    def test_appends_to_mutations_log(self, tmp_path, monkeypatch):
        self._setup(tmp_path)
        monkeypatch.chdir(tmp_path)
        mutate(worker_id=0)
        log = (tmp_path / "mutations_0.txt").read_text()
        assert "  - " in log

    def test_theory_file_modified_or_unchanged(self, tmp_path, monkeypatch):
        """After mutation, the theory file must still be valid text."""
        self._setup(tmp_path)
        monkeypatch.chdir(tmp_path)
        mutate(worker_id=0)
        content = (tmp_path / "Test_0.thy").read_text()
        assert isinstance(content, str) and content
