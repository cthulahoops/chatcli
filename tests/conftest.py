import pytest
from pathlib import Path
from click.testing import CliRunner
import chatcli_gpt.models
import json
from chatcli_gpt.cli import cli
from openai import OpenAI, AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessage, ChatCompletionChunk

from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_chunk import ChoiceDelta, Choice as ChunkChoice


@pytest.fixture(autouse=True)
def _no_http_requests(monkeypatch):
    def urlopen_mock(self, method, url, *_args, **_kwargs):
        raise RuntimeError(
            f"The test was about to {method} {self.scheme}://{self.host}{url}"
        )

    monkeypatch.setattr(
        "urllib3.connectionpool.HTTPConnectionPool.urlopen", urlopen_mock
    )

    def mock_send(*_args, **_kwargs):
        raise RuntimeError("HTTP requests are disabled in this test.")

    monkeypatch.setattr("httpx.Client.send", mock_send)
    monkeypatch.setattr("httpx.AsyncClient.send", mock_send)


def to_chunks(model, tokens):
    yield ChatCompletionChunk(
        id="chatcmpl-123",
        object="chat.completion.chunk",
        created=1677652288,
        model=model,
        choices=[
            ChunkChoice(
                delta=ChoiceDelta(
                    content="",
                    role="assistant",
                ),
                index=0,
                finish_reason=None,
            )
        ],
    )

    for token in tokens:
        yield ChatCompletionChunk(
            id="chatcmpl-123",
            object="chat.completion.chunk",
            created=1677652288,
            model=model,
            choices=[
                ChunkChoice(
                    delta=ChoiceDelta(
                        content=token,
                        function_call=None,
                        refusal=None,
                        role="assistant",
                    ),
                    index=0,
                    finish_reason="stop",
                )
            ],
        )


@pytest.fixture(autouse=True)
def _fake_assistant(mocker):
    def ai(message, model):
        if model == "name_is_alice":
            return "My name is Alice."
        if message.startswith("evaluate: "):
            message = message.replace("evaluate: ", "")
            return f"EVALUATE:\n```python\n{message}```"
        return message.upper()

    def streaming_ai(model, message):
        tokens = ai(message, model).split(" ")
        tokens[1:] = [" " + token for token in tokens[1:]]

        yield from to_chunks(model, tokens)

    def advanced_ai(model, messages, *, stream=False):
        if stream:
            return (x for x in streaming_ai(model, messages[-1]["content"]))
        return ChatCompletion(
            id="chatcmpl-123",
            object="chat.completion",
            created=1677652288,
            model=model,
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant", content=ai(messages[-1]["content"], model)
                    ),
                    finish_reason="stop",
                )
            ],
            usage={"prompt_tokens": 11, "completion_tokens": 10, "total_tokens": 41},
        )

    async def async_advanced_ai(*args, **kwargs):
        async def agen(gen):
            for x in gen:
                yield x

        return agen(advanced_ai(*args, **kwargs))

    mock_client = mocker.Mock()
    mock_client.chat.completions.create = mocker.Mock(side_effect=advanced_ai)
    mocker.patch("openai.OpenAI", return_value=mock_client)

    mock_async_client = mocker.Mock()
    mock_async_client.chat.completions.create = mocker.AsyncMock(
        side_effect=async_advanced_ai
    )
    mocker.patch("openai.AsyncOpenAI", return_value=mock_async_client)

    mocker.patch(
        "chatcli_gpt.conversation.completion_usage",
        return_value={"prompt_tokens": 11, "completion_tokens": 10, "total_tokens": 41},
    )


@pytest.fixture()
def chatcli(mocker):
    mocker.patch("chatcli_gpt.models.MODEL_CACHE", Path(".chatcli-models.json"))
    runner = CliRunner()
    with runner.isolated_filesystem():
        chatcli_gpt.models.MODEL_CACHE.open("w").write(
            json.dumps(
                [
                    {
                        "id": "name_is_alice",
                        "pricing": {"prompt": 0.002, "completion": 0.002},
                    }
                ]
            )
        )

        def chatcli(*args, catch_exceptions=False, expected_exit_code=0, **kwargs):
            result = runner.invoke(
                cli, *args, catch_exceptions=catch_exceptions, **kwargs
            )
            assert result.exit_code == expected_exit_code
            return result

        chatcli("init")
        yield chatcli
