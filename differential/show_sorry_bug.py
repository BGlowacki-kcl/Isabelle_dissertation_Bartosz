import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from server import start_isabelle_server, read_until_finished

THEORY_NAME = "BugDemo"
THEORY_CONTENT = """\
theory BugDemo
  imports "HOL-Combinatorics.Multiset_Permutations"
begin

text \\<open>
  map_index_self: mapping the index function over a distinct list gives [0..<length xs].
\\<close>

lemma map_index_self:
  assumes "distinct xs"
  shows   "map (index xs) xs = [0..<length xs]"
proof -
  have "xs = map (\\<lambda>i. xs ! i) [0..<length xs]"
    by (simp add: map_nth)
  also have "map (index xs) \\<dots> = map id [0..<length xs]"
    by (intro map_cong) simp_all
  finally show ?thesis
    by sorry
qed

end
"""

# The line numbers we expect to see (1-indexed as Isabelle reports them)
ORACLE_EXPECTED_LINE = 19   # "qed"
PIDE_EXPECTED_LINE   = 18   # "by sorry"

TIMEOUT = 12000  # seconds

def _connect(host, port, password):
    sock = socket.create_connection((host, port))
    sock.settimeout(TIMEOUT)
    f = sock.makefile("rw", buffering=1)
    f.write(f"{password}\n")
    handshake = f.readline().strip()
    if not handshake.startswith("OK"):
        sock.close()
        raise ConnectionError(f"Handshake failed: {handshake!r}")
    return sock, f


def run_pide(theory_file: Path, host, port, password) -> tuple[str, list[int]]:
    """
    Load theory_file into a fresh HOL session via use_theories.
    Returns (raw_response_string, sorted_error_lines).
    Uses read_until_finished from server.py (the tested version).
    """
    theory_name = theory_file.stem
    work_dir    = str(theory_file.parent)

    print(f"  [PIDE] Connecting to {host}:{port}...")
    sock, f = _connect(host, port, password)
    raw = ""
    try:
        print(f"  [PIDE] Sending session_start (HOL)...")
        f.write(f'session_start {{"session": "HOL"}}\n')
        finished = read_until_finished(f)
        print(f"  [PIDE] session_start response: {(finished or 'FAILED')[:120]}")
        if not finished:
            raw = "session_start returned FAILED"
            return raw, []
        m = re.search(r'"session_id"\s*:\s*"([^"]+)"', finished)
        if not m:
            raw = f"No session_id in: {finished}"
            return raw, []
        session_id = m.group(1)
        print(f"  [PIDE] Session ID: {session_id}")

        cmd = (f'use_theories {{"session_id": "{session_id}",'
               f' "theories": ["{theory_name}"],'
               f' "master_dir": "{work_dir}"}}')
        print(f"  [PIDE] Sending: {cmd}")
        f.write(cmd + "\n")
        result = read_until_finished(f)
        print(f"  [PIDE] use_theories response: {'FAILED' if result is None else 'FINISHED (' + str(len(result)) + ' chars)'}")

        try:
            f.write(f'session_stop {{"session_id": "{session_id}"}}\n')
            read_until_finished(f)
        except Exception:
            pass

        raw = result or "use_theories returned FAILED"
    except Exception as e:
        raw = f"Exception in run_pide: {e}"
        print(f"  [PIDE] ERROR: {e}")
    finally:
        try:
            f.close()
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass

    error_lines = []
    if raw.startswith("FINISHED"):
        try:
            data = json.loads(raw[len("FINISHED"):].strip())
            thy_name = theory_file.name

            for err in data.get("errors", []):
                if err.get("kind") == "error":
                    pos  = err.get("pos", {})
                    line = pos.get("line")
                    if line is not None and thy_name in pos.get("file", ""):
                        error_lines.append(int(line))

            if not error_lines:
                for node in data.get("nodes", []):
                    if thy_name not in node.get("node_name", ""):
                        continue
                    for msg in node.get("messages", []):
                        if msg.get("kind") == "error":
                            line = msg.get("pos", {}).get("line")
                            if line is not None:
                                error_lines.append(int(line))
                    break
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  [PIDE] JSON parse error: {e}")

    return raw, sorted(set(error_lines))

def run_oracle(theory_file: Path) -> tuple[str, list[int]]:
    """
    Run isabelle build on theory_file.
    Returns (output_text, sorted_error_lines).
    """
    theory_name  = theory_file.stem
    oracle_dir   = theory_file.parent / ".show_bug_oracle"
    oracle_dir.mkdir(exist_ok=True)

    dest = oracle_dir / theory_file.name
    shutil.copy2(str(theory_file), str(dest))

    root = (
        f'session "ShowBugOracle" = "HOL-Combinatorics" +\n'
        f'  options [quick_and_dirty = false]\n'
        f'  theories\n'
        f'    "{theory_name}"\n'
    )
    (oracle_dir / "ROOT").write_text(root)

    proc = subprocess.Popen(
        ["isabelle", "build", "-v", "-d", str(oracle_dir), "ShowBugOracle"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        preexec_fn=os.setsid,
    )
    try:
        stdout, stderr = proc.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        stdout, stderr = proc.communicate()
        return (stdout + stderr), []

    output = stdout + stderr

    at_cmd = re.compile(
        r'At command[^\n]+\(line (\d+) of "[^"]*' + re.escape(theory_name) + r'\.thy"\)',
        re.IGNORECASE,
    )
    lines = sorted({int(m.group(1)) for m in at_cmd.finditer(output)})
    return output, lines

def _banner(title):
    w = 60
    print("\n" + "=" * w)
    print(f"  {title}")
    print("=" * w)


def _save_outputs(script_dir: Path, oracle_output: str, pide_raw: str, run: int):
    oracle_path = script_dir / f"show_bug_oracle_{run}.txt"
    pide_path   = script_dir / f"show_bug_pide_{run}.txt"
    oracle_path.write_text(oracle_output, encoding="utf-8")
    pide_path.write_text(pide_raw, encoding="utf-8")
    print(f"\n  [Saved] Oracle output → {oracle_path}")
    print(f"  [Saved] PIDE output   → {pide_path}")


def _show_results(oracle_output, oracle_lines, pide_raw, pide_lines):
    _banner("ORACLE  (isabelle build)")
    for line in oracle_output.splitlines():
        if any(kw in line for kw in ("***", "FAILED", "Finished", "Error", "error")):
            print("  " + line)

    _banner("PIDE SERVER  (use_theories)")
    if not pide_raw.startswith("FINISHED"):
        print(f"  (no FINISHED response — got: {pide_raw[:200]})")
    else:
        try:
            data = json.loads(pide_raw[len("FINISHED"):].strip())
            printed = False
            for err in data.get("errors", []):
                if err.get("kind") == "error":
                    pos = err.get("pos", {})
                    print(f'  line {pos.get("line","?")}: {err.get("message","").splitlines()[0]}')
                    printed = True
            if not printed:
                for node in data.get("nodes", []):
                    if THEORY_NAME not in node.get("node_name", ""):
                        continue
                    for msg in node.get("messages", []):
                        if msg.get("kind") == "error":
                            pos = msg.get("pos", {})
                            print(f'  line {pos.get("line","?")}: {msg.get("message","").splitlines()[0]}')
                            printed = True
                    break
            if not printed:
                ok = data.get("ok", "?")
                print(f"  (no errors in response — ok={ok})")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  (JSON parse error: {e})")

    _banner("VERDICT")
    print(f"  Oracle error lines : {oracle_lines}")
    print(f"  PIDE error lines   : {pide_lines}")
    print()
    if oracle_lines and pide_lines and oracle_lines != pide_lines:
        print("  *** BUG REPRODUCED ***")
        print("  Both tools detect an error, but report DIFFERENT lines.")
        print("  Oracle sees 'Bad context for qed'; PIDE sees a syntax error one line earlier.")
    elif oracle_lines and not pide_lines:
        print("  *** BUG REPRODUCED (PIDE missed the error entirely) ***")
    elif oracle_lines == pide_lines:
        print("  No mismatch — both tools agree.")
    else:
        print("  Unexpected result — check output above.")

def _cleanup():
    """Kill any leftover polyml/bash_process workers from previous runs.

    These accumulate across runs and exhaust swap, causing the HOL session to
    be OOM-killed mid-load (connection closes with an empty readline).
    """
    import signal as _signal
    killed = 0
    for proc in subprocess.run(
        ["pgrep", "-x", "poly"], capture_output=True, text=True
    ).stdout.split():
        try:
            os.kill(int(proc), _signal.SIGKILL)
            killed += 1
        except (ProcessLookupError, ValueError):
            pass
    if killed:
        print(f"  [cleanup] Killed {killed} leftover polyml process(es).")
        import time; time.sleep(2)


def main():
    script_dir = Path(__file__).parent.absolute()
    theory_file = script_dir / f"{THEORY_NAME}.thy"

    print(f"\nWriting theory to: {theory_file}")
    theory_file.write_text(THEORY_CONTENT)

    print("Cleaning up leftover processes...")
    _cleanup()

    print("Starting Isabelle server (this takes ~30 s)...")
    host, port, password = start_isabelle_server()
    print(f"Server ready at {host}:{port}")

    print("\nStarting HOL session (this takes ~90-120 s on first run)...")

    import concurrent.futures
    run = 0
    try:
        while True:
            run += 1
            print(f"\nRun #{run} — running oracle and PIDE server (parallel)...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                oracle_fut = pool.submit(run_oracle, theory_file)
                pide_fut = pool.submit(run_pide, theory_file, host, port, password)
                oracle_output, oracle_lines = oracle_fut.result()
                pide_raw, pide_lines = pide_fut.result()

            _save_outputs(script_dir, oracle_output, pide_raw, run)
            _show_results(oracle_output, oracle_lines, pide_raw, pide_lines)

            print("\nPress Enter to run again, Ctrl+C to exit.")
            input()
    except KeyboardInterrupt:
        print("\nDone.")


if __name__ == "__main__":
    main()
