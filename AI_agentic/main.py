import time
from config import SCREENSHOT_DIR
from ai_chats import chat_strategist, chat_coder, chat_vision, reset_all_chats, sanitize_code, has_cheat
from gui import launch_isabelle, find_isabelle_window, focus_window, screenshot, type_code_into_editor, wait_for_isabelle_ready, get_screen_description

BLANK_THEORY = "theory Scratch\n  imports Main\nbegin\nend"


def run_ai_demo():
    """Run the contradiction-finder loop: Strategist proposes attacks, Coder writes theories,
    Vision reads the IDE screen, and the loop continues until a genuine proof of False is found."""
    print("  Isabelle Contradiction Finder — 3-Chat Architecture")

    reset_all_chats()
    launch_isabelle()
    win = find_isabelle_window()
    focus_window(win)

    init_description = get_screen_description(win)
    print(f"[Vision] Initial state:\n{init_description}\n")

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

    current_code = sanitize_code(chat_coder(
        f"Implement the following strategy as a complete Isabelle theory:\n\n{strategy}\n\n"
        "Output ONLY the raw Isabelle theory code. Theory name must be 'Scratch'. "
        "Must import Main. No sorry. No oops. No markdown fences."
    ))
    print(f"[Coder] Theory:\n{current_code}\n")

    type_code_into_editor(win, current_code)
    wait_for_isabelle_ready(win, timeout=120)

    iteration = 0
    while True:
        iteration += 1
        print(f"\n  ITERATION {iteration}\n")

        region = (win.left, win.top, win.width, win.height),
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

        eval_upper = evaluation.upper()

        if "VERDICT: CONTRADICTION_FOUND" in eval_upper:
            if has_cheat(current_code):
                print(f"[Iter {iteration}] Strategist claims contradiction but code has sorry/oops — overriding to FAILED.")
                evaluation = chat_strategist(
                    "CORRECTION: The code actually contains 'sorry' or 'oops', "
                    "which are cheats. This does NOT count as a contradiction. "
                    "Please propose a completely new strategy that does not rely on sorry or oops in any way."
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
            type_code_into_editor(win, BLANK_THEORY)
            current_code = BLANK_THEORY
            time.sleep(10)

        current_code = sanitize_code(chat_coder(
            f"The previous code had issues. Here is the strategist's analysis and new strategy:\n\n"
            f"--- STRATEGIST ---\n{evaluation}\n--- END ---\n\n"
            f"Previous code was:\n```isabelle\n{current_code}\n```\n\n"
            "Write a COMPLETE new Isabelle theory implementing the strategist's "
            "new approach. Theory name: 'Scratch'. Import Main. "
            "No sorry. No oops. No markdown fences. Output ONLY the code."
        ))
        print(f"[Coder] New theory:\n{current_code}\n")

        type_code_into_editor(win, current_code)
        wait_for_isabelle_ready(win, timeout=120)

    print("\nContradiction finder loop complete!")


if __name__ == "__main__":
    run_ai_demo()
