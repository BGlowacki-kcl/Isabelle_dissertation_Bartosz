"""
test_history.py - Conversation history accumulation, persistence, and isolation.

The multi-agent loop depends on each agent maintaining its own conversation
context across calls.  If history is corrupted or shared incorrectly the
strategist and coder lose context and the feedback loop breaks down.
"""
import ai_chats


# History accumulates across calls

def test_single_strategist_call_appends_two_entries(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response("strategy A")
    ai_chats.chat_strategist("first prompt")
    assert len(ai_chats._strategist_history) == 2

def test_multiple_strategist_calls_accumulate(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response("reply")
    ai_chats.chat_strategist("prompt 1")
    ai_chats.chat_strategist("prompt 2")
    ai_chats.chat_strategist("prompt 3")
    assert len(ai_chats._strategist_history) == 6 

def test_history_entries_have_correct_roles(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response("the reply")
    ai_chats.chat_strategist("my prompt")
    roles = [m["role"] for m in ai_chats._strategist_history]
    assert roles == ["user", "assistant"]

def test_history_user_entry_contains_original_prompt(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response("reply")
    ai_chats.chat_strategist("unique-prompt-xyz")
    user_entry = ai_chats._strategist_history[0]
    assert user_entry["role"] == "user"
    assert user_entry["content"] == "unique-prompt-xyz"

def test_history_assistant_entry_contains_model_reply(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response("model-reply-abc")
    ai_chats.chat_strategist("any prompt")
    assistant_entry = ai_chats._strategist_history[1]
    assert assistant_entry["role"] == "assistant"
    assert assistant_entry["content"] == "model-reply-abc"


# Agent isolation

def test_strategist_call_leaves_coder_history_empty(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response("strat")
    ai_chats.chat_strategist("propose something")
    assert len(ai_chats._coder_history) == 0

def test_coder_call_leaves_strategist_history_empty(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response("code")
    ai_chats.chat_coder("write something")
    assert len(ai_chats._strategist_history) == 0

def test_coder_history_independent_of_strategist(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response("X")
    ai_chats.chat_strategist("s-prompt")
    ai_chats.chat_coder("c-prompt")
    assert len(ai_chats._strategist_history) == 2
    assert len(ai_chats._coder_history) == 2
    strat_user = ai_chats._strategist_history[0]["content"]
    coder_user = ai_chats._coder_history[0]["content"]
    assert strat_user == "s-prompt"
    assert coder_user == "c-prompt"


# Vision is stateless

def test_vision_call_does_not_modify_strategist_history(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response("screen description")
    ai_chats.chat_vision(tiny_image)
    assert len(ai_chats._strategist_history) == 0

def test_vision_call_does_not_modify_coder_history(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response("screen description")
    ai_chats.chat_vision(tiny_image)
    assert len(ai_chats._coder_history) == 0

def test_repeated_vision_calls_remain_stateless(mock_client, make_response, tiny_image):
    mock_client.chat.complete.return_value = make_response("description")
    for _ in range(5):
        ai_chats.chat_vision(tiny_image)
    assert len(ai_chats._strategist_history) == 0
    assert len(ai_chats._coder_history) == 0


# reset_all_chats

def test_reset_clears_strategist_history(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response("reply")
    ai_chats.chat_strategist("p1")
    ai_chats.chat_strategist("p2")
    ai_chats.reset_all_chats()
    assert ai_chats._strategist_history == []

def test_reset_clears_coder_history(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response("reply")
    ai_chats.chat_coder("p1")
    ai_chats.reset_all_chats()
    assert ai_chats._coder_history == []

def test_history_functional_after_reset(mock_client, make_response):
    mock_client.chat.complete.return_value = make_response("reply")
    ai_chats.chat_strategist("before reset")
    ai_chats.reset_all_chats()
    ai_chats.chat_strategist("after reset")
    assert len(ai_chats._strategist_history) == 2
    assert ai_chats._strategist_history[0]["content"] == "after reset"
