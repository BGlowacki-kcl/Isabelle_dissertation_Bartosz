import subprocess
import time
import pyautogui
import pygetwindow as gw
import pyperclip
from PIL import ImageGrab
from config import ISABELLE_EXE
from ai_chats import chat_vision

pyautogui.PAUSE = 0.3
pyautogui.FAILSAFE = True


def launch_isabelle():
    subprocess.Popen([ISABELLE_EXE])
    print("Launched Isabelle, waiting for window to open...")
    time.sleep(15)


def find_isabelle_window():
    for fragment in ["Isabelle", "jEdit"]:
        windows = gw.getWindowsWithTitle(fragment)
        if windows:
            win = windows[0]
            print(f"Found window: '{win.title}' at ({win.left}, {win.top}), size {win.width}x{win.height}")
            return win
    raise RuntimeError("Isabelle window not found. Make sure it is running.")


def focus_window(win):
    win.activate()
    time.sleep(0.5)


def screenshot(region=None, save_path=None):
    if region:
        left, top, width, height = region
        img = ImageGrab.grab(bbox=(left, top, left + width, top + height))
    else:
        img = ImageGrab.grab()
    if save_path:
        img.save(save_path)
        print(f"Screenshot saved to: {save_path}")
    return img


def click_in_window(win, rel_x: float, rel_y: float):
    x = win.left + int(win.width * rel_x)
    y = win.top + int(win.height * rel_y)
    pyautogui.click(x, y)


def type_text(text: str):
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")


def hotkey(*keys):
    pyautogui.hotkey(*keys)


def type_code_into_editor(win, code: str):
    click_in_window(win, rel_x=0.5, rel_y=0.5)
    time.sleep(0.3)
    hotkey("ctrl", "a")
    time.sleep(0.2)
    type_text(code)


def wait_for_isabelle_ready(win, timeout=90, poll_interval=6) -> bool:
    print("Waiting for Isabelle to finish processing...")
    start = time.time()
    while time.time() - start < timeout:
        img = screenshot((win.left, win.top, win.width, win.height))
        response = chat_vision(
            img,
            "Is Isabelle still processing (parsing, loading, checking) or "
            "is it finished/ready? Reply with ONLY 'READY' or 'BUSY' as the "
            "first word, then a brief reason.",
        )
        if "READY" in response.upper().split("\n")[0]:
            print("Isabelle appears ready.")
            return True
        print(f"  Still processing... ({int(time.time() - start)}s elapsed)")
        time.sleep(poll_interval)
    print("Timed out waiting for Isabelle.")
    return False


def get_screen_description(win) -> str:
    img = screenshot((win.left, win.top, win.width, win.height))
    return chat_vision(img)
