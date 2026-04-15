import os
from mistralai import Mistral

ISABELLE_EXE = r"C:\Isabelle\Isabelle2025-2\Isabelle2025-2.exe"
SCREENSHOT_DIR = r"C:\Isabelle"

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_MODEL = "mistral-large-latest"

client = Mistral(api_key=MISTRAL_API_KEY)

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
