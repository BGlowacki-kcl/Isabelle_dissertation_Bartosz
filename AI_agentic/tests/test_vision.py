"""
test_vision.py - chat_vision encoding, prompt handling, and statelessness.

The Vision agent is intentionally stateless: it reads a single screenshot and
reports what it sees.  It must not pollute the strategist/coder history lists,
which would inject noisy screen descriptions into strategy/code conversations.
The image-to-base64 pipeline must also produce valid PNG-encoded data.
"""
import base64
import io
from PIL import Image
import ai_chats


def _last_call_messages(mock_client):
    _, kwargs = mock_client.chat.complete.call_args
    return kwargs["messages"]


# Image encoding 

def test_image_encoded_as_base64_png(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_vision(tiny_image)

    messages = _last_call_messages(mock_client)
    user_content = messages[1]["content"]

    image_part = next(p for p in user_content if p["type"] == "image_url")
    url = image_part["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")

    b64_data = url.split(",", 1)[1]
    raw = base64.b64decode(b64_data)
    recovered = Image.open(io.BytesIO(raw))
    assert recovered.size == tiny_image.size

def test_image_preserves_pixel_content(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_vision(tiny_image)

    messages = _last_call_messages(mock_client)
    url = messages[1]["content"][1]["image_url"]["url"]
    raw = base64.b64decode(url.split(",", 1)[1])
    recovered = Image.open(io.BytesIO(raw)).convert("RGB")
    assert recovered.getpixel((0, 0)) == tiny_image.getpixel((0, 0))


# Prompt handling

def test_vision_uses_custom_prompt_when_provided(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_vision(tiny_image, prompt="Is Isabelle ready?")

    messages = _last_call_messages(mock_client)
    text_part = next(p for p in messages[1]["content"] if p["type"] == "text")
    assert text_part["text"] == "Is Isabelle ready?"

def test_vision_uses_default_prompt_when_none(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_vision(tiny_image, prompt=None)

    messages = _last_call_messages(mock_client)
    text_part = next(p for p in messages[1]["content"] if p["type"] == "text")
    assert "Isabelle" in text_part["text"] or "screenshot" in text_part["text"].lower()

def test_vision_uses_default_prompt_when_empty_string(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_vision(tiny_image, prompt="")

    messages = _last_call_messages(mock_client)
    text_part = next(p for p in messages[1]["content"] if p["type"] == "text")
    assert len(text_part["text"]) > 0

def test_vision_user_message_has_text_and_image_parts(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_vision(tiny_image)

    messages = _last_call_messages(mock_client)
    user_parts = messages[1]["content"]
    types = {p["type"] for p in user_parts}
    assert "text" in types
    assert "image_url" in types


# Statelessness

def test_vision_does_not_add_to_strategist_history(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response("screen desc")
    ai_chats.chat_vision(tiny_image)
    assert ai_chats._strategist_history == []

def test_vision_does_not_add_to_coder_history(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response("screen desc")
    ai_chats.chat_vision(tiny_image)
    assert ai_chats._coder_history == []

def test_vision_sends_no_prior_history(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_vision(tiny_image)
    messages = _last_call_messages(mock_client)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"

def test_vision_returns_model_reply(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response("READY — no errors visible")
    result = ai_chats.chat_vision(tiny_image)
    assert result == "READY — no errors visible"
