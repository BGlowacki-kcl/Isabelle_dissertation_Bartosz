from pathlib import Path


THEORY_NAME = "Test"
THEORY_FILE = "Test.thy"
MUTATIONS_LOG = "mutations.txt"
INPUT_DIR = "input"
MUTATIONS_PER_FILE = 10
NUM_WORKERS = 1
ORACLE_TIMEOUT = 900
SERVER_TIMEOUT = 1200
ORACLE_PARENT = "HOL-Combinatorics"
SESSION_NAME = "HOL"
REPORT_DIR = Path("bug_reports")
REPORT_DIR.mkdir(exist_ok=True)
NO_BUG_DIR = Path("no_bug")
NO_BUG_DIR.mkdir(exist_ok=True)