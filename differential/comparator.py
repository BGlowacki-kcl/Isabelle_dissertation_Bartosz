import json
from pathlib import Path
from oracle import _oracle_has_theory_error


def _extract_server_errors(server_json_str, theory_name="Test"):
    """Parse server JSON and return a list of (line, message_snippet) tuples for theory errors."""
    errors = []
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
        for msg in messages:
            if msg.get("kind") != "error":
                continue
            pos = msg.get("pos", {})
            fpath = pos.get("file", "")
            if fpath and thy_filename not in fpath:
                continue
            line = pos.get("line")
            text = msg.get("message", "")
            if line is not None:
                errors.append((int(line), text))

    if isinstance(server_data, dict):
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

            # Fallback: if the top-level errors list was empty but ok=false,
            # scan each node's messages (some Isabelle versions put errors there).
            if not errors and server_data.get("ok") is False:
                for node in server_data.get("nodes", []):
                    node_name = node.get("node_name", "")
                    if thy_filename not in node_name:
                        continue
                    if not node.get("status", {}).get("ok", True):
                        _collect_from_messages(node.get("messages", []))
                    break  # only care about the requested theory node

            if not errors and server_data.get("ok") is False:
                errors.append((None, "Server ok=false but no error details"))

        if not errors and "status" in server_data:
            if not server_data.get("status", {}).get("ok", True):
                _collect_from_messages(server_data.get("messages", []))

    elif isinstance(server_data, list):
        for node in server_data:
            node_name = node.get("node_name", "")
            status = node.get("status", {})
            if thy_filename not in node_name:
                continue
            if not status.get("ok", True):
                _collect_from_messages(node.get("messages", []))
            break

    return errors


def _dump_raw_outputs(server_json_str, oracle_text, worker_id):
    """Write raw server and oracle output to disk for debugging."""
    suffix = f"_{worker_id}" if worker_id is not None else ""
    base = Path(__file__).parent

    with open(base / f"oracle_output{suffix}.txt", "w", encoding="utf-8") as f:
        f.write(oracle_text)
    with open(base / f"server_output{suffix}.txt", "w", encoding="utf-8") as f:
        f.write(server_json_str)


def compare_outputs(server_json_str, oracle_text, theory_name="Test", worker_id=None):
    """Return (mismatch, reason, oracle_pass, server_pass, comparison_detail)."""
    print(f"--- COMPARISON REPORT (worker {worker_id}) ---\n")
    mismatch_reasons = []

    if server_json_str is None:
        server_json_str = ""
    if oracle_text is None:
        oracle_text = ""
    if isinstance(server_json_str, bytes):
        server_json_str = server_json_str.decode('utf-8', errors='replace')
    if isinstance(oracle_text, bytes):
        oracle_text = oracle_text.decode('utf-8', errors='replace')

    _dump_raw_outputs(server_json_str, oracle_text, worker_id)

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

    oracle_has_error, oracle_lines = _oracle_has_theory_error(oracle_text, theory_name)

    detail = {
        "server_error_lines": server_lines,
        "server_errors": [(l, m[:120]) for l, m in server_errors],
        "oracle_error_lines": oracle_lines,
        "oracle_pass": not oracle_has_error,
        "server_pass": not server_has_error,
    }

    if not server_has_error and not oracle_has_error:
        print("[MATCH] Both Server and Oracle: PASS (no errors in theory).")
        return False, "", True, True, detail

    if server_has_error and oracle_has_error:
        if server_lines == oracle_lines:
            print(f"[MATCH] Both failed at the same lines ({oracle_lines}). No bug.")
            return False, "", False, False, detail

        oracle_set = set(oracle_lines)
        server_set = set(server_lines)
        only_oracle = sorted(oracle_set - server_set)
        only_server = sorted(server_set - oracle_set)

        if only_oracle:
            parts = [f"Oracle-only errors: {only_oracle}"]
            if only_server:
                parts.append(f"Server-only extras: {only_server}")
            reason = "Server missed oracle errors. " + "; ".join(parts)
            print(f"[FAIL] {reason}")
            mismatch_reasons.append(reason)
            return True, "\n".join(mismatch_reasons), False, False, detail

        reason = (
            f"Server more verbose: oracle errors {oracle_lines} ⊆ server errors "
            f"{server_lines} (extra server-only: {only_server})."
        )
        print(f"[INFO] {reason}")
        return False, reason, False, False, detail

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

    reason = (
        f"Oracle detected proof failures at lines {oracle_lines} in Test.thy, "
        f"but Server reported no errors."
    )
    print(f"[FAIL] {reason}")
    mismatch_reasons.append(reason)
    return True, "\n".join(mismatch_reasons), False, True, detail
