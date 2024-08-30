import asyncio
from io import StringIO
import pytest
from chatcli_gpt.conversation import (
    Conversation,
    stream_request,
    accumulate_streaming_response,
)
import openai  # noqa: F401

from .conftest import to_chunks


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


def mock_acreate(mocker, stream):
    mock_async_client = mocker.Mock()
    mock_async_client.chat.completions.create = mocker.AsyncMock(side_effect=stream)
    mocker.patch("openai.AsyncOpenAI", return_value=mock_async_client)


def test_stream_interrupt(mocker):
    async def astream(model, *_args, **_kwargs):
        chunks = to_chunks(model, ["a ", "quick ", "brown ", "fox ", "jumped "])

        for _ in range(4):
            yield next(chunks)
        raise asyncio.CancelledError

        async for chunk in chunks:
            yield chunk

    mock_acreate(mocker, astream)

    buffer = StringIO()

    result = asyncio.run(stream_request([], "gpt-4", buffer.write))

    assert result.model == "gpt-4"

    assert buffer.getvalue() == "a quick brown "


@pytest.mark.asyncio()
async def test_accumulate_streaming_response_empty_iterator():
    iterator = async_gen(to_chunks("test_model", []))
    result = await accumulate_streaming_response(iterator)
    assert result.choices[0].message.content == ""


@pytest.mark.asyncio()
async def test_accumulate_streaming_response_single_delta(stream_tokens):
    iterator = async_gen(to_chunks("test_model", ["".join(stream_tokens)]))
    result = await accumulate_streaming_response(iterator)
    assert result.choices[0].message.content == "".join(stream_tokens)


async def async_gen(iteratable):
    for item in iteratable:
        yield item


@pytest.fixture()
def stream_tokens():
    return ["Hello, ", "how ", "are ", "you?"]


@pytest.mark.asyncio()
async def test_accumulate_multiple_deltas(stream_tokens):
    iterator = async_gen(to_chunks("test_model", stream_tokens))
    result = await accumulate_streaming_response(iterator)
    assert result.choices[0].message.content == "".join(stream_tokens)


@pytest.mark.asyncio()
async def test_callback_gets_message(stream_tokens):
    callback_tokens = []
    iterator = async_gen(to_chunks("test_model", stream_tokens))
    result = await accumulate_streaming_response(iterator, callback_tokens.append)
    assert result.choices[0].message.content == "".join(stream_tokens)

    assert callback_tokens == stream_tokens
