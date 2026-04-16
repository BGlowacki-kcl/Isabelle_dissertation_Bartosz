"""
Tests for server.py socket-level helpers.

read_until_finished / read_until_ok implement a tiny line-oriented protocol
over a socket file object.  We test them with io.StringIO to avoid real sockets.
"""

import io
from server import read_until_finished, read_until_ok


def make_file(*lines):
    """Return a file-like object with the given lines."""
    return io.StringIO("\n".join(lines) + "\n")


# read_until_finished

class TestReadUntilFinished:
    def test_returns_finished_line(self):
        f = make_file("FINISHED {data}")
        assert read_until_finished(f) == "FINISHED {data}"

    def test_returns_none_on_failed(self):
        f = make_file("FAILED reason")
        assert read_until_finished(f) is None

    def test_returns_none_on_eof(self):
        f = io.StringIO("")
        assert read_until_finished(f) is None

    def test_skips_intermediate_lines(self):
        f = make_file("NOTE loading", "NOTE progress 50%", "FINISHED done")
        result = read_until_finished(f)
        assert result == "FINISHED done"

    def test_failed_stops_before_finished(self):
        """FAILED should terminate immediately, not continue looking for FINISHED."""
        f = make_file("FAILED early", "FINISHED late")
        assert read_until_finished(f) is None

    def test_finished_with_json_payload(self):
        line = 'FINISHED {"ok": true, "nodes": []}'
        f = make_file(line)
        assert read_until_finished(f) == line


# read_until_ok

class TestReadUntilOk:
    def test_returns_ok_line(self):
        f = make_file("OK 1")
        assert read_until_ok(f) == "OK 1"

    def test_returns_none_on_error(self):
        f = make_file("ERROR bad password")
        assert read_until_ok(f) is None

    def test_returns_none_on_failed(self):
        f = make_file("FAILED")
        assert read_until_ok(f) is None

    def test_returns_none_on_eof(self):
        f = io.StringIO("")
        assert read_until_ok(f) is None

    def test_skips_intermediate_before_ok(self):
        f = make_file("connecting...", "OK ready")
        assert read_until_ok(f) == "OK ready"
