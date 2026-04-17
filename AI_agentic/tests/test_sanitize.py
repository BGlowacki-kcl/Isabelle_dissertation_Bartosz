"""
test_sanitize.py - Pure unit tests for sanitize_code() and has_cheat().

These two functions are the anti-cheat gatekeepers: they clean LLM output and
detect forbidden 'sorry'/'oops' keywords before code reaches Isabelle.  No
external dependencies or mocks are needed.
"""
from ai_chats import sanitize_code, has_cheat


# sanitize_code: fence stripping

def test_sanitize_strips_opening_fence():
    result = sanitize_code("```\ntheory Scratch imports Main begin end")
    assert result.startswith("theory Scratch")

def test_sanitize_strips_opening_fence_with_language():
    result = sanitize_code("```isabelle\ntheory Scratch imports Main begin end")
    assert result.startswith("theory Scratch")

def test_sanitize_strips_closing_fence():
    result = sanitize_code("theory Scratch imports Main begin end\n```")
    assert result.endswith("end")
    assert "```" not in result

def test_sanitize_strips_both_fences():
    code = "```isabelle\ntheory Scratch\n  imports Main\nbegin\nend\n```"
    result = sanitize_code(code)
    assert result == "theory Scratch\n  imports Main\nbegin\nend"

def test_sanitize_noop_for_clean_code():
    code = "theory Scratch\n  imports Main\nbegin\nend"
    assert sanitize_code(code) == code

def test_sanitize_strips_surrounding_whitespace():
    code = "  \n  theory Scratch imports Main begin end  \n  "
    assert sanitize_code(code) == "theory Scratch imports Main begin end"

def test_sanitize_does_not_strip_internal_fence():
    inner = "theory Scratch imports Main begin\n-- ``` this is a comment\nend"
    result = sanitize_code("```\n" + inner + "\n```")
    assert "-- ``` this is a comment" in result

def test_sanitize_language_variant_python_fence():
    result = sanitize_code("```python\ntheory Scratch imports Main begin end\n```")
    assert result.startswith("theory Scratch")
    assert "```" not in result

def test_sanitize_empty_string_returns_empty():
    assert sanitize_code("") == ""

def test_sanitize_only_fences_returns_empty():
    assert sanitize_code("```\n```") == ""


# sanitize_code: cheat warnings

def test_sanitize_warns_on_sorry(capsys):
    sanitize_code("theory Scratch imports Main begin\nby sorry\nend")
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "sorry" in out.lower()

def test_sanitize_warns_on_oops(capsys):
    sanitize_code("theory Scratch imports Main begin\noops\nend")
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "oops" in out.lower()

def test_sanitize_no_warning_for_clean_code(capsys):
    sanitize_code("theory Scratch imports Main begin end")
    out = capsys.readouterr().out
    assert "WARNING" not in out


# has_cheat

def test_has_cheat_detects_sorry():
    assert has_cheat("lemma False by sorry") is True

def test_has_cheat_false_for_clean_code():
    assert has_cheat("theory Scratch imports Main begin end") is False

def test_has_cheat_sorry_case_insensitive():
    assert has_cheat("SORRY") is True
    assert has_cheat("SoRrY") is True

def test_has_cheat_oops_case_insensitive():
    assert has_cheat("OOPS") is True
    assert has_cheat("Oops") is True
    assert has_cheat("oops") is True

def test_has_cheat_detects_both_in_same_code():
    assert has_cheat("sorry here, oops there") is True

def test_has_cheat_sorry_embedded_in_line():
    assert has_cheat("notsorryatall") is True

def test_has_cheat_empty_string():
    assert has_cheat("") is False
