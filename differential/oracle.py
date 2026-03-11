import re
import subprocess
from pathlib import Path
from const import ORACLE_TIMEOUT


def _oracle_has_theory_error(output_text, theory_name):
    """Return (has_error, sorted_error_line_numbers) for the user's theory file."""
    at_cmd = re.compile(
        r'At command[^\n]+\(line (\d+) of "[^"]*' + re.escape(theory_name) + r'\.thy"\)',
        re.IGNORECASE
    )
    failed_proof = re.compile(
        r'Failed to finish proof[^\n]*\(line (\d+) of "[^"]*' + re.escape(theory_name) + r'\.thy"\)',
        re.IGNORECASE
    )
    lines = set()
    for m in at_cmd.finditer(output_text):
        lines.add(int(m.group(1)))
    for m in failed_proof.finditer(output_text):
        lines.add(int(m.group(1)))
    return bool(lines), sorted(lines)


def run_oracle(theory_arg, timeout=ORACLE_TIMEOUT, worker_id=None):
    """Run `isabelle process` on a theory file and return (passed, output_text)."""
    theory_name = Path(theory_arg).stem

    cmd = [
        "isabelle", "process",
        "-e", f'use_thy "{theory_name}"'
    ]

    script_dir = Path(__file__).parent.absolute()

    try:
        print(f"[Worker-{worker_id}] Oracle: Processing theory '{theory_name}' in {script_dir}...")

        result = subprocess.run(
            cmd,
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        output = result.stdout if result.stdout else result.stderr
        has_error, _ = _oracle_has_theory_error(output, theory_name)

        if has_error:
            print(f"[Worker-{worker_id}] Oracle: Proof/command failure detected in {theory_name}.thy")
            return False, output

        print(f"[Worker-{worker_id}] Oracle Success")
        return True, output

    except subprocess.TimeoutExpired as e:
        print(f"[Worker-{worker_id}] Oracle Timed Out after {timeout}s!")
        output = e.stdout if e.stdout else (e.stderr if e.stderr else "")
        return False, output
    except Exception as e:
        print(f"[Worker-{worker_id}] Unexpected Python Error: {e}")
        return False, ""
