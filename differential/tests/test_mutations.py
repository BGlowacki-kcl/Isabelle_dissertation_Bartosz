"""
Tests for mutations.py — pure string-transformation functions.

Each mutation must:
  - Apply correctly when the target pattern is present (returning a changed string
    and a descriptive message that does NOT start with "No-op").
  - Leave content unchanged and return a "No-op" message when the pattern is absent.
  - Replace only the FIRST occurrence (idempotent application matters for fuzzing).
"""

import random
import pytest
from mutations import (
    swap_and_or,
    negate_condition,
    weaken_quantifier,
    flip_inequality,
    replace_by_with_sorry,
    remove_random_line,
    duplicate_random_line,
)


# Helpers

def _is_noop(result, original, desc):
    return result == original and desc.startswith("No-op")


# swap_and_or

class TestSwapAndOr:
    def test_ascii_conjunction_swapped(self):
        result, desc = swap_and_or("P \\<and> Q")
        assert "\\<or>" in result
        assert "No-op" not in desc


# negate_condition

class TestNegateCondition:
    def test_unicode_negation_removed(self):
        result, desc = negate_condition("¬P ∧ Q")
        assert "¬" not in result
        assert "No-op" not in desc

    def test_ascii_negation_removed(self):
        result, desc = negate_condition("\\<not>P")
        assert "\\<not>" not in result
        assert "No-op" not in desc


# weaken_quantifier

class TestWeakenQuantifier:
    def test_forall_becomes_exists(self):
        result, desc = weaken_quantifier("∀x. P x")
        assert "∃" in result
        assert "∀" not in result
        assert "No-op" not in desc

    def test_ascii_forall_becomes_exists(self):
        result, _ = weaken_quantifier("\\<forall>x. P x")
        assert "\\<exists>" in result


# flip_inequality

class TestFlipInequality:
    @pytest.mark.parametrize("original, flipped", [
        (" ≤ ", " ≥ "),
        (" ≥ ", " ≤ "),
        (" < ",  " > "),
        (" > ",  " < "),
        (" \\<le> ", " \\<ge> "),
        (" \\<ge> ", " \\<le> "),
    ])
    def test_flips_correctly(self, original, flipped):
        content = f"a{original}b"
        result, desc = flip_inequality(content)
        assert flipped in result
        assert "No-op" not in desc

    def test_noop_when_no_inequality(self):
        original = "a = b"
        result, desc = flip_inequality(original)
        assert _is_noop(result, original, desc)


# replace_by_with_sorry

class TestReplaceByWithSorry:
    @pytest.mark.parametrize("tactic", ["simp", "auto", "blast", "linarith", "omega"])
    def test_replaces_tactic_with_sorry(self, tactic):
        content = f"  by {tactic}"
        result, desc = replace_by_with_sorry(content)
        assert "by sorry" in result
        assert f"by {tactic}" not in result
        assert tactic in desc

    def test_noop_when_no_by_tactic(self):
        original = "  apply simp\n  done"
        result, desc = replace_by_with_sorry(original)
        assert _is_noop(result, original, desc)

    def test_only_first_by_replaced(self):
        content = "  by simp\n  by auto"
        result, _ = replace_by_with_sorry(content)
        assert result.count("by sorry") == 1
        assert "by auto" in result


# remove_random_line

class TestRemoveRandomLine:
    def test_reduces_line_count(self):
        content = "theory T\nbegin\nlemma foo: True\n  by simp\nend"
        random.seed(0)
        result, desc = remove_random_line(content)
        assert len(result.splitlines()) < len(content.splitlines())
        assert "No-op" not in desc

    def test_never_removes_theory_or_end_headers(self):
        content = "theory T\nbegin\nlemma foo: True\n  by simp\nend"
        for seed in range(40):
            random.seed(seed)
            result, _ = remove_random_line(content)
            lines = result.splitlines()
            assert any(l.startswith("theory") for l in lines), f"seed {seed}: theory line removed"
            assert any(l.startswith("end") for l in lines),    f"seed {seed}: end line removed"

    def test_noop_when_only_structural_lines(self):
        original = "theory T\nend"
        result, desc = remove_random_line(original)
        assert _is_noop(result, original, desc)


# duplicate_random_line

class TestDuplicateRandomLine:
    def test_increases_line_count_by_one(self):
        content = "theory T\nbegin\nlemma foo: True\nend\n"
        random.seed(0)
        result, desc = duplicate_random_line(content)
        assert len(result.splitlines()) == len(content.splitlines()) + 1
        assert "No-op" not in desc

    def test_noop_on_empty_string(self):
        result, desc = duplicate_random_line("")
        assert "No-op" in desc


# No-op description consistency

def test_noop_description_consistent():
    """No-op descriptions must include the word 'No-op' for callers that check it."""
    noop_inputs = [
        (swap_and_or, "P → Q"),
        (negate_condition, "P ∧ Q"),
        (weaken_quantifier, "∃x. P x"),
        (flip_inequality, "a = b"),
        (replace_by_with_sorry, "apply simp"),
    ]
    for fn, content in noop_inputs:
        _, desc = fn(content)
        assert "No-op" in desc, f"{fn.__name__} did not say 'No-op' on '{content}'"
