"""
Shared test configuration. Inserts the project root into sys.path so that
all differential-testing modules are importable from tests/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import comparator


SIMPLE_THEORY = (
    "theory Test\n"
    "  imports Main\n"
    "begin\n"
    "\n"
    'lemma foo: "P ∧ Q"\n'
    "  by simp\n"
    "\n"
    "end\n"
)


@pytest.fixture
def simple_theory():
    return SIMPLE_THEORY


@pytest.fixture(autouse=False)
def no_disk(monkeypatch):
    """Suppress file I/O in compare_outputs so tests don't write artefacts."""
    monkeypatch.setattr(comparator, "_dump_raw_outputs", lambda *a, **kw: None)
