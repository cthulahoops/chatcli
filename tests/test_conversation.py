import os
import signal
from unittest.mock import Mock
import pytest
from chatcli_gpt.conversation import Conversation, stream_request, accumulate_deltas
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
    def stream(model, messages, stream, **_kwargs):
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
    assert callback.call_count == 4


def test_accumulate_deltas_empty_iterator():
    iterator = []
    callback = None
    result = accumulate_deltas(iterator, callback)
    assert result == {}


@pytest.fixture()
def streaming_data():
    return [
        {
            "model": "fake_data",
            "choices": [
                {"index": 0, "delta": {"role": "user", "content": "Hello, "}},
                {"index": 1, "delta": {"role": "user", "content": "write "}},
                {"index": 2, "delta": {"role": "user", "content": "write "}},
            ],
        },
        {
            "choices": [
                {"index": 0, "delta": {"content": "how "}},
                {"index": 1, "delta": {"content": "a "}},
                {"index": 2, "delta": {"role": "user", "content": "a "}},
            ],
        },
        {
            "choices": [
                {"index": 0, "delta": {"content": "are "}},
                {"index": 1, "delta": {"content": "simple "}},
                {"index": 2, "delta": {"role": "user", "content": "poem"}},
            ],
        },
        {
            "choices": [
                {"index": 0, "delta": {"content": "you?"}},
                {"index": 1, "delta": {"role": "user", "content": "function "}},
            ],
        },
        {
            "choices": [
                {"index": 1, "delta": {"role": "user", "content": "in "}},
            ],
        },
        {
            "choices": [
                {"index": 1, "delta": {"role": "user", "content": "Python"}},
            ],
        },
    ]


def test_accumulate_deltas_single_delta():
    iterator = [
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "user",
                        "content": "Hello, how are you?",
                    },
                },
            ],
        },
    ]
    callback = None
    result = accumulate_deltas(iterator, callback)
    expected_result = {
        "choices": [
            {
                "message": {
                    "role": "user",
                    "content": "Hello, how are you?",
                },
            },
        ],
    }
    assert result == expected_result


def test_accumulate_multiple_deltas(streaming_data):
    for message in streaming_data:
        message["choices"] = [item for item in message["choices"] if item["index"] == 0]

    streaming_data = [item for item in streaming_data if item["choices"]]

    callback = None
    result = accumulate_deltas(streaming_data, callback)
    expected_result = {
        "model": "fake_data",
        "choices": [
            {
                "message": {
                    "role": "user",
                    "content": "Hello, how are you?",
                },
            },
        ],
    }
    assert result == expected_result


def test_accumulate_multiple_choices(streaming_data):
    callback = None
    result = accumulate_deltas(streaming_data, callback)
    expected_result = {
        "model": "fake_data",
        "choices": [
            {
                "message": {
                    "role": "user",
                    "content": "Hello, how are you?",
                },
            },
            {
                "message": {
                    "role": "user",
                    "content": "write a simple function in Python",
                },
            },
            {
                "message": {
                    "role": "user",
                    "content": "write a poem",
                },
            },
        ],
    }
    assert result == expected_result


def test_callback_gets_message(streaming_data):
    from io import StringIO

    buffer = StringIO()

    accumulate_deltas(streaming_data, buffer.write)

    assert buffer.getvalue() == "Hello, how are you?"
