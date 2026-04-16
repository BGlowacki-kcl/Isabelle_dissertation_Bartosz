"""
Mocked subprocess tests for oracle.run_oracle and server.start_isabelle_server.

These are the only two public functions that invoke Isabelle binaries.  By
patching subprocess.Popen / subprocess.run we can drive every branch in their
control flow without a real Isabelle installation.
"""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import oracle
from oracle import run_oracle
from server import start_isabelle_server


# Shared helpers

DIFFERENTIAL_DIR = Path(oracle.__file__).parent
MOCK_WORKER_ID   = "_mock"


def _proc(stdout="", stderr="", returncode=0):
    """Build a fake subprocess.Popen result that succeeds immediately."""
    p = MagicMock()
    p.communicate.return_value = (stdout, stderr)
    p.returncode = returncode
    p.pid = 99999
    return p


@pytest.fixture(autouse=True)
def cleanup_mock_oracle_dir():
    """Remove .oracle__mock if it was created during a test."""
    yield
    d = DIFFERENTIAL_DIR / f".oracle_{MOCK_WORKER_ID}"
    if d.exists():
        shutil.rmtree(d)


# oracle -> run_oracle

class TestRunOracleSuccess:
    @patch("oracle.shutil.copy2")
    @patch("oracle.subprocess.Popen")
    def test_clean_build_returns_true(self, mock_popen, mock_copy):
        mock_popen.return_value = _proc(stdout="Finished (0:01:23 elapsed)", returncode=0)
        success, output = run_oracle("Test_mock", worker_id=MOCK_WORKER_ID)
        assert success is True
        assert "Finished" in output

    @patch("oracle.shutil.copy2")
    @patch("oracle.subprocess.Popen")
    def test_isabelle_build_command_invoked(self, mock_popen, mock_copy):
        """The build command must mention 'build' and the oracle session name."""
        mock_popen.return_value = _proc(returncode=0)
        run_oracle("Test_mock", worker_id=MOCK_WORKER_ID)
        cmd = mock_popen.call_args[0][0]
        assert "build" in cmd
        assert any(MOCK_WORKER_ID in arg for arg in cmd)

    @patch("oracle.shutil.copy2")
    @patch("oracle.subprocess.Popen")
    def test_root_file_created_with_correct_session(self, mock_popen, mock_copy):
        """A ROOT file specifying our oracle session must be written to oracle_dir."""
        mock_popen.return_value = _proc(returncode=0)
        run_oracle("Test_mock", worker_id=MOCK_WORKER_ID)
        root = DIFFERENTIAL_DIR / f".oracle_{MOCK_WORKER_ID}" / "ROOT"
        assert root.exists()
        content = root.read_text()
        assert f"OracleSession_{MOCK_WORKER_ID}" in content
        assert "quick_and_dirty = false" in content

    @patch("oracle._extract_session_imports", return_value=["HOL-Algebra"])
    @patch("oracle.shutil.copy2")
    @patch("oracle.subprocess.Popen")
    def test_root_file_contains_sessions_clause_for_extra_imports(
            self, mock_popen, mock_copy, mock_imports):
        """When the theory imports extra sessions, the ROOT file must list them."""
        mock_popen.return_value = _proc(returncode=0)
        run_oracle("Test_mock", worker_id=MOCK_WORKER_ID)
        root = DIFFERENTIAL_DIR / f".oracle_{MOCK_WORKER_ID}" / "ROOT"
        content = root.read_text()
        assert "sessions" in content
        assert "HOL-Algebra" in content


class TestRunOracleErrors:
    @patch("oracle.shutil.copy2")
    @patch("oracle.subprocess.Popen")
    def test_at_command_error_returns_false(self, mock_popen, mock_copy):
        output = 'At command "by" (line 5 of "Test_mock.thy")'
        mock_popen.return_value = _proc(stdout=output, returncode=0)
        success, _ = run_oracle("Test_mock", worker_id=MOCK_WORKER_ID)
        assert success is False

    @patch("oracle.shutil.copy2")
    @patch("oracle.subprocess.Popen")
    def test_failed_proof_error_returns_false(self, mock_popen, mock_copy):
        output = 'Failed to finish proof (line 10 of "Test_mock.thy")'
        mock_popen.return_value = _proc(stdout=output, returncode=0)
        success, _ = run_oracle("Test_mock", worker_id=MOCK_WORKER_ID)
        assert success is False

    @patch("oracle.shutil.copy2")
    @patch("oracle.subprocess.Popen")
    def test_nonzero_exit_without_error_text_returns_false(self, mock_popen, mock_copy):
        """Non-zero returncode with no parseable error text still counts as failure."""
        mock_popen.return_value = _proc(stdout="Build failed", returncode=1)
        success, output = run_oracle("Test_mock", worker_id=MOCK_WORKER_ID)
        assert success is False

    @patch("oracle.shutil.copy2")
    @patch("oracle.subprocess.Popen")
    def test_output_combines_stdout_and_stderr(self, mock_popen, mock_copy):
        p = MagicMock()
        p.communicate.return_value = ("stdout part", "stderr part")
        p.returncode = 0
        p.pid = 99999
        mock_popen.return_value = p
        success, output = run_oracle("Test_mock", worker_id=MOCK_WORKER_ID)
        assert "stdout part" in output
        assert "stderr part" in output

    @patch("oracle.shutil.copy2")
    @patch("oracle.subprocess.Popen")
    def test_unexpected_exception_returns_false_empty(self, mock_popen, mock_copy):
        mock_popen.side_effect = OSError("something went wrong")
        success, output = run_oracle("Test_mock", worker_id=MOCK_WORKER_ID)
        assert success is False
        assert output == ""


class TestRunOracleTimeout:
    @patch("oracle.os.getpgid", return_value=12345)
    @patch("oracle.os.killpg")
    @patch("oracle.shutil.copy2")
    @patch("oracle.subprocess.Popen")
    def test_timeout_returns_false(self, mock_popen, mock_copy, mock_killpg, mock_getpgid):
        p = MagicMock()
        p.pid = 99999
        p.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd=["isabelle"], timeout=1),
            ("partial output", ""),
        ]
        mock_popen.return_value = p
        success, output = run_oracle("Test_mock", worker_id=MOCK_WORKER_ID, timeout=1)
        assert success is False

    @patch("oracle.os.getpgid", return_value=12345)
    @patch("oracle.os.killpg")
    @patch("oracle.shutil.copy2")
    @patch("oracle.subprocess.Popen")
    def test_timeout_kills_process_group(self, mock_popen, mock_copy, mock_killpg, mock_getpgid):
        p = MagicMock()
        p.pid = 99999
        p.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd=["isabelle"], timeout=1),
            ("", ""),
        ]
        mock_popen.return_value = p
        run_oracle("Test_mock", worker_id=MOCK_WORKER_ID, timeout=1)
        mock_killpg.assert_called_once()

    @patch("oracle.os.getpgid", side_effect=ProcessLookupError)
    @patch("oracle.os.killpg")
    @patch("oracle.shutil.copy2")
    @patch("oracle.subprocess.Popen")
    def test_timeout_handles_missing_process_gracefully(
            self, mock_popen, mock_copy, mock_killpg, mock_getpgid):
        """If the process already died before we can kill it, no exception is raised."""
        p = MagicMock()
        p.pid = 99999
        p.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd=["isabelle"], timeout=1),
            ("", ""),
        ]
        mock_popen.return_value = p
        success, _ = run_oracle("Test_mock", worker_id=MOCK_WORKER_ID, timeout=1)
        assert success is False   # still reports failure


# server.start_isabelle_server

def _server_proc(*lines):
    """Build a fake Popen process whose stdout emits the given lines then EOF."""
    p = MagicMock()
    p.stdout.readline.side_effect = list(lines) + [""]
    p.poll.return_value = None
    return p


class TestStartIsabelleServer:
    @patch("server.subprocess.run")
    @patch("server.subprocess.Popen")
    def test_parses_host_port_password(self, mock_popen, mock_run):
        line = 'server "isabelle" = 127.0.0.1:1234 (password "s3cr3t")\n'
        mock_popen.return_value = _server_proc(line)
        host, port, password = start_isabelle_server()
        assert host == "127.0.0.1"
        assert port == 1234
        assert password == "s3cr3t"

    @patch("server.subprocess.run")
    @patch("server.subprocess.Popen")
    def test_skips_noise_lines_before_server_line(self, mock_popen, mock_run):
        server_line = 'server "isabelle" = 192.168.1.5:9999 (password "abc")\n'
        mock_popen.return_value = _server_proc(
            "Starting Isabelle server...\n",
            "Some debug output\n",
            server_line,
        )
        host, port, password = start_isabelle_server()
        assert port == 9999
        assert password == "abc"

    @patch("server.subprocess.run")
    @patch("server.subprocess.Popen")
    def test_kills_existing_server_first(self, mock_popen, mock_run):
        """subprocess.run must be called with the -x flag before starting new server."""
        server_line = 'server "isabelle" = 127.0.0.1:1234 (password "x")\n'
        mock_popen.return_value = _server_proc(server_line)
        start_isabelle_server()
        cmd = mock_run.call_args[0][0]
        assert "-x" in cmd

    @patch("server.subprocess.run")
    @patch("server.subprocess.Popen")
    def test_raises_runtime_error_on_eof_without_server_line(self, mock_popen, mock_run):
        """If stdout closes without the expected server line, raise RuntimeError."""
        mock_popen.return_value = _server_proc()
        with pytest.raises(RuntimeError, match="Failed to parse"):
            start_isabelle_server()

    @patch("server.subprocess.run")
    @patch("server.subprocess.Popen")
    def test_raises_when_process_exits_early(self, mock_popen, mock_run):
        """If poll() shows the process exited on a non-matching line, raise RuntimeError."""
        p = MagicMock()
        p.stdout.readline.side_effect = ["startup noise\n"]
        p.poll.return_value = 1
        mock_popen.return_value = p
        with pytest.raises(RuntimeError):
            start_isabelle_server()

    @patch("server.subprocess.run")
    @patch("server.subprocess.Popen")
    def test_port_returned_as_integer(self, mock_popen, mock_run):
        line = 'server "isabelle" = 0.0.0.0:8080 (password "p")\n'
        mock_popen.return_value = _server_proc(line)
        _, port, _ = start_isabelle_server()
        assert isinstance(port, int)
