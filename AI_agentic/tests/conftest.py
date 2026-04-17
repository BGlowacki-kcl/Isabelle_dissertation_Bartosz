"""
conftest.py - pytest bootstrap for AI_agentic tests.
"""
import sys
import types
from unittest.mock import MagicMock

import pytest

import ai_chats


# Path setup

AGENTIC_PATH = "/home/bartek1301/workplace/isabelle/git/AI_agentic"
if AGENTIC_PATH not in sys.path:
    sys.path.insert(0, AGENTIC_PATH)


# Stub pygetwindow (raises NotImplementedError on Linux)

def _stub(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


_stub("pygetwindow", getWindowsWithTitle=MagicMock(return_value=[]))


# Shared fixtures

@pytest.fixture(autouse=True)
def _clean_histories():
    """Isolate every test: reset chat histories before and after."""
    ai_chats.reset_all_chats()
    yield
    ai_chats.reset_all_chats()


@pytest.fixture
def mock_client(monkeypatch):
    """Replace ai_chats.client with a fresh MagicMock for each test."""
    mc = MagicMock()
    monkeypatch.setattr(ai_chats, "client", mc)
    return mc


@pytest.fixture
def make_response():
    """Factory that builds a minimal Mistral-shaped response object."""
    def _make(content="reply text"):
        resp = MagicMock()
        resp.choices[0].message.content = content
        return resp
    return _make


@pytest.fixture
def tiny_image():
    """A real 4x4 RGB PIL image usable in chat_vision calls."""
    from PIL import Image
    return Image.new("RGB", (4, 4), color=(128, 0, 255))
