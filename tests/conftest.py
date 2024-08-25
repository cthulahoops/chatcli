import pytest
from pathlib import Path
from click.testing import CliRunner
import chatcli_gpt.models
import json
from chatcli_gpt.cli import cli


@pytest.fixture(autouse=True)
def _no_http_requests(monkeypatch):
    def urlopen_mock(self, method, url, *_args, **_kwargs):
        raise RuntimeError(
            f"The test was about to {method} {self.scheme}://{self.host}{url}"
        )

    monkeypatch.setattr(
        "urllib3.connectionpool.HTTPConnectionPool.urlopen", urlopen_mock
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
        yield {
            "model": model,
            "choices": [{"delta": {"role": "assistant"}, "index": 0}],
        }
        first = True
        for word in ai(message, model).split(" "):
            yield {
                "choices": [
                    {"delta": {"content": word if first else " " + word}, "index": 0}
                ]
            }
            first = False

    def advanced_ai(model, messages, *, stream=False, api_key=None, api_base=None):
        if stream:
            return (x for x in streaming_ai(model, messages[-1]["content"]))
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": ai(messages[-1]["content"], model),
                    },
                },
            ],
            "usage": {"total_tokens": 41},
        }

    async def async_advanced_ai(*args, **kwargs):
        async def agen(gen):
            for x in gen:
                yield x

        return agen(advanced_ai(*args, **kwargs))

    mocker.patch("openai.ChatCompletion.create", advanced_ai)
    mocker.patch("openai.ChatCompletion.acreate", async_advanced_ai)
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
