import random


def swap_and_or(content):
    """Swap a conjunction for a disjunction."""
    if " ∧ " in content:
        return content.replace(" ∧ ", " ∨ ", 1), "Swapped ∧ → ∨"
    if " \\<and>" in content:
        return content.replace(" \\<and>", " \\<or>", 1), "Swapped \\<and> → \\<or>"
    return content, "No-op (swap_and_or: nothing to swap)"


def negate_condition(content):
    """Remove a negation operator."""
    if "¬" in content:
        return content.replace("¬", "", 1), "Removed a negation ¬"
    if "\\<not>" in content:
        return content.replace("\\<not>", "", 1), "Removed \\<not>"
    return content, "No-op (negate: nothing found)"


def remove_random_line(content):
    """Delete a random non-structural line."""
    lines = content.splitlines(keepends=True)
    removable = [
        i for i, l in enumerate(lines)
        if l.strip()
        and not l.strip().startswith("theory")
        and not l.strip().startswith("end")
    ]
    if not removable:
        return content, "No-op (remove_line: nothing removable)"
    idx = random.choice(removable)
    removed = lines[idx].rstrip()
    lines.pop(idx)
    return "".join(lines), f"Removed line {idx}: {removed!r}"


def duplicate_random_line(content):
    """Duplicate a random line in place."""
    lines = content.splitlines(keepends=True)
    if not lines:
        return content, "No-op (duplicate_line: empty)"
    idx = random.randint(0, len(lines) - 1)
    lines.insert(idx, lines[idx])
    return "".join(lines), f"Duplicated line {idx}: {lines[idx].rstrip()!r}"


ALL_MUTATIONS = [
    swap_and_or,
    negate_condition,
    remove_random_line,
    duplicate_random_line,
]
