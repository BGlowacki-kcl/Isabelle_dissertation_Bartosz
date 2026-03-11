import json
from pathlib import Path
import re
import subprocess

def start_isabelle_server():    
    subprocess.run(["isabelle", "server", "-x"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    process = subprocess.Popen(
        ["isabelle", "server"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    while True:
        line = process.stdout.readline()
        if not line:
            break
        
        match = re.search(r'server "isabelle" = ([0-9.]+):(\d+) \(password "([^"]+)"\)', line)
        if match:
            host, port, password = match.group(1), int(match.group(2)), match.group(3)
            print(f"Found Server: {host}:{port}")
            return host, port, password
            
        if process.poll() is not None:
             break

    raise RuntimeError("Failed to parse Isabelle server output or server exited unexpectedly")


def read_until_finished(sock_file):
    """Reads lines from the socket until FINISHED or FAILED is encountered."""
    while True:
        line = sock_file.readline()
        if not line:
            break
        
        line = line.strip()
        # print(f"[Server] {line}")
        
        if line.startswith("FINISHED"):
            return line
        if line.startswith("FAILED"):
            return None
    return None

def _oracle_has_theory_error(output_text, theory_name):
    """
    Returns (has_error, sorted_list_of_error_line_numbers) by scanning for
    proof/command failures in the user's own theory file.
    Lines like:
      *** At command "by" (line 42 of "~/.../.../Test.thy")
      *** Failed to finish proof (line 58 of "~/.../.../Test.thy"):
    are real errors.  Internal Isabelle noise like Bad bash_process server
    address refers to library files and is ignored.
    """
    # Two patterns that reference the user's theory file by stem name.
    # 1) "At command ... (line N of "...Test.thy")"
    # 2) "Failed to finish proof (line N of "...Test.thy"):"
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


def run_oracle(theory_arg, timeout=500, worker_id=None):
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

        # Determine pass/fail by looking for errors in the user's theory file,
        # not by exit code (exit code can be non-zero due to library noise).
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

def _extract_server_errors(server_json_str, theory_name="Test"):
    """
    Parse the server JSON and return a list of (line, message_snippet) tuples
    for every error in the user's theory file.  Ignores errors from library files.
    Works with:
      Format A (use_theories):  list of node objects [{node_name, status, messages}, ...]
      Format B (simpler):       single object {ok, errors: [{kind, message, pos}, ...]}
    """
    errors = []   # list of (line_int, msg_str)
    thy_filename = f"{theory_name}.thy"

    json_start_index = server_json_str.find('[')
    brace_start = server_json_str.find('{')
    if json_start_index != -1 and (brace_start == -1 or json_start_index < brace_start):
        parsed_str = server_json_str[json_start_index:]
    elif brace_start != -1:
        parsed_str = server_json_str[brace_start:]
    else:
        parsed_str = ""

    server_data = json.loads(parsed_str) if parsed_str.strip() else {}

    def _collect_from_messages(messages):
        """Collect (line, msg) from a list of message objects where kind==error
        and the file is the user's theory (or no file specified)."""
        for msg in messages:
            if msg.get("kind") != "error":
                continue
            pos = msg.get("pos", {})
            fpath = pos.get("file", "")
            # Only keep errors in the user's theory file (path ends with the
            # theory filename or is empty).
            if fpath and thy_filename not in fpath:
                continue
            line = pos.get("line")
            text = msg.get("message", "")
            if line is not None:
                errors.append((int(line), text))

    if isinstance(server_data, dict):
        # Format B: {ok: bool, errors: [...]}
        if server_data.get("ok") is False or server_data.get("errors"):
            err_list = server_data.get("errors", [])
            for err in err_list:
                if err.get("kind") != "error":
                    continue
                pos = err.get("pos", {})
                fpath = pos.get("file", "")
                if fpath and thy_filename not in fpath:
                    continue
                line = pos.get("line")
                text = err.get("message", "")
                if line is not None:
                    errors.append((int(line), text))
            # If ok=False but no parseable error entries, flag a generic error
            if not errors and server_data.get("ok") is False:
                errors.append((None, "Server ok=false but no error details"))
        # Format A: single node object with "status" and "messages"
        if not errors and "status" in server_data:
            if not server_data.get("status", {}).get("ok", True):
                _collect_from_messages(server_data.get("messages", []))

    elif isinstance(server_data, list):
        # Format A: list of node objects
        for node in server_data:
            node_name = node.get("node_name", "")
            status = node.get("status", {})
            if thy_filename not in node_name:
                continue
            if not status.get("ok", True):
                _collect_from_messages(node.get("messages", []))
            break

    return errors


def compare_outputs(server_json_str, oracle_text, theory_name="Test", worker_id=None):
    """
    Returns (mismatch, reason, oracle_pass, server_pass, comparison_detail).

    comparison_detail is a dict with:
        server_error_lines : list[int]          – sorted error lines from server
        server_errors      : list[(int, str)]   – (line, message_snippet) tuples
        oracle_error_lines : list[int]          – sorted error lines from oracle
        oracle_pass        : bool
        server_pass        : bool
    """
    print(f"--- COMPARISON REPORT (worker {worker_id}) ---\n")
    mismatch_reasons = []

    # Ensure inputs are strings
    if server_json_str is None:
        server_json_str = ""
    if oracle_text is None:
        oracle_text = ""
    if isinstance(server_json_str, bytes):
        server_json_str = server_json_str.decode('utf-8', errors='replace')
    if isinstance(oracle_text, bytes):
        oracle_text = oracle_text.decode('utf-8', errors='replace')

    suffix = f"_{worker_id}" if worker_id is not None else ""
    output_path = Path(__file__).parent / f"oracle_output{suffix}.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(oracle_text)

    output_path = Path(__file__).parent / f"server_output{suffix}.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(server_json_str)

    # ---------------------------------------------------------
    # 1. Extract Server Errors (all error lines in the worker's theory)
    # ---------------------------------------------------------
    try:
        server_errors = _extract_server_errors(server_json_str, theory_name)
    except json.JSONDecodeError:
        reason = "Server returned invalid/unparseable JSON."
        print(f"[!] Error: {reason}")
        mismatch_reasons.append(reason)
        detail = {"server_error_lines": [], "server_errors": [],
                  "oracle_error_lines": [], "oracle_pass": True, "server_pass": False}
        return True, "\n".join(mismatch_reasons), True, False, detail

    server_lines = sorted({line for line, _ in server_errors if line is not None})
    server_has_error = bool(server_errors)

    # ---------------------------------------------------------
    # 2. Extract Oracle Errors (all error lines in the worker's theory)
    #    Library noise (Bad bash_process, Multiset.thy, etc.) is ignored.
    # ---------------------------------------------------------
    oracle_has_error, oracle_lines = _oracle_has_theory_error(oracle_text, theory_name)

    # Build the comparison detail dict (always returned)
    detail = {
        "server_error_lines": server_lines,
        "server_errors": [(l, m[:120]) for l, m in server_errors],
        "oracle_error_lines": oracle_lines,
        "oracle_pass": not oracle_has_error,
        "server_pass": not server_has_error,
    }

    # ---------------------------------------------------------
    # 3. High-Level Outcome Comparison
    # ---------------------------------------------------------
    if not server_has_error and not oracle_has_error:
        print("[MATCH] Both Server and Oracle: PASS (no errors in theory).")
        return False, "", True, True, detail

    if server_has_error and oracle_has_error:
        # Both failed — check if they agree on the same set of error lines
        if server_lines == oracle_lines:
            print(f"[MATCH] Both failed at the same lines ({oracle_lines}). No bug.")
            return False, "", False, False, detail
        else:
            # Check if one is a subset of the other — partial match
            common = sorted(set(server_lines) & set(oracle_lines))
            only_server = sorted(set(server_lines) - set(oracle_lines))
            only_oracle = sorted(set(oracle_lines) - set(server_lines))
            if only_server or only_oracle:
                parts = []
                if common:
                    parts.append(f"Common error lines: {common}")
                if only_server:
                    parts.append(f"Only in Server: {only_server}")
                if only_oracle:
                    parts.append(f"Only in Oracle: {only_oracle}")
                reason = "Both detected errors but at different lines. " + "; ".join(parts)
            else:
                reason = (
                    f"Both detected errors but at different lines: "
                    f"Oracle={oracle_lines}, Server={server_lines}."
                )
            print(f"[FAIL] {reason}")
            mismatch_reasons.append(reason)
            return True, "\n".join(mismatch_reasons), False, False, detail

    if server_has_error and not oracle_has_error:
        s_msg_preview = ""
        if server_errors:
            s_msg_preview = server_errors[0][1][:80] if server_errors[0][1] else ""
        reason = (
            f"Server reported errors at lines {server_lines} ({s_msg_preview!r}), "
            f"but Oracle found no error in Test.thy."
        )
        print(f"[FAIL] {reason}")
        mismatch_reasons.append(reason)
        return True, "\n".join(mismatch_reasons), True, False, detail

    # oracle_has_error and not server_has_error
    reason = (
        f"Oracle detected proof failures at lines {oracle_lines} in Test.thy, "
        f"but Server reported no errors."
    )
    print(f"[FAIL] {reason}")
    mismatch_reasons.append(reason)
    return True, "\n".join(mismatch_reasons), False, True, detail

