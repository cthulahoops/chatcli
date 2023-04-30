import os
import signal
from unittest.mock import Mock
import pytest
from chatcli_gpt.conversation import Conversation, stream_request
import openai  # noqa: F401


def test_find_recent_message():
    conversation = Conversation(
        {
            "messages": [
                {"role": "assistant", "message": "???"},
                {"role": "user", "message": "hello"},
                {"role": "assistant", "message": "hi"},
                {"role": "user", "message": "how are you?"},
            ],
        },
    )

    def predicate(msg):
        return msg["role"] == "assistant"

    result = conversation.find(predicate)
    expected = {"role": "assistant", "message": "hi"}

    assert result == expected

    with pytest.raises(ValueError, match="No matching message found"):
        conversation.find(lambda msg: msg["role"] == "not_found")


def test_stream_interrupt(mocker):
    def stream(model, messages, stream):
        assert model == "gpt-4"
        assert messages == []
        assert stream
        yield {"model": model, "choices": [{"delta": {"role": "assistant"}, "index": 0}]}
        for word in ["a", "quick", "brown"]:
            yield {"choices": [{"delta": {"content": " " + word}, "index": 0}]}
        os.kill(os.getpid(), signal.SIGINT)
        for word in ["jumped", "over", "the"]:
            yield {"choices": [{"delta": {"content": " " + word}, "index": 0}]}

    mocker.patch("openai.ChatCompletion.create", stream)
    callback = Mock()
    response = stream_request([], "gpt-4", callback)

    assert response["choices"][0]["message"]["content"] == " a quick brown jumped"
    assert callback.call_count == 6
