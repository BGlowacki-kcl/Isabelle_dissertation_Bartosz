import os
import re
import shutil
import signal
import subprocess
from pathlib import Path

from const import ORACLE_TIMEOUT, ORACLE_PARENT

ISABELLE = "isabelle"


def _oracle_has_theory_error(output_text, theory_name):
    """Return (has_error, sorted_error_line_numbers) for the user's theory file."""
    at_cmd = re.compile(
        r'At command[^\n]+\(line (\d+) of "[^"]*' + re.escape(theory_name) + r'\.thy"\)',
        re.IGNORECASE,
    )
    failed_proof = re.compile(
        r'Failed to finish proof[^\n]*\(line (\d+) of "[^"]*' + re.escape(theory_name) + r'\.thy"\)',
        re.IGNORECASE,
    )
    lines = set()
    for m in at_cmd.finditer(output_text):
        lines.add(int(m.group(1)))
    for m in failed_proof.finditer(output_text):
        lines.add(int(m.group(1)))
    return bool(lines), sorted(lines)


def _extract_session_imports(theory_file: Path) -> list:
    """Return the Isabelle session names required by the theory's imports."""
    try:
        content = theory_file.read_text(encoding="utf-8")
    except OSError:
        return []

    imports_match = re.search(
        r"\bimports\b(.*?)\bbegin\b", content, re.DOTALL | re.IGNORECASE
    )
    if not imports_match:
        return []

    sessions = []
    for imp in re.findall(r'"([^"]+)"', imports_match.group(1)):
        dot = imp.find(".")
        if dot > 0:
            prefix = imp[:dot]
            if not prefix.startswith("~"):   # skip ~~-paths
                sessions.append(prefix)

    seen = set()
    result = []
    for s in sessions:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def run_oracle(theory_arg, timeout=ORACLE_TIMEOUT, worker_id=None):
    theory_name = Path(theory_arg).stem          # e.g. "Test_0"
    script_dir  = Path(__file__).parent.absolute()
    theory_file = script_dir / f"{theory_name}.thy"

    # Per-worker directory persists between runs so dep heaps are cached.
    oracle_dir   = script_dir / f".oracle_{worker_id}"
    oracle_dir.mkdir(exist_ok=True)
    session_name = f"OracleSession_{worker_id}"

    dest_theory = oracle_dir / f"{theory_name}.thy"
    shutil.copy2(str(theory_file), str(dest_theory))

    required_sessions = [
        s for s in _extract_session_imports(dest_theory)
        if s != ORACLE_PARENT
    ]
    sessions_clause = ""
    if required_sessions:
        sessions_clause = (
            "  sessions\n"
            + "".join(f'    "{s}"\n' for s in required_sessions)
        )

    root_content = (
        f'session "{session_name}" = "{ORACLE_PARENT}" +\n'
        + "  options [quick_and_dirty = false]\n"
        + sessions_clause
        + "  theories\n"
        + f'    "{theory_name}"\n'
    )
    (oracle_dir / "ROOT").write_text(root_content)

    cmd = [ISABELLE, "build", "-v", "-d", str(oracle_dir), session_name]

    print(f"[Worker-{worker_id}] Oracle: isabelle build '{theory_name}'...")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid,
        )
        try:
            stdout_data, stderr_data = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout_data, stderr_data = proc.communicate()
            output = (stdout_data or "") + (stderr_data or "")
            print(f"[Worker-{worker_id}] Oracle Timed Out after {timeout}s!")
            return False, output

        output = (stdout_data or "") + (stderr_data or "")

        has_error, _ = _oracle_has_theory_error(output, theory_name)

        if not has_error and proc.returncode != 0:
            has_error = True

        if has_error:
            print(
                f"[Worker-{worker_id}] Oracle: "
                f"Proof/command failure detected in {theory_name}.thy"
            )
            return False, output

        print(f"[Worker-{worker_id}] Oracle Success")
        return True, output

    except Exception as e:
        print(f"[Worker-{worker_id}] Unexpected Python Error: {e}")
        return False, ""
