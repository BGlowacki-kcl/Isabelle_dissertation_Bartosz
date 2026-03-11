import sys
import os
import time
import socket
import re
import concurrent.futures
from const import NUM_WORKERS, MUTATIONS_PER_FILE, SESSION_NAME
from server import start_isabelle_server, read_until_finished, read_until_ok
from oracle import run_oracle
from comparator import compare_outputs
from reporter import save_report, save_match_log
from mutator import load_new_theory, mutate, theory_name_for


def one_test(host, port, password, worker_id=0):
    """Run a single fuzzing worker in a loop."""
    theory_name = theory_name_for(worker_id)
    thy_file = f"{theory_name}.thy"

    sock = socket.create_connection((host, port))
    f = sock.makefile('rw', buffering=1)

    f.write(f"{password}\n")
    handshake = f.readline().strip()

    if not handshake or not handshake.startswith("OK"):
        print(f"[Worker-{worker_id}] Connection failed: {handshake}")
        return

    print(f"[Worker-{worker_id}] Connected to Isabelle Server.")

    try:
        f.write(f'session_start {{"session": "{SESSION_NAME}"}}\n')

        finished_line = read_until_finished(f)
        if not finished_line:
            print(f"[Worker-{worker_id}] Session start failed.")
            return

        match = re.search(r'"session_id"\s*:\s*"([^"]+)"', finished_line)
        if not match:
            print(f"[Worker-{worker_id}] Could not find session_id in output.")
            return

        session_id = match.group(1)
        print(f"[Worker-{worker_id}] Session started. ID: {session_id}")

        iteration = 0
        current_dir = os.path.abspath(".")

        while True:
            load_new_theory(worker_id)

            for mutation_num in range(MUTATIONS_PER_FILE):
                if mutation_num > 0:
                    mutate(worker_id)

                print(f"\n[Worker-{worker_id}] --- mutation {mutation_num+1}/{MUTATIONS_PER_FILE}, iteration {iteration} ---")
                iteration += 1

                use_cmd = f'use_theories {{"session_id": "{session_id}", "theories": ["{theory_name}"], "master_dir": "{current_dir}"}}'

                purge_cmd = f'purge_theories {{"session_id": "{session_id}", "theories": ["{theory_name}"], "master_dir": "{current_dir}", "all": true}}'
                f.write(f"{purge_cmd}\n")
                read_until_ok(f)

                print(f"[Worker-{worker_id}] Processing theories...")
                f.write(f"{use_cmd}\n")
                line_server = read_until_finished(f)

                _, line_oracle = run_oracle(thy_file, worker_id=worker_id)
                time.sleep(2)

                if line_server is not None or line_oracle is not None:
                    mismatch, mismatch_reason, oracle_pass, server_pass, comp_detail = compare_outputs(
                        line_server, line_oracle, theory_name=theory_name, worker_id=worker_id
                    )
                    print(f"[Worker-{worker_id}] Comparison complete.")

                    oracle_res = (oracle_pass, line_oracle or "")
                    server_res = (server_pass, line_server or "")

                    if mismatch:
                        with open(thy_file, "r") as thy:
                            content = thy.read()
                        save_report(iteration, content, oracle_res, server_res, mismatch_reason, comp_detail, worker_id=worker_id)
                    else:
                        save_match_log(iteration, oracle_res, server_res, comp_detail, worker_id=worker_id)

    except KeyboardInterrupt:
        print(f"\n[Worker-{worker_id}] Stopped by user.")
    except Exception as e:
        print(f"[Worker-{worker_id}] Error: {e}")
    finally:
        try:
            f.write(f'session_stop {{"session_id": "{session_id}"}}\n')
            sock.close()
        except Exception:
            pass


if __name__ == "__main__":
    num_workers = int(sys.argv[1]) if len(sys.argv) > 1 else NUM_WORKERS
    host, port, password = start_isabelle_server()

    print(f"[Main] Starting {num_workers} parallel fuzzing workers...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(one_test, host, port, password, worker_id=i): i
            for i in range(num_workers)
        }
        try:
            for future in concurrent.futures.as_completed(futures):
                wid = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    print(f"[Main] Worker {wid} raised: {exc}")
        except KeyboardInterrupt:
            print("\n[Main] Ctrl+C received — shutting down workers...")
