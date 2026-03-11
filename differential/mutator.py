import os
import random
import glob
import re
from const import THEORY_NAME, THEORY_FILE, MUTATIONS_LOG, INPUT_DIR
from mutations import ALL_MUTATIONS


def _theory_file_for(worker_id=None):
    """Return the theory filename for a given worker."""
    if worker_id is None:
        return THEORY_FILE
    return f"Test_{worker_id}.thy"


def _mutations_log_for(worker_id=None):
    """Return the mutations-log filename for a given worker."""
    if worker_id is None:
        return MUTATIONS_LOG
    return f"mutations_{worker_id}.txt"


def theory_name_for(worker_id=None):
    """Return the bare theory name (without .thy) for a given worker."""
    if worker_id is None:
        return THEORY_NAME
    return f"Test_{worker_id}"


def _mutate_content(content):
    """Apply a random mutation to the theory content, protecting the header and footer."""
    lines = content.splitlines(keepends=True)

    begin_idx = -1
    end_idx = len(lines)

    for i, line in enumerate(lines):
        if re.search(r'\bbegin\b', line):
            begin_idx = i
            break

    for i in range(len(lines) - 1, -1, -1):
        if re.search(r'\bend\b', lines[i]):
            end_idx = i
            break

    if begin_idx == -1 or end_idx == len(lines) or begin_idx >= end_idx - 1:
        return content, "No-op (could not find valid 'begin' and 'end' boundaries)"

    protected_top = lines[:begin_idx + 1]
    mutable_middle = lines[begin_idx + 1:end_idx]
    protected_bottom = lines[end_idx:]

    if not mutable_middle:
        return content, "No-op (no mutable lines available)"

    mutable_middle_string = "".join(mutable_middle)
    mutation_fn = random.choice(ALL_MUTATIONS)
    mutated_middle_string, description = mutation_fn(mutable_middle_string)

    final_content = "".join(protected_top) + mutated_middle_string + "".join(protected_bottom)
    return final_content, description


def load_new_theory(worker_id=None):
    """Pick a random .thy file from input/, copy it to Test[_N].thy, clear mutations log."""
    thy_files = glob.glob(os.path.join(INPUT_DIR, "*.thy"))
    if not thy_files:
        raise FileNotFoundError(f"No .thy files found in '{INPUT_DIR}/'")

    chosen = random.choice(thy_files)
    with open(chosen, "r") as f:
        content = f.read()

    t_name = theory_name_for(worker_id)
    t_file = _theory_file_for(worker_id)
    m_log  = _mutations_log_for(worker_id)

    content = re.sub(r'\btheory\s+\S+', f'theory {t_name}', content, count=1)

    with open(t_file, "w") as f:
        f.write(content)

    with open(m_log, "w") as f:
        f.write(f"Source file: {chosen}\n")
        f.write("="*40 + "\n")
        f.write(content)
        f.write("\n" + "="*40 + "\n")
        f.write("Mutations applied:\n")

    print(f"[Mutator-{worker_id}] Loaded: {chosen}")
    return chosen


def mutate(worker_id=None):
    """Apply one random mutation to Test[_N].thy in-place and log it."""
    t_file = _theory_file_for(worker_id)
    m_log  = _mutations_log_for(worker_id)

    with open(t_file, "r") as f:
        content = f.read()

    mutated, description = _mutate_content(content)

    with open(t_file, "w") as f:
        f.write(mutated)

    with open(m_log, "a") as f:
        f.write(f"  - {description}\n")

    print(f"[Mutator-{worker_id}] Applied mutation: {description}")
    return description