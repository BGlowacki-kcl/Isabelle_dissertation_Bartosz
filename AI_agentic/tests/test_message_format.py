"""
test_message_format.py - Verify the exact message structure sent to Mistral.

The Mistral API is strict about message ordering: system must come first,
followed by alternating user/assistant history, then the new user message.
Getting this wrong silently degrades response quality.
"""
import pytest
import ai_chats
import config


def _last_call_messages(mock_client):
    """Extract the 'messages' kwarg from the most recent client.chat.complete call."""
    _, kwargs = mock_client.chat.complete.call_args
    return kwargs["messages"]

def _last_call_temperature(mock_client):
    _, kwargs = mock_client.chat.complete.call_args
    return kwargs["temperature"]

def _last_call_model(mock_client):
    _, kwargs = mock_client.chat.complete.call_args
    return kwargs["model"]


# Message ordering

def test_system_prompt_is_first_message(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_strategist("test prompt")
    messages = _last_call_messages(mock_client)
    assert messages[0]["role"] == "system"

def test_new_user_prompt_is_last_message(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_strategist("the-new-prompt")
    messages = _last_call_messages(mock_client)
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "the-new-prompt"

def test_history_is_sandwiched_between_system_and_user(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response("reply-1")
    ai_chats.chat_strategist("prompt-1")
    mock_client.chat.complete.return_value = make_response("reply-2")
    ai_chats.chat_strategist("prompt-2")

    messages = _last_call_messages(mock_client)
    assert len(messages) == 4
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "prompt-1"
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "reply-1"
    assert messages[3]["role"] == "user"
    assert messages[3]["content"] == "prompt-2"

def test_three_turn_message_layout(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response("r")
    ai_chats.chat_coder("c1")
    ai_chats.chat_coder("c2")
    ai_chats.chat_coder("c3")
    messages = _last_call_messages(mock_client)
    assert len(messages) == 6
    roles = [m["role"] for m in messages]
    assert roles == ["system", "user", "assistant", "user", "assistant", "user"]


# Correct system prompts per agent

def test_strategist_uses_strategist_system_prompt(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_strategist("p")
    messages = _last_call_messages(mock_client)
    assert messages[0]["content"] == config.STRATEGIST_SYSTEM

def test_coder_uses_coder_system_prompt(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_coder("p")
    messages = _last_call_messages(mock_client)
    assert messages[0]["content"] == config.CODER_SYSTEM

def test_vision_uses_vision_system_prompt(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_vision(tiny_image)
    messages = _last_call_messages(mock_client)
    assert messages[0]["content"] == config.VISION_SYSTEM


# Temperature discipline

def test_strategist_default_temperature_is_0_4(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_strategist("p")
    assert _last_call_temperature(mock_client) == pytest.approx(0.4)

def test_coder_default_temperature_is_0_2(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_coder("p")
    assert _last_call_temperature(mock_client) == pytest.approx(0.2)

def test_vision_default_temperature_is_0_1(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_vision(tiny_image)
    assert _last_call_temperature(mock_client) == pytest.approx(0.1)

def test_correct_model_is_sent(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_strategist("p")
    assert _last_call_model(mock_client) == config.MISTRAL_MODEL

def test_custom_temperature_overrides_default(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response()
    ai_chats.chat_strategist("p", temperature=0.99)
    assert _last_call_temperature(mock_client) == pytest.approx(0.99)
