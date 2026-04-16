"""
Tests for reporter.py.

Covers both the pure formatting helpers (_result_label, _write_comp_detail) and the
file-writing functions (save_report, save_match_log).  The latter are tested by
redirecting REPORT_DIR / NO_BUG_DIR to pytest's tmp_path so no real artefacts are
created in the project tree.
"""

import io
import reporter
from reporter import _result_label, _write_comp_detail, save_report, save_match_log


class TestResultLabel:
    def test_true_contains_pass(self):
        label = _result_label(True)
        assert "PASS" in label

    def test_false_contains_fail(self):
        label = _result_label(False)
        assert "FAIL" in label

    def test_returns_string(self):
        assert isinstance(_result_label(True), str)
        assert isinstance(_result_label(False), str)


class TestWriteCompDetail:
    def _run(self, detail):
        buf = io.StringIO()
        _write_comp_detail(buf, detail)
        return buf.getvalue()

    def test_oracle_lines_appear_in_output(self):
        detail = {
            "oracle_error_lines": [5, 10],
            "server_error_lines": [],
            "server_errors": [],
        }
        out = self._run(detail)
        assert "5" in out and "10" in out

    def test_server_lines_appear_in_output(self):
        detail = {
            "oracle_error_lines": [],
            "server_error_lines": [3, 8],
            "server_errors": [],
        }
        out = self._run(detail)
        assert "3" in out and "8" in out

    def test_server_error_messages_included(self):
        detail = {
            "oracle_error_lines": [],
            "server_error_lines": [3],
            "server_errors": [(3, "proof failed here")],
        }
        out = self._run(detail)
        assert "proof failed here" in out

    def test_none_detail_writes_placeholder(self):
        out = self._run(None)
        assert "no comparison detail" in out.lower()

    def test_empty_detail_does_not_raise(self):
        """Empty (but valid) dict should not crash the writer."""
        detail = {
            "oracle_error_lines": [],
            "server_error_lines": [],
            "server_errors": [],
        }
        out = self._run(detail)
        assert isinstance(out, str)


# save_report — file-writing integration

DETAIL = {
    "oracle_error_lines": [10],
    "server_error_lines": [],
    "server_errors": [],
}

class TestSaveReport:
    def test_creates_thy_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(reporter, "REPORT_DIR", tmp_path)
        save_report(1, "theory T begin end",
                    oracle_res=(True, "oracle log"),
                    server_res=(False, "server log"),
                    mismatch_reason="disagree",
                    comp_detail=DETAIL, worker_id=0)
        assert any(f.suffix == ".thy" for f in tmp_path.iterdir())

    def test_creates_info_file_with_iteration(self, tmp_path, monkeypatch):
        monkeypatch.setattr(reporter, "REPORT_DIR", tmp_path)
        save_report(42, "theory T begin end",
                    oracle_res=(True, "oracle log"),
                    server_res=(False, "server log"),
                    mismatch_reason="",
                    comp_detail=DETAIL, worker_id=1)
        info_files = [f for f in tmp_path.iterdir() if f.suffix == ".info"]
        assert info_files
        text = info_files[0].read_text()
        assert "Iteration: 42" in text
        assert "Worker: 1" in text

    def test_mismatch_reason_written_to_info(self, tmp_path, monkeypatch):
        monkeypatch.setattr(reporter, "REPORT_DIR", tmp_path)
        save_report(1, "theory T begin end",
                    oracle_res=(True, ""),
                    server_res=(False, ""),
                    mismatch_reason="Server missed line 5",
                    comp_detail=DETAIL, worker_id=0)
        info = next(f for f in tmp_path.iterdir() if f.suffix == ".info")
        assert "Server missed line 5" in info.read_text()

    def test_copies_mutations_log_when_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr(reporter, "REPORT_DIR", tmp_path)
        mutations_log = tmp_path / "mutations_5.txt"
        mutations_log.write_text("Mutation: swapped ∧ → ∨\n")
        monkeypatch.chdir(tmp_path)
        save_report(1, "theory T begin end",
                    oracle_res=(True, ""), server_res=(False, ""),
                    comp_detail=DETAIL, worker_id=5)
        assert any(f.suffix == ".txt" and "mutations" in f.name for f in tmp_path.iterdir())


# save_match_log — file-writing integration

class TestSaveMatchLog:
    def test_creates_txt_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(reporter, "NO_BUG_DIR", tmp_path)
        save_match_log(7, oracle_res=(True, ""), server_res=(True, ""),
                       comp_detail=None, worker_id=0)
        assert any(f.suffix == ".txt" for f in tmp_path.iterdir())

    def test_match_file_contains_iteration(self, tmp_path, monkeypatch):
        monkeypatch.setattr(reporter, "NO_BUG_DIR", tmp_path)
        save_match_log(99, oracle_res=(True, ""), server_res=(True, ""),
                       comp_detail=DETAIL, worker_id=2)
        txt = next(f for f in tmp_path.iterdir() if f.suffix == ".txt")
        assert "Iteration: 99" in txt.read_text()

    def test_info_reason_written_when_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr(reporter, "NO_BUG_DIR", tmp_path)
        save_match_log(1, oracle_res=(False, ""), server_res=(False, ""),
                       info_reason="server more verbose", worker_id=0)
        txt = next(f for f in tmp_path.iterdir() if f.suffix == ".txt")
        content = txt.read_text()
        assert "server more verbose" in content
        assert "INFO" in content
