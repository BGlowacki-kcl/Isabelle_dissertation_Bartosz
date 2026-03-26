import sys
import os
import time
import socket
import re
import threading
import concurrent.futures
from const import NUM_WORKERS, MUTATIONS_PER_FILE, SESSION_NAME, SERVER_TIMEOUT
from server import start_isabelle_server, read_until_finished
from oracle import run_oracle
from comparator import compare_outputs
from reporter import save_report, save_match_log
from mutator import load_new_theory, mutate, theory_name_for

_server_lock = threading.Lock()
_server_state = {"host": None, "port": None, "password": None}


def _cleanup_processes():
    import signal as _signal
    killed = 0
    result = __import__("subprocess").run(
        ["pgrep", "-x", "poly"], capture_output=True, text=True
    )
    for pid in result.stdout.split():
        try:
            os.kill(int(pid), _signal.SIGKILL)
            killed += 1
        except (ProcessLookupError, ValueError):
            pass
    if killed:
        print(f"[Main] Killed {killed} leftover polyml process(es) — freeing memory.")
        time.sleep(2)


def _restart_server(worker_id, known_port):
    with _server_lock:
        if _server_state["port"] != known_port:
            print(f"[Worker-{worker_id}] Server already restarted by another worker "
                  f"(port {known_port} → {_server_state['port']}). Adopting new state.")
            return _server_state["host"], _server_state["port"], _server_state["password"]

        print(f"[Worker-{worker_id}] Restarting Isabelle server …")
        try:
            host, port, password = start_isabelle_server()
            _server_state["host"] = host
            _server_state["port"] = port
            _server_state["password"] = password
            print(f"[Worker-{worker_id}] Server restarted at {host}:{port}")
            return host, port, password
        except Exception as e:
            print(f"[Worker-{worker_id}] Server restart failed: {e}")
            raise


def _connect(host, port, password, worker_id):
    """Open a socket to the server and authenticate; return (sock, file)."""
    sock = socket.create_connection((host, port))
    sock.settimeout(SERVER_TIMEOUT)
    f = sock.makefile("rw", buffering=1)
    f.write(f"{password}\n")
    handshake = f.readline().strip()
    if not handshake or not handshake.startswith("OK"):
        sock.close()
        raise ConnectionError(f"Handshake failed: {handshake!r}")
    print(f"[Worker-{worker_id}] Connected to Isabelle Server.")
    return sock, f


def _start_session(f, worker_id):
    """Send session_start and return the session_id string."""
    f.write(f'session_start {{"session": "{SESSION_NAME}"}}\n')
    finished = read_until_finished(f)
    if not finished:
        raise ConnectionError("session_start returned no FINISHED line.")
    m = re.search(r'"session_id"\s*:\s*"([^"]+)"', finished)
    if not m:
        raise ConnectionError("Could not find session_id in session_start reply.")
    sid = m.group(1)
    print(f"[Worker-{worker_id}] Session started. ID: {sid}")
    return sid


def one_test(host, port, password, worker_id=0):
    """Run a single fuzzing worker.  Reconnects and restarts server automatically on errors."""
    theory_name = theory_name_for(worker_id)
    thy_file    = f"{theory_name}.thy"
    current_dir = os.path.abspath(".")

    iteration = 0
    consecutive_failures = 0
    MAX_FAILURES_BEFORE_RESTART = 5

    while True:
        sock = None
        f    = None
        session_id = None

        if consecutive_failures >= MAX_FAILURES_BEFORE_RESTART:
            try:
                host, port, password = _restart_server(worker_id, known_port=port)
                consecutive_failures = 0
            except Exception:
                time.sleep(10)
                continue

        try:
            sock, f = _connect(host, port, password, worker_id)
            consecutive_failures = 0   # reset on successful connect

            while True:
                load_new_theory(worker_id)
                with open(thy_file, "r") as _fh:
                    _base_content = _fh.read()
                session_id = _start_session(f, worker_id)

                for mutation_num in range(MUTATIONS_PER_FILE):
                    if mutation_num > 0:
                        with open(thy_file, "w") as _fh:
                            _fh.write(_base_content)
                        mutate(worker_id)

                    print(
                        f"\n[Worker-{worker_id}] "
                        f"--- mutation {mutation_num + 1}/{MUTATIONS_PER_FILE},"
                        f" iteration {iteration} ---"
                    )
                    iteration += 1

                    use_cmd = (
                        f'use_theories {{"session_id": "{session_id}",'
                        f' "theories": ["{theory_name}"],'
                        f' "master_dir": "{current_dir}"}}'
                    )

                    print(f"[Worker-{worker_id}] Processing theories...")
                    f.write(f"{use_cmd}\n")

                    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                        server_future = pool.submit(read_until_finished, f)
                        oracle_future = pool.submit(
                            run_oracle, thy_file, worker_id=worker_id
                        )
                        try:
                            line_server = server_future.result(timeout=SERVER_TIMEOUT)
                        except concurrent.futures.TimeoutError:
                            print(
                                f"[Worker-{worker_id}] Server use_theories timed out "
                                f"after {SERVER_TIMEOUT}s — closing connection."
                            )
                            sock.close()   # interrupt the background read thread
                            _, line_oracle = oracle_future.result()
                            raise ConnectionError(
                                f"Server timed out after {SERVER_TIMEOUT}s"
                            )
                        _, line_oracle = oracle_future.result()

                    if line_server is None:
                        raise ConnectionError("use_theories returned FAILED or connection lost.")

                    time.sleep(2)

                    mismatch, mismatch_reason, oracle_pass, server_pass, comp_detail = (
                        compare_outputs(
                            line_server, line_oracle,
                            theory_name=theory_name,
                            worker_id=worker_id,
                        )
                    )
                    print(f"[Worker-{worker_id}] Comparison complete.")

                    oracle_res = (oracle_pass, line_oracle or "")
                    server_res = (server_pass, line_server or "")

                    if mismatch:
                        with open(thy_file, "r") as thy:
                            content = thy.read()
                        save_report(
                            iteration, content,
                            oracle_res, server_res,
                            mismatch_reason, comp_detail,
                            worker_id=worker_id,
                        )
                    else:
                        save_match_log(
                            iteration, oracle_res, server_res, comp_detail,
                            worker_id=worker_id,
                            info_reason=mismatch_reason,
                        )

                try:
                    f.write(f'session_stop {{"session_id": "{session_id}"}}\n')
                    read_until_finished(f)
                except Exception:
                    pass
                session_id = None

        except KeyboardInterrupt:
            print(f"\n[Worker-{worker_id}] Stopped by user.")
            return

        except (OSError, ConnectionError, BrokenPipeError) as e:
            consecutive_failures += 1
            print(f"[Worker-{worker_id}] Connection error: {e} — reconnecting in 5 s …"
                  f" ({consecutive_failures}/{MAX_FAILURES_BEFORE_RESTART})")
            time.sleep(5)

        except Exception as e:
            consecutive_failures += 1
            print(f"[Worker-{worker_id}] Unexpected error: {e} — reconnecting in 5 s …")
            time.sleep(5)

        finally:
            if session_id and f:
                try:
                    f.write(f'session_stop {{"session_id": "{session_id}"}}\n')
                except Exception:
                    pass
            if f:
                try:
                    f.close()
                except Exception:
                    pass
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass


if __name__ == "__main__":
    num_workers = int(sys.argv[1]) if len(sys.argv) > 1 else NUM_WORKERS
    _cleanup_processes()
    host, port, password = start_isabelle_server()
    _server_state["host"] = host
    _server_state["port"] = port
    _server_state["password"] = password

    print(f"[Main] Starting {num_workers} parallel fuzzing workers…")

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
            print("\n[Main] Ctrl+C received — shutting down workers…")
