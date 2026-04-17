"""
test_main_loop.py - Branch coverage for run_ai_demo().

run_ai_demo() is the top-level orchestration loop.  It has four distinct
branches per iteration: clean contradiction (break), cheat override, system
hang, and continue (FAILED).  Each is tested here with all external calls
mocked via main's own namespace (because main.py uses 'from x import y').
"""
import time as _time
from unittest.mock import MagicMock
import pytest
from PIL import Image

import main


CLEAN_CODE = "theory Scratch\n  imports Main\nbegin\nend"


class _StopTest(Exception):
    """Raised by mocked side effects to abort a test mid-loop cleanly."""


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(_time, "sleep", MagicMock())


@pytest.fixture
def base(monkeypatch):
    """Patch every external name in main's namespace."""
    win = MagicMock()
    win.left, win.top, win.width, win.height = 0, 0, 800, 600

    monkeypatch.setattr(main, "reset_all_chats", MagicMock())
    monkeypatch.setattr(main, "launch_isabelle", MagicMock())
    monkeypatch.setattr(main, "find_isabelle_window", MagicMock(return_value=win))
    monkeypatch.setattr(main, "focus_window", MagicMock())
    monkeypatch.setattr(main, "get_screen_description", MagicMock(return_value="IDE ready"))
    monkeypatch.setattr(main, "screenshot", MagicMock(return_value=Image.new("RGB", (4, 4))))
    monkeypatch.setattr(main, "type_code_into_editor", MagicMock())
    monkeypatch.setattr(main, "wait_for_isabelle_ready", MagicMock(return_value=True))
    monkeypatch.setattr(main, "chat_vision", MagicMock(return_value="No errors visible"))
    monkeypatch.setattr(main, "sanitize_code", lambda x: x)

    return monkeypatch, win


# Startup sequence

def test_reset_is_called_before_launch_isabelle(base, monkeypatch):
    call_order = []
    monkeypatch.setattr(main, "reset_all_chats", MagicMock(side_effect=lambda: call_order.append("reset")))
    monkeypatch.setattr(main, "launch_isabelle", MagicMock(side_effect=lambda: call_order.append("launch")))
    monkeypatch.setattr(main, "chat_strategist", MagicMock(side_effect=_StopTest))
    monkeypatch.setattr(main, "chat_coder", MagicMock(return_value=CLEAN_CODE))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=False))

    with pytest.raises(_StopTest):
        main.run_ai_demo()

    assert "reset" in call_order and "launch" in call_order
    assert call_order.index("reset") < call_order.index("launch")


def test_find_and_focus_window_called_on_startup(base, monkeypatch):
    find_mock = MagicMock(return_value=MagicMock(left=0, top=0, width=800, height=600))
    focus_mock = MagicMock()
    monkeypatch.setattr(main, "find_isabelle_window", find_mock)
    monkeypatch.setattr(main, "focus_window", focus_mock)
    monkeypatch.setattr(main, "chat_strategist", MagicMock(side_effect=[
        "strategy", "VERDICT: CONTRADICTION_FOUND", "analysis"
    ]))
    monkeypatch.setattr(main, "chat_coder", MagicMock(return_value=CLEAN_CODE))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=False))

    main.run_ai_demo()

    find_mock.assert_called_once()
    focus_mock.assert_called_once()


def test_initial_strategy_and_code_generated_before_loop(base, monkeypatch):
    coder_mock = MagicMock(return_value=CLEAN_CODE)
    monkeypatch.setattr(main, "chat_coder", coder_mock)
    monkeypatch.setattr(main, "chat_strategist", MagicMock(side_effect=[
        "initial strategy", "VERDICT: CONTRADICTION_FOUND", "analysis"
    ]))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=False))

    main.run_ai_demo()

    assert coder_mock.call_count >= 1


# CONTRADICTION_FOUND with clean code 

def test_clean_contradiction_exits_loop(base, monkeypatch):
    monkeypatch.setattr(main, "chat_strategist", MagicMock(side_effect=[
        "strategy", "VERDICT: CONTRADICTION_FOUND", "final analysis"
    ]))
    monkeypatch.setattr(main, "chat_coder", MagicMock(return_value=CLEAN_CODE))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=False))

    main.run_ai_demo()


def test_clean_contradiction_requests_final_analysis(base, monkeypatch):
    strat_mock = MagicMock(side_effect=["strategy", "VERDICT: CONTRADICTION_FOUND", "analysis"])
    monkeypatch.setattr(main, "chat_strategist", strat_mock)
    monkeypatch.setattr(main, "chat_coder", MagicMock(return_value=CLEAN_CODE))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=False))

    main.run_ai_demo()

    assert strat_mock.call_count == 3


def test_clean_contradiction_takes_screenshot(base, monkeypatch):
    monkeypatch.setattr(main, "chat_strategist", MagicMock(side_effect=[
        "strategy", "VERDICT: CONTRADICTION_FOUND", "analysis"
    ]))
    monkeypatch.setattr(main, "chat_coder", MagicMock(return_value=CLEAN_CODE))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=False))
    sc_mock = MagicMock(return_value=Image.new("RGB", (4, 4)))
    monkeypatch.setattr(main, "screenshot", sc_mock)

    main.run_ai_demo()

    assert sc_mock.call_count >= 2


# CONTRADICTION_FOUND with cheat code 

def test_cheat_override_sends_correction_prompt_to_strategist(base, monkeypatch):
    correction_prompt = []
    call_n = 0

    def strat(prompt, **kw):
        nonlocal call_n
        call_n += 1
        if call_n == 1:
            return "strategy"
        if call_n == 2:
            return "VERDICT: CONTRADICTION_FOUND"
        correction_prompt.append(prompt)
        raise _StopTest

    monkeypatch.setattr(main, "chat_strategist", MagicMock(side_effect=strat))
    monkeypatch.setattr(main, "chat_coder", MagicMock(return_value="sorry code"))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=True))

    with pytest.raises(_StopTest):
        main.run_ai_demo()

    assert correction_prompt, "correction call never made"
    assert "CORRECTION" in correction_prompt[0]


def test_cheat_override_correction_mentions_sorry(base, monkeypatch):
    call_n = 0
    received = []

    def strat(prompt, **kw):
        nonlocal call_n
        call_n += 1
        if call_n == 1: return "strategy"
        if call_n == 2: return "VERDICT: CONTRADICTION_FOUND"
        received.append(prompt)
        raise _StopTest

    monkeypatch.setattr(main, "chat_strategist", MagicMock(side_effect=strat))
    monkeypatch.setattr(main, "chat_coder", MagicMock(return_value="sorry"))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=True))

    with pytest.raises(_StopTest):
        main.run_ai_demo()

    assert "sorry" in received[0].lower() or "oops" in received[0].lower()


def test_no_cheat_override_for_clean_contradiction(base, monkeypatch):
    strat_mock = MagicMock(side_effect=["strategy", "VERDICT: CONTRADICTION_FOUND", "analysis"])
    monkeypatch.setattr(main, "chat_strategist", strat_mock)
    monkeypatch.setattr(main, "chat_coder", MagicMock(return_value=CLEAN_CODE))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=False))

    main.run_ai_demo()

    assert strat_mock.call_count == 3


# SYSTEM_HANG branch

def _hang_then_succeed_strat(call_n_box):
    def strat(prompt, **kw):
        call_n_box[0] += 1
        n = call_n_box[0]
        if n == 1: return "strategy"
        if n == 2: return "VERDICT: SYSTEM_HANG"
        if n == 3: return "VERDICT: CONTRADICTION_FOUND"
        return "analysis"
    return strat


def test_system_hang_types_blank_theory_into_editor(base, monkeypatch):
    type_mock = MagicMock()
    monkeypatch.setattr(main, "type_code_into_editor", type_mock)
    call_n = [0]
    monkeypatch.setattr(main, "chat_strategist", MagicMock(side_effect=_hang_then_succeed_strat(call_n)))
    monkeypatch.setattr(main, "chat_coder", MagicMock(return_value=CLEAN_CODE))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=False))

    main.run_ai_demo()

    typed_codes = [c.args[1] for c in type_mock.call_args_list]
    assert main.BLANK_THEORY in typed_codes


def test_system_hang_sleeps_10_seconds(base, monkeypatch):
    sleep_mock = MagicMock()
    monkeypatch.setattr(_time, "sleep", sleep_mock)
    call_n = [0]
    monkeypatch.setattr(main, "chat_strategist", MagicMock(side_effect=_hang_then_succeed_strat(call_n)))
    monkeypatch.setattr(main, "chat_coder", MagicMock(return_value=CLEAN_CODE))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=False))

    main.run_ai_demo()

    sleep_mock.assert_called_with(10)


def test_system_hang_resets_current_code_to_blank(base, monkeypatch):
    coder_prompts = []
    def coder(prompt, **kw):
        coder_prompts.append(prompt)
        return CLEAN_CODE
    monkeypatch.setattr(main, "chat_coder", MagicMock(side_effect=coder))
    call_n = [0]
    monkeypatch.setattr(main, "chat_strategist", MagicMock(side_effect=_hang_then_succeed_strat(call_n)))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=False))

    main.run_ai_demo()

    post_hang_prompt = coder_prompts[1] 
    assert main.BLANK_THEORY in post_hang_prompt


# Code typing and readiness polling

def test_coder_output_is_typed_into_editor(base, monkeypatch):
    coder_output = "theory Scratch imports Main begin\nlemma True by simp\nend"
    monkeypatch.setattr(main, "chat_coder", MagicMock(return_value=coder_output))
    monkeypatch.setattr(main, "chat_strategist", MagicMock(side_effect=[
        "strategy", "VERDICT: CONTRADICTION_FOUND", "analysis"
    ]))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=False))
    type_mock = MagicMock()
    monkeypatch.setattr(main, "type_code_into_editor", type_mock)

    main.run_ai_demo()

    typed = [c.args[1] for c in type_mock.call_args_list]
    assert coder_output in typed


def test_wait_for_ready_called_after_code_submission(base, monkeypatch):
    wait_mock = MagicMock(return_value=True)
    monkeypatch.setattr(main, "wait_for_isabelle_ready", wait_mock)
    monkeypatch.setattr(main, "chat_strategist", MagicMock(side_effect=[
        "strategy", "VERDICT: CONTRADICTION_FOUND", "analysis"
    ]))
    monkeypatch.setattr(main, "chat_coder", MagicMock(return_value=CLEAN_CODE))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=False))

    main.run_ai_demo()

    assert wait_mock.call_count >= 1


def test_vision_called_each_iteration(base, monkeypatch):
    vision_mock = MagicMock(return_value="No errors")
    monkeypatch.setattr(main, "chat_vision", vision_mock)
    monkeypatch.setattr(main, "chat_strategist", MagicMock(side_effect=[
        "strategy", "VERDICT: CONTRADICTION_FOUND", "analysis"
    ]))
    monkeypatch.setattr(main, "chat_coder", MagicMock(return_value=CLEAN_CODE))
    monkeypatch.setattr(main, "has_cheat", MagicMock(return_value=False))

    main.run_ai_demo()

    assert vision_mock.call_count >= 1
