import re
import subprocess


def start_isabelle_server():
    """Kill any existing server, start a fresh one, return (host, port, password)."""
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
    """Read lines from the socket until FINISHED or FAILED is encountered."""
    while True:
        line = sock_file.readline()
        if not line:
            break

        line = line.strip()

        if line.startswith("FINISHED"):
            return line
        if line.startswith("FAILED"):
            return None
    return None


def read_until_ok(sock_file):
    """Read lines from the socket until OK or an error response is encountered."""
    while True:
        line = sock_file.readline()
        if not line:
            break

        line = line.strip()

        if line.startswith("OK"):
            return line
        if line.startswith("ERROR") or line.startswith("FAILED"):
            return None
    return None
