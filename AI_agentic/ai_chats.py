import base64
import io
from PIL import Image
from config import client, MISTRAL_MODEL, STRATEGIST_SYSTEM, CODER_SYSTEM, VISION_SYSTEM

_strategist_history: list[dict] = []
_coder_history: list[dict] = []


def _chat(system: str, history: list[dict], prompt: str, temperature: float, label: str) -> str:
    """Send a prompt to the model with full conversation history and append both turns to history."""
    user_msg = {"role": "user", "content": prompt}
    messages = [{"role": "system", "content": system}, *history, user_msg]
    response = client.chat.complete(model=MISTRAL_MODEL, messages=messages, temperature=temperature)
    reply = response.choices[0].message.content
    history.append(user_msg)
    history.append({"role": "assistant", "content": reply})
    print(f"[{label}] Response ({len(reply)} chars)")
    return reply


def chat_strategist(prompt: str, temperature: float = 0.4) -> str:
    return _chat(STRATEGIST_SYSTEM, _strategist_history, prompt, temperature, "Strategist")


def chat_coder(prompt: str, temperature: float = 0.2) -> str:
    return _chat(CODER_SYSTEM, _coder_history, prompt, temperature, "Coder")


def chat_vision(img: Image.Image, prompt: str | None = None, temperature: float = 0.1) -> str:
    """Encode a PIL image as base64 and send it with an optional prompt to the vision model."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
    if not prompt:
        prompt = "Describe exactly what you see on this Isabelle/jEdit screenshot."
    messages = [
        {"role": "system", "content": VISION_SYSTEM},
        {"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]},
    ]
    response = client.chat.complete(model=MISTRAL_MODEL, messages=messages, temperature=temperature)
    reply = response.choices[0].message.content
    print(f"[Vision] Response ({len(reply)} chars)")
    return reply


def reset_all_chats():
    global _strategist_history, _coder_history
    _strategist_history.clear()
    _coder_history.clear()
    print("[Reset] All chat histories cleared.")


def sanitize_code(code: str) -> str:
    """Strip markdown code fences from model output and warn if sorry/oops are present."""
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
    low = code.lower()
    return "sorry" in low or "oops" in low
