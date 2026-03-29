import pyautogui
import pygetwindow as gw
from PIL import Image, ImageGrab
import pyperclip
import time
import subprocess
import base64
import io
import os
from mistralai import Mistral

pyautogui.PAUSE = 0.3
pyautogui.FAILSAFE = True  

ISABELLE_EXE = r"C:\Isabelle\Isabelle2025-2\Isabelle2025-2.exe"
SCREENSHOT_DIR = r"C:\Isabelle"

# ─── Mistral AI Configuration

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
MISTRAL_MODEL = "mistral-large-latest"

client = Mistral(api_key=MISTRAL_API_KEY)


# 3-Chat Architecture
#
# Chat 1: STRATEGIST — text-only, long conversation history
#   Brainstorms creative strategies to break Isabelle/HOL's soundness,
#   evaluates feedback from the vision chat, decides next moves.
#
# Chat 2: CODER — text-only, long conversation history
#   Receives a strategy description and produces valid Isabelle theory code.
#   Remembers prior code attempts so it doesn't repeat itself.
#
# Chat 3: VISION — one-shot with image, NO conversation history
#   Receives a single screenshot, describes exactly what is on screen.
#   Pure perception — no strategy, no code generation.
#

STRATEGIST_SYSTEM = (
    "You are an expert in Isabelle/HOL theorem proving, formal logic, and "
    "proof assistant internals. Your mission is to find a GENUINE logical "
    "contradiction — a real proof of False — in Isabelle/HOL.\n\n"
    "CRITICAL RULES:\n"
    "- 'sorry' is FORBIDDEN. It is a cheat that admits anything. Not a proof.\n"
    "- 'oops' is FORBIDDEN. It abandons proofs.\n"
    "- Trivially axiomatizing False is FORBIDDEN.\n"
    "- Only a proof accepted by Isabelle with NO red errors, NO sorry, NO oops counts.\n\n"
    "Your role is to THINK about attack strategies. You do NOT write code.\n"
    "You propose a concrete strategy and explain WHY it might work.\n"
    "When you receive feedback about what happened (errors, success, etc.), you "
    "analyze it and propose a NEW or REFINED strategy.\n\n"
    "Creative strategies to consider:\n"
    "- typedef with empty carrier sets to derive False\n"
    "- Conflicting type class instantiations\n"
    "- Overloading definition abuse / conflicting overloaded constants\n"
    "- locale/interpretation tricks to create inconsistencies\n"
    "- ML code injection via ML blocks to bypass the kernel\n"
    "- Nontermination: partial_function, function package, non-well-founded recursion\n"
    "- Code generator / eval exploits\n"
    "- Coercion / type representation abuse\n"
    "- Infinite rewriting or looping tactics to hang the system\n"
    "- Historical soundness bugs in Isabelle\n"
    "- Interactions between different Isabelle modules\n"
    "- Abuse of axiom_of_choice, Hilbert_Choice, or foundation axioms\n\n"
    "Each attempt MUST try a DIFFERENT strategy. Never repeat a failed approach.\n"
    "Be specific and detailed in your strategy descriptions."
)

CODER_SYSTEM = (
    "You are an expert Isabelle/HOL code writer. You receive a strategy "
    "description and produce a COMPLETE, valid Isabelle theory file that "
    "implements that strategy.\n\n"
    "CRITICAL RULES:\n"
    "- Output ONLY raw Isabelle code starting with 'theory' and ending with 'end'.\n"
    "- NO markdown code fences. NO commentary. Just the code.\n"
    "- NEVER use 'sorry' anywhere.\n"
    "- NEVER use 'oops' anywhere.\n"
    "- NEVER trivially axiomatize False.\n"
    "- The theory name MUST be 'Scratch'.\n"
    "- The theory MUST import 'Main' (and possibly other theories if needed).\n"
    "- Make the code syntactically valid. Use proper Isabelle syntax.\n"
    "- If you receive error feedback, fix the code based on the errors."
)

VISION_SYSTEM = (
    "You are a precise screen reader for the Isabelle/jEdit IDE. "
    "You receive a screenshot and describe EXACTLY what you see.\n\n"
    "You MUST report:\n"
    "1. PROCESSING STATUS: Is Isabelle still processing (look for status bar "
    "messages like 'Parsing...', 'Checking...', spinning indicators) or is it "
    "finished (status shows 'Prover: ready' or similar)?\n"
    "2. ERRORS: Are there any red error markers, red highlighting, or error "
    "messages in the output panel? If yes, describe them as precisely as possible — "
    "quote the error text if you can read it.\n"
    "3. SUCCESS INDICATORS: Are there green or blue highlighted lines? Which ones?\n"
    "4. CODE VISIBLE: What theory code is visible in the editor? Summarize it.\n"
    "5. PROOF STATUS: For each lemma/theorem visible, is it proven (green/blue), "
    "errored (red), or unprocessed (gray)?\n\n"
    "Be factual and precise. Do NOT interpret strategy or suggest code changes. "
    "Just describe what you see."
)

_strategist_history: list[dict] = []
_coder_history: list[dict] = []


# ─── Chat Functions 

def _image_to_base64(img: Image.Image, fmt: str = "PNG") -> str:
    """Convert a PIL image to a base64-encoded string."""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def chat_strategist(prompt: str, temperature: float = 0.4) -> str:
    """Text-only message to the Strategist chat. Long conversation history."""
    global _strategist_history
    user_msg = {"role": "user", "content": prompt}
    messages = [{"role": "system", "content": STRATEGIST_SYSTEM}]
    messages.extend(_strategist_history)
    messages.append(user_msg)
    response = client.chat.complete(
        model=MISTRAL_MODEL, messages=messages, temperature=temperature,
    )
    reply = response.choices[0].message.content
    _strategist_history.append(user_msg)
    _strategist_history.append({"role": "assistant", "content": reply})
    print(f"[Strategist] Response ({len(reply)} chars)")
    return reply


def chat_coder(prompt: str, temperature: float = 0.2) -> str:
    """Text-only message to the Coder chat. Long conversation history."""
    global _coder_history
    user_msg = {"role": "user", "content": prompt}
    messages = [{"role": "system", "content": CODER_SYSTEM}]
    messages.extend(_coder_history)
    messages.append(user_msg)
    response = client.chat.complete(
        model=MISTRAL_MODEL, messages=messages, temperature=temperature,
    )
    reply = response.choices[0].message.content
    _coder_history.append(user_msg)
    _coder_history.append({"role": "assistant", "content": reply})
    print(f"[Coder] Response ({len(reply)} chars)")
    return reply


def chat_vision(img: Image.Image, prompt: str | None = None,
                temperature: float = 0.1) -> str:
    """One-shot vision call — NO conversation history. Single screenshot in, description out."""
    b64 = _image_to_base64(img)
    if not prompt:
        prompt = "Describe exactly what you see on this Isabelle/jEdit screenshot."
    messages = [
        {"role": "system", "content": VISION_SYSTEM},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        },
    ]
    response = client.chat.complete(
        model=MISTRAL_MODEL, messages=messages, temperature=temperature,
    )
    reply = response.choices[0].message.content
    print(f"[Vision] Response ({len(reply)} chars)")
    return reply


def reset_all_chats():
    """Clear all conversation histories."""
    global _strategist_history, _coder_history
    _strategist_history = []
    _coder_history = []
    print("[Reset] All chat histories cleared.")


# ─── Code Helpers

def sanitize_code(code: str) -> str:
    """Strip markdown code fences and warn about sorry/oops."""
    lines = code.strip().splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    cleaned = "\n".join(lines).strip()
    if "sorry" in cleaned.lower():
        print("WARNING: Code contains 'sorry'.")
    if "oops" in cleaned.lower():
        print("WARNING: Code contains 'oops'.")
    return cleaned


def has_cheat(code: str) -> bool:
    """Check if code uses sorry or oops."""
    low = code.lower()
    return "sorry" in low or "oops" in low


# ─── GUI Actions

def launch_isabelle():
    """Launch Isabelle/jEdit."""
    subprocess.Popen([ISABELLE_EXE])
    print("Launched Isabelle, waiting for window to open...")
    time.sleep(15)


def find_isabelle_window():
    """Find the Isabelle/jEdit window by title."""
    for title_fragment in ["Isabelle", "jEdit"]:
        windows = gw.getWindowsWithTitle(title_fragment)
        if windows:
            win = windows[0]
            print(f"Found window: '{win.title}' at ({win.left}, {win.top}), "
                  f"size {win.width}x{win.height}")
            return win
    raise RuntimeError("Isabelle window not found. Make sure it is running.")


def focus_window(win):
    win.activate()
    time.sleep(0.5)


def screenshot(region=None, save_path=None):
    """Take a screenshot. Returns a PIL Image."""
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
    print(f"Clicked at ({x}, {y})")


def type_text(text: str):
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    print(f"Typed text via clipboard ({len(text)} chars)")


def hotkey(*keys):
    pyautogui.hotkey(*keys)
    print(f"Hotkey: {'+'.join(keys)}")


def type_code_into_editor(win, code: str):
    """Select all in editor and replace with new code."""
    click_in_window(win, rel_x=0.5, rel_y=0.5)
    time.sleep(0.3)
    hotkey("ctrl", "a")
    time.sleep(0.2)
    type_text(code)


# ─── Isabelle Helpers

def wait_for_isabelle_ready(win, timeout=90, poll_interval=6):
    """Poll the screen with the Vision chat to check if Isabelle is done."""
    print("Waiting for Isabelle to finish processing...")
    start = time.time()
    while time.time() - start < timeout:
        region = (win.left, win.top, win.width, win.height)
        img = screenshot(region)
        response = chat_vision(
            img,
            "Is Isabelle still processing (parsing, loading, checking) or "
            "is it finished/ready? Reply with ONLY 'READY' or 'BUSY' as the "
            "first word, then a brief reason.",
        )
        if "READY" in response.upper().split("\n")[0]:
            print("Isabelle appears ready.")
            return True
        elapsed = int(time.time() - start)
        print(f"  Still processing... ({elapsed}s elapsed)")
        time.sleep(poll_interval)
    print("Timed out waiting for Isabelle.")
    return False


def get_screen_description(win) -> str:
    """Take a screenshot and get a text description from the Vision chat."""
    region = (win.left, win.top, win.width, win.height)
    img = screenshot(region)
    return chat_vision(img)


# ─── Main Loop

def run_ai_demo():
    print("=" * 60)
    print("  Isabelle Contradiction Finder — 3-Chat Architecture")
    print("=" * 60)

    reset_all_chats()

    # ── Launch & find Isabelle ──
    launch_isabelle()
    win = find_isabelle_window()
    focus_window(win)

    # ── Initial screen read ──
    print("\n[Init] Reading initial screen state...")
    init_description = get_screen_description(win)
    print(f"[Vision] Initial state:\n{init_description}\n")

    # ── Strategist: first attack strategy ──
    print("[Init] Asking Strategist for first attack strategy...")
    strategy = chat_strategist(
        "We are starting a new session to find a genuine contradiction "
        "(proof of False) in Isabelle/HOL. The Isabelle/jEdit IDE is open "
        "with the default Scratch theory.\n\n"
        f"Current screen state:\n{init_description}\n\n"
        "Propose your FIRST attack strategy. Be specific and detailed about "
        "what Isabelle constructs to use and why this might break soundness. "
        "Remember: no sorry, no oops, no trivial axiom of False."
    )
    print(f"[Strategist] Strategy:\n{strategy}\n")

    # ── Coder: implement the strategy ──
    print("[Init] Asking Coder to implement the strategy...")
    code_raw = chat_coder(
        f"Implement the following strategy as a complete Isabelle theory:\n\n"
        f"{strategy}\n\n"
        "Output ONLY the raw Isabelle theory code. Theory name must be 'Scratch'. "
        "Must import Main. No sorry. No oops. No markdown fences."
    )
    current_code = sanitize_code(code_raw)
    print(f"[Coder] Theory:\n{current_code}\n")

    # ── Type into Isabelle ──
    type_code_into_editor(win, current_code)
    wait_for_isabelle_ready(win, timeout=120)

    # ─── Main Loop
    iteration = 0
    while True:
        iteration += 1
        print(f"\n{'='*60}")
        print(f"  ITERATION {iteration}")
        print(f"{'='*60}")

        # ── Step A: Vision reads the screen (one-shot, no history)
        region = (win.left, win.top, win.width, win.height)
        img = screenshot(region, save_path=SCREENSHOT_DIR + rf"\screenshot_iter_{iteration}.png")

        screen_desc = chat_vision(
            img,
            "Describe the Isabelle/jEdit screenshot in detail. For each lemma "
            "or theorem visible, report whether it is proven (green/blue), "
            "errored (red), or unprocessed. Quote any error messages you can read. "
            "Report the prover status. Does any line successfully prove False "
            "WITHOUT using sorry or oops?"
        )
        print(f"[Vision] Screen description:\n{screen_desc}\n")

        # ── Step B: Strategist evaluates (text-only, gets vision description)
        evaluation = chat_strategist(
            f"ITERATION {iteration} — Here is what the screen looks like after "
            f"running your last strategy:\n\n"
            f"--- SCREEN DESCRIPTION ---\n{screen_desc}\n--- END ---\n\n"
            f"The code that was typed:\n```isabelle\n{current_code}\n```\n\n"
            "Based on this feedback:\n"
            "1. Did it work? Was False proven without sorry/oops?\n"
            "   - If YES and there are no errors and no sorry/oops in the code, "
            "respond with EXACTLY 'VERDICT: CONTRADICTION_FOUND' as the first line.\n"
            "   - If the system appears hung/frozen, respond with "
            "'VERDICT: SYSTEM_HANG' as the first line.\n"
            "2. If it didn't work, ANALYZE why it failed. What specific errors "
            "did Isabelle produce?\n"
            "3. Then propose your NEXT strategy. It MUST be DIFFERENT from all "
            "previous attempts. Explain the new approach in detail.\n\n"
            "Start your response with one of:\n"
            "VERDICT: CONTRADICTION_FOUND\n"
            "VERDICT: SYSTEM_HANG\n"
            "VERDICT: FAILED — <brief reason>\n"
            "Then provide your analysis and next strategy."
        )
        print(f"[Strategist] Evaluation:\n{evaluation}\n")

        # ── Check verdicts ──
        eval_upper = evaluation.upper()

        if "VERDICT: CONTRADICTION_FOUND" in eval_upper:
            if has_cheat(current_code):
                print(f"[Iter {iteration}] Strategist claims contradiction but "
                      "code has sorry/oops — overriding to FAILED.")
                evaluation = chat_strategist(
                    "CORRECTION: The code actually contains 'sorry' or 'oops', "
                    "which are cheats. This does NOT count as a contradiction. "
                    "Please propose a completely new strategy that does not "
                    "rely on sorry or oops in any way."
                )
                print(f"[Strategist] Corrected strategy:\n{evaluation}\n")
            else:
                print("!" * 60)
                print("  GENUINE CONTRADICTION FOUND!")
                print("!" * 60)
                screenshot(region, save_path=SCREENSHOT_DIR + r"\screenshot_contradiction.png")
                final = chat_strategist(
                    "CONFIRMED: A genuine proof of False was accepted by Isabelle "
                    "with no sorry, no oops, and no errors.\n\n"
                    f"The code:\n```isabelle\n{current_code}\n```\n\n"
                    "Explain in detail:\n"
                    "1. What exploit/trick was used?\n"
                    "2. Why does Isabelle's kernel accept this?\n"
                    "3. What are the implications for Isabelle's soundness?"
                )
                print(f"\n[Strategist] Final analysis:\n{final}\n")
                break

        if "VERDICT: SYSTEM_HANG" in eval_upper:
            print(f"[Iter {iteration}] System hang detected!")
            screenshot(region, save_path=SCREENSHOT_DIR + rf"\screenshot_hang_{iteration}.png")
            print(f"  Code that caused hang:\n{current_code}\n")
            type_code_into_editor(win, "theory Scratch\n  imports Main\nbegin\nend")
            current_code = "theory Scratch\n  imports Main\nbegin\nend"
            time.sleep(10)

        # ── Step C: Coder writes new code based on strategist's analysis
        print(f"[Iter {iteration}] Asking Coder for new code...")
        code_raw = chat_coder(
            f"The previous code had issues. Here is the strategist's analysis "
            f"and new strategy:\n\n"
            f"--- STRATEGIST ---\n{evaluation}\n--- END ---\n\n"
            f"Previous code was:\n```isabelle\n{current_code}\n```\n\n"
            "Write a COMPLETE new Isabelle theory implementing the strategist's "
            "new approach. Theory name: 'Scratch'. Import Main. "
            "No sorry. No oops. No markdown fences. Output ONLY the code."
        )
        new_code = sanitize_code(code_raw)
        print(f"[Coder] New theory:\n{new_code}\n")

        # ── Step D: Type into Isabelle
        type_code_into_editor(win, new_code)
        current_code = new_code

        wait_for_isabelle_ready(win, timeout=120)

    print("\nContradiction finder loop complete!")


if __name__ == "__main__":
    run_ai_demo()
