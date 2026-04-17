"""
test_gui.py - Unit tests for gui.py with all platform calls mocked.

gui.py orchestrates Windows GUI automation: launching Isabelle, finding its
window, taking screenshots, typing code into the editor, and polling readiness
via the Vision agent.  Every platform call (subprocess, pyautogui, ImageGrab,
pyperclip, time.sleep) is replaced with mocks so these tests run headlessly.
"""
import time as _time
from unittest.mock import MagicMock
import pytest
from PIL import Image

import gui
import subprocess
import config


# Module-level fixtures

@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Prevent any test from actually sleeping."""
    m = MagicMock()
    monkeypatch.setattr(_time, "sleep", m)
    return m


@pytest.fixture
def mock_imagegrab(monkeypatch):
    m = MagicMock()
    monkeypatch.setattr(gui, "ImageGrab", m)
    return m


@pytest.fixture
def mock_pag(monkeypatch):
    m = MagicMock()
    monkeypatch.setattr(gui, "pyautogui", m)
    return m


@pytest.fixture
def mock_pyperclip(monkeypatch):
    m = MagicMock()
    monkeypatch.setattr(gui, "pyperclip", m)
    return m


@pytest.fixture
def win():
    """A fake Isabelle window: left=100, top=200, 800x600."""
    w = MagicMock()
    w.left, w.top, w.width, w.height = 100, 200, 800, 600
    w.title = "Isabelle2025"
    return w


# launch_isabelle

def test_launch_isabelle_calls_popen_with_exe(monkeypatch):
    popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", popen)
    gui.launch_isabelle()
    popen.assert_called_once_with([config.ISABELLE_EXE])


def test_launch_isabelle_sleeps_15s(no_sleep, monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", MagicMock())
    gui.launch_isabelle()
    no_sleep.assert_called_with(15)


# find_isabelle_window

def test_find_window_returns_isabelle_match(win):
    gui.gw.getWindowsWithTitle.side_effect = lambda name: [win] if name == "Isabelle" else []
    assert gui.find_isabelle_window() is win


def test_find_window_falls_back_to_jedit(win):
    gui.gw.getWindowsWithTitle.side_effect = lambda name: [] if name == "Isabelle" else [win]
    assert gui.find_isabelle_window() is win


def test_find_window_raises_when_nothing_found():
    gui.gw.getWindowsWithTitle.side_effect = lambda name: []
    with pytest.raises(RuntimeError, match="Isabelle window not found"):
        gui.find_isabelle_window()


def test_find_window_returns_first_of_multiple_matches(win):
    other = MagicMock()
    gui.gw.getWindowsWithTitle.side_effect = lambda name: [win, other] if name == "Isabelle" else []
    assert gui.find_isabelle_window() is win


# focus_window 

def test_focus_window_calls_activate(win):
    gui.focus_window(win)
    win.activate.assert_called_once()


def test_focus_window_sleeps_half_second(win, no_sleep):
    gui.focus_window(win)
    no_sleep.assert_called_with(0.5)


# screenshot

def test_screenshot_with_region_computes_correct_bbox(mock_imagegrab):
    fake = Image.new("RGB", (4, 4))
    mock_imagegrab.grab.return_value = fake
    gui.screenshot((10, 20, 100, 200))
    mock_imagegrab.grab.assert_called_once_with(bbox=(10, 20, 110, 220))


def test_screenshot_without_region_calls_grab_no_args(mock_imagegrab):
    fake = Image.new("RGB", (4, 4))
    mock_imagegrab.grab.return_value = fake
    gui.screenshot()
    mock_imagegrab.grab.assert_called_once_with()


def test_screenshot_returns_grabbed_image(mock_imagegrab):
    fake = Image.new("RGB", (4, 4))
    mock_imagegrab.grab.return_value = fake
    assert gui.screenshot() is fake


def test_screenshot_saves_when_path_provided(tmp_path, mock_imagegrab):
    mock_img = MagicMock()
    mock_imagegrab.grab.return_value = mock_img
    path = str(tmp_path / "shot.png")
    gui.screenshot(save_path=path)
    mock_img.save.assert_called_once_with(path)


def test_screenshot_does_not_save_without_path(mock_imagegrab):
    mock_img = MagicMock()
    mock_imagegrab.grab.return_value = mock_img
    gui.screenshot()
    mock_img.save.assert_not_called()


# click_in_window 

def test_click_center_of_window(win, mock_pag):
    gui.click_in_window(win, 0.5, 0.5)
    mock_pag.click.assert_called_once_with(500, 500)


def test_click_top_left_of_window(win, mock_pag):
    gui.click_in_window(win, 0.0, 0.0)
    mock_pag.click.assert_called_once_with(100, 200)


def test_click_bottom_right_of_window(win, mock_pag):
    gui.click_in_window(win, 1.0, 1.0)
    mock_pag.click.assert_called_once_with(900, 800)


# type_text

def test_type_text_copies_to_clipboard(mock_pag, mock_pyperclip):
    gui.type_text("hello Isabelle")
    mock_pyperclip.copy.assert_called_once_with("hello Isabelle")


def test_type_text_pastes_via_ctrl_v(mock_pag, mock_pyperclip):
    gui.type_text("anything")
    mock_pag.hotkey.assert_called_once_with("ctrl", "v")


# hotkey

def test_hotkey_delegates_to_pyautogui(mock_pag):
    gui.hotkey("ctrl", "a")
    mock_pag.hotkey.assert_called_once_with("ctrl", "a")


def test_hotkey_passes_multiple_keys(mock_pag):
    gui.hotkey("ctrl", "shift", "s")
    mock_pag.hotkey.assert_called_once_with("ctrl", "shift", "s")


# type_code_into_editor

def test_type_code_clicks_window_center(win, mock_pag, mock_pyperclip):
    gui.type_code_into_editor(win, "theory Scratch imports Main begin end")
    expected_x = win.left + int(win.width * 0.5)
    expected_y = win.top + int(win.height * 0.5)
    mock_pag.click.assert_called_once_with(expected_x, expected_y)


def test_type_code_sends_ctrl_a_to_select_all(win, mock_pag, mock_pyperclip):
    gui.type_code_into_editor(win, "code")
    mock_pag.hotkey.assert_any_call("ctrl", "a")


def test_type_code_pastes_the_code_text(win, mock_pag, mock_pyperclip):
    gui.type_code_into_editor(win, "my theory code")
    mock_pyperclip.copy.assert_called_once_with("my theory code")


def test_type_code_paste_hotkey_fires_after_select_all(win, mock_pag, mock_pyperclip):
    gui.type_code_into_editor(win, "code")
    hotkey_calls = [c.args for c in mock_pag.hotkey.call_args_list]
    ctrl_a_idx = next(i for i, a in enumerate(hotkey_calls) if a == ("ctrl", "a"))
    ctrl_v_idx = next(i for i, a in enumerate(hotkey_calls) if a == ("ctrl", "v"))
    assert ctrl_a_idx < ctrl_v_idx


# wait_for_isabelle_ready

def test_wait_ready_returns_true_on_first_ready(win, mock_imagegrab, monkeypatch):
    mock_imagegrab.grab.return_value = Image.new("RGB", (4, 4))
    times = iter([0, 1, 999])
    monkeypatch.setattr(_time, "time", lambda: next(times))
    monkeypatch.setattr(gui, "chat_vision", MagicMock(return_value="READY — prover idle"))
    assert gui.wait_for_isabelle_ready(win, timeout=90) is True


def test_wait_ready_returns_false_after_timeout(win, monkeypatch):
    times = iter([0, 1000])
    monkeypatch.setattr(_time, "time", lambda: next(times))
    assert gui.wait_for_isabelle_ready(win, timeout=90) is False


def test_wait_ready_retries_on_busy_then_ready(win, mock_imagegrab, monkeypatch):
    mock_imagegrab.grab.return_value = Image.new("RGB", (4, 4))
    times = iter([0, 1, 2, 3, 999])
    monkeypatch.setattr(_time, "time", lambda: next(times))
    responses = iter(["BUSY — loading", "READY — done"])
    mock_cv = MagicMock(side_effect=lambda img, prompt=None: next(responses))
    monkeypatch.setattr(gui, "chat_vision", mock_cv)
    result = gui.wait_for_isabelle_ready(win, timeout=90, poll_interval=0)
    assert result is True
    assert mock_cv.call_count == 2


def test_wait_ready_prompt_contains_ready_and_busy(win, mock_imagegrab, monkeypatch):
    mock_imagegrab.grab.return_value = Image.new("RGB", (4, 4))
    times = iter([0, 1, 999])
    monkeypatch.setattr(_time, "time", lambda: next(times))
    mock_cv = MagicMock(return_value="READY")
    monkeypatch.setattr(gui, "chat_vision", mock_cv)
    gui.wait_for_isabelle_ready(win, timeout=90)
    prompt = mock_cv.call_args[0][1]
    assert "READY" in prompt and "BUSY" in prompt


def test_wait_ready_screenshots_window_region(win, mock_imagegrab, monkeypatch):
    mock_imagegrab.grab.return_value = Image.new("RGB", (4, 4))
    times = iter([0, 1, 999])
    monkeypatch.setattr(_time, "time", lambda: next(times))
    monkeypatch.setattr(gui, "chat_vision", MagicMock(return_value="READY"))
    gui.wait_for_isabelle_ready(win, timeout=90)
    expected_bbox = (win.left, win.top, win.left + win.width, win.top + win.height)
    mock_imagegrab.grab.assert_called_with(bbox=expected_bbox)


# get_screen_description

def test_get_screen_description_calls_screenshot_with_window_region(win, monkeypatch):
    mock_sc = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(gui, "screenshot", mock_sc)
    monkeypatch.setattr(gui, "chat_vision", MagicMock(return_value="desc"))
    gui.get_screen_description(win)
    mock_sc.assert_called_once_with((win.left, win.top, win.width, win.height))


def test_get_screen_description_returns_vision_output(win, monkeypatch):
    monkeypatch.setattr(gui, "screenshot", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(gui, "chat_vision", MagicMock(return_value="Isabelle is processing"))
    assert gui.get_screen_description(win) == "Isabelle is processing"
