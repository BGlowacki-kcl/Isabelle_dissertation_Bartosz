import os
import time
import threading
from const import REPORT_DIR, NO_BUG_DIR
from mutator import _mutations_log_for

_report_lock = threading.Lock()


def _result_label(passed):
    """Format a pass/fail label for reports."""
    return "PASS (no error)" if passed else "FAIL (error detected)"


def _write_comp_detail(f, comp_detail):
    """Write the comparison detail block into an open file handle."""
    if not comp_detail:
        f.write("(no comparison detail available)\n")
        return
    f.write(f"Oracle error lines extracted: {comp_detail['oracle_error_lines']}\n")
    f.write(f"Server error lines extracted: {comp_detail['server_error_lines']}\n")
    if comp_detail['server_errors']:
        f.write("\nServer errors (line -> message snippet):\n")
        for line_no, msg in comp_detail['server_errors']:
            f.write(f"  line {line_no}: {msg}\n")


def save_report(iteration, content, oracle_res, server_res,
                mismatch_reason="", comp_detail=None, worker_id=None):
    """Save a mismatch / crash report to disk."""
    timestamp = int(time.time())
    base_name = REPORT_DIR / f"mismatch_iter{iteration}_{timestamp}_w{worker_id}"

    print(f"\n[Worker-{worker_id}] Saving Crash/Mismatch Report to {base_name}...")

    with _report_lock:
        with open(f"{base_name}.thy", "w") as f:
            f.write(content)

        with open(f"{base_name}.info", "w") as f:
            f.write(f"Iteration: {iteration}\n")
            f.write(f"Worker: {worker_id}\n")
            f.write(f"Oracle Result: {_result_label(oracle_res[0])}\n")
            f.write(f"Server Result: {_result_label(server_res[0])}\n")

            f.write("\n" + "="*20 + " COMPARED DATA " + "="*20 + "\n")
            _write_comp_detail(f, comp_detail)

            f.write("\n" + "="*20 + " MISMATCH DETAIL " + "="*20 + "\n")
            if mismatch_reason:
                f.write(mismatch_reason + "\n")
            else:
                f.write("Oracle and Server disagree on the outcome.\n")
            f.write("\n" + "="*20 + " ORACLE LOGS " + "="*20 + "\n")
            f.write(oracle_res[1])
            f.write("\n" + "="*20 + " SERVER LOGS " + "="*20 + "\n")
            f.write(server_res[1])

        mutations_log = _mutations_log_for(worker_id)
        if os.path.exists(mutations_log):
            with open(mutations_log, "r") as f:
                mutations_content = f.read()
            with open(f"{base_name}.mutations.txt", "w") as f:
                f.write(mutations_content)


def save_match_log(iteration, oracle_res, server_res,
                   comp_detail=None, worker_id=None):
    """Save a match (no bug) log to disk."""
    timestamp = int(time.time())
    log_path = NO_BUG_DIR / f"match_iter{iteration}_{timestamp}_w{worker_id}.txt"

    print(f"[Worker-{worker_id}] Match found! Saving overview to {log_path}...")

    with _report_lock:
        with open(log_path, "w") as f:
            f.write(f"Iteration: {iteration}\n")
            f.write(f"Worker: {worker_id}\n")
            f.write("Status: MATCH (No Bug)\n")
            f.write("="*40 + "\n")

            f.write("=== HIGH-LEVEL OVERVIEW ===\n")
            f.write(f"Oracle Result: {_result_label(oracle_res[0])}\n")
            f.write(f"Server Result: {_result_label(server_res[0])}\n\n")

            f.write("=== COMPARED DATA ===\n")
            _write_comp_detail(f, comp_detail)
            f.write("\n")

            f.write("=== MATCHED OUTPUTS ===\n")
            f.write("Both Oracle and Server agreed on the outcome.\n\n")
            f.write("--- Server Output ---\n")
            f.write(server_res[1])
            f.write("\n--- Oracle Output ---\n")
            f.write(oracle_res[1])
            f.write("\n" + "-"*40 + "\n")
