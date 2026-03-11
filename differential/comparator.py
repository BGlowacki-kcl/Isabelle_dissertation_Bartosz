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

    reason = (
        f"Oracle detected proof failures at lines {oracle_lines} in Test.thy, "
        f"but Server reported no errors."
    )
    print(f"[FAIL] {reason}")
    mismatch_reasons.append(reason)
    return True, "\n".join(mismatch_reasons), False, True, detail
