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


def weaken_quantifier(content):
    """Replace a universal quantifier with an existential one, weakening the statement."""
    if "∀" in content:
        return content.replace("∀", "∃", 1), "Replaced ∀ → ∃ (weakened quantifier)"
    if "\\<forall>" in content:
        return content.replace("\\<forall>", "\\<exists>", 1), "Replaced \\<forall> → \\<exists>"
    return content, "No-op (weaken_quantifier: no ∀ found)"


def replace_by_with_sorry(content):
    """Replace a proof tactic (e.g. "by simp") with "by sorry" - don't check the proof"""
    import re
    pattern = re.compile(r'\bby\s+\w[\w_]*', re.MULTILINE)
    match = pattern.search(content)
    if match:
        new_content = content[:match.start()] + "by sorry" + content[match.end():]
        return new_content, f"Replaced '{match.group()}' → 'by sorry'"
    return content, "No-op (replace_by_with_sorry: no 'by <tactic>' found)"


def flip_inequality(content):
    """Flip an inequality sign to its opposite."""
    pairs = [
        (" ≤ ", " ≥ "),
        (" ≥ ", " ≤ "),
        (" < ",  " > "),
        (" > ",  " < "),
        (" \\<le> ", " \\<ge> "),
        (" \\<ge> ", " \\<le> "),
        (" \\<less> ", " \\<greater> "),
    ]
    for original, replacement in pairs:
        if original in content:
            return content.replace(original, replacement, 1), \
                   f"Flipped inequality '{original.strip()}' → '{replacement.strip()}'"
    return content, "No-op (flip_inequality: no inequality found)"


ALL_MUTATIONS = [
    swap_and_or,
    negate_condition,
    remove_random_line,
    duplicate_random_line,
    weaken_quantifier,
    replace_by_with_sorry,
    flip_inequality,
]
