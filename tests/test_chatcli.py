import os
from unittest.mock import patch
import pytest
import json
from click.testing import CliRunner
from chatcli_gpt.chatcli import cli, find_recent_message


@pytest.fixture(autouse=True)
def fake_assistant(mocker):
    def ai(message):
        if message.startswith("evaluate: "):
            message = message.replace("evaluate: ", "")
            return f"EVALUATE:\n```python\n{message}```"
        return message.upper()

    def streaming_ai(model, message):
        yield {"model": model, "choices": [{"delta": {"role": "assistant"}, "index": 0}]}
        for word in ai(message).split(" "):
            yield {"choices": [{"delta": {"content": " " + word}, "index": 0}]}

    def advanced_ai(model, messages, stream=False):
        if stream:
            return (x for x in streaming_ai(model, messages[-1]["content"]))
        return {
            "choices": [{"message": {"role": "assistant", "content": ai(messages[-1]["content"])}}],
            "usage": {"total_tokens": 41},
        }

    mocker.patch("chatcli_gpt.chatcli.openai.ChatCompletion.create", advanced_ai)


def test_chat_code():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(
            cli, ["chat", "--quick", "-p", "code"], input="Say hello in python", catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "SAY HELLO IN PYTHON" in result.output


def test_show_short():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(cli, ["chat", "-q"], input="What is your name?", catch_exceptions=False)
        result = runner.invoke(cli, ["show", "-s"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "What is your name?" not in result.output
        assert "WHAT IS YOUR NAME?" in result.output


def test_show_long(mocker):
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(cli, ["chat", "-q"], input="What is your name?", catch_exceptions=False)
        result = runner.invoke(cli, ["show", "-l"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "expert linux user" in result.output
        assert "What is your name?" in result.output
        assert "WHAT IS YOUR NAME?" in result.output


def test_log(mocker):
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(
            cli, ["chat", "--quick", "-p", "concise"], input="What is your name?", catch_exceptions=False
        )
        result = runner.invoke(cli, ["chat", "--quick", "-c"], input="What is your quest?", catch_exceptions=False)
        result = runner.invoke(cli, ["log"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "2: What is your name?" in result.output
        assert "1: What is your quest?" in result.output


def test_chat_log_search():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(
            cli, ["chat", "--quick", "-p", "concise"], input="What is your name?", catch_exceptions=False
        )
        result = runner.invoke(cli, ["chat", "--quick", "-c"], input="What is your quest?", catch_exceptions=False)
        result = runner.invoke(cli, ["log", "-s", "name"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "2: What is your name?" in result.output
        assert "1: What is your quest?" not in result.output


def test_usage():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(cli, ["chat"], input="What is your name?", catch_exceptions=False)
        result = runner.invoke(cli, ["chat"], input="What is your name?", catch_exceptions=False)
        result = runner.invoke(cli, ["usage"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Tokens: 82" in result.output
        assert "Cost: $0.00" in result.output


def test_tag_usage():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(cli, ["chat"], input="What is your name?", catch_exceptions=False)
        result = runner.invoke(cli, ["chat"], input="What is your name?", catch_exceptions=False)
        result = runner.invoke(cli, ["tag", "test_tag"], catch_exceptions=False)
        result = runner.invoke(cli, ["usage"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Tokens: 82" in result.output
        assert "Cost: $0.00" in result.output


def test_untag_usage():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(cli, ["chat"], input="What is your name?", catch_exceptions=False)
        result = runner.invoke(cli, ["chat"], input="What is your name?", catch_exceptions=False)
        result = runner.invoke(cli, ["untag", "test_tag"], catch_exceptions=False)
        result = runner.invoke(cli, ["usage"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Tokens: 82" in result.output
        assert "Cost: $0.00" in result.output


def test_chat_retry():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(cli, ["chat"], input="What is your name?", catch_exceptions=False)
        result = runner.invoke(cli, ["chat", "--quick", "--retry"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "WHAT IS YOUR NAME?" in result.output


def test_tag():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(
            cli, ["chat", "--quick", "-p", "concise"], input="What is your name?", catch_exceptions=False
        )
        result = runner.invoke(cli, ["tag", "test_tag"], catch_exceptions=False)
        assert result.exit_code == 0
        result = runner.invoke(cli, ["log", "-t", "test_tag"], catch_exceptions=False)
        assert result.exit_code == 0
        assert len(result.output.splitlines()) == 1
        assert "test_tag" in result.output


def test_tags():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(
            cli, ["chat", "--quick", "-p", "concise"], input="What is your name?", catch_exceptions=False
        )
        result = runner.invoke(cli, ["tag", "test_tag"], catch_exceptions=False)
        result = runner.invoke(cli, ["tag", "test_tag2"], catch_exceptions=False)
        result = runner.invoke(cli, ["tags"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "test_tag" in result.output
        assert "test_tag2" in result.output


def test_tag_delete():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(
            cli, ["chat", "--quick", "-p", "concise"], input="What is your name?", catch_exceptions=False
        )
        result = runner.invoke(cli, ["tag", "test_tag"], catch_exceptions=False)
        result = runner.invoke(cli, ["untag", "test_tag"], catch_exceptions=False)
        assert result.exit_code == 0
        result = runner.invoke(cli, ["log", "-l", "1"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "test_tag" not in result.output


def test_show_tag():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(
            cli, ["chat", "--quick", "-p", "concise"], input="What is your name?", catch_exceptions=False
        )
        result = runner.invoke(cli, ["tag", "test_tag"], catch_exceptions=False)
        result = runner.invoke(cli, ["show-tag"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "test_tag" in result.output


def test_current_tag_follows_conversation():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(
            cli, ["chat", "--quick", "-p", "concise"], input="What is your name?", catch_exceptions=False
        )
        result = runner.invoke(cli, ["tag", "test_tag"], catch_exceptions=False)
        result = runner.invoke(
            cli, ["chat", "--continue", "--quick"], input="What is your quest?", catch_exceptions=False
        )
        result = runner.invoke(cli, ["show-tag"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "test_tag" in result.output


def test_add_personality():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(
            cli, ["add", "-p", "test_personality"], input="You are a test personality.", catch_exceptions=False
        )
        assert result.exit_code == 0
        result = runner.invoke(cli, ["log"], catch_exceptions=False)
        assert "^test_personality" in result.output


def test_add_personality_with_pyeval_and_evaluate():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(
            cli,
            ["add", "-p", "test_personality", "--plugin", "pyeval"],
            input="You are a test personality.",
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        result = runner.invoke(cli, ["log", "--plugins"], catch_exceptions=False)
        assert "^test_personality" in result.output


def test_default_personality_cannot_evaluate():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(cli, ["chat"], input="evaluate: 6 * 7", catch_exceptions=False)

        assert result.exit_code == 0
        assert "42" not in result.output


def test_pyeval():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(cli, ["chat", "-p", "pyeval"], input="evaluate: 6 * 7", catch_exceptions=False)

        assert result.exit_code == 0
        assert "42" in result.output


def test_find_recent_message():
    conversation = {
        "messages": [
            {"sender": "assistant", "message": "???"},
            {"sender": "user", "message": "hello"},
            {"sender": "assistant", "message": "hi"},
            {"sender": "user", "message": "how are you?"},
        ]
    }

    def predicate(msg):
        return msg["sender"] == "assistant"

    result = find_recent_message(predicate, conversation)
    expected = {"sender": "assistant", "message": "hi"}

    assert result == expected


def test_parents_log():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init"], catch_exceptions=False)
        os.mkdir("subdir")
        os.chdir("subdir")
        runner.invoke(cli, ["log"], catch_exceptions=False)


def test_no_log():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with pytest.raises(FileNotFoundError):
            runner.invoke(cli, ["log"], catch_exceptions=False)


def test_answer():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init"], catch_exceptions=False)
        result = runner.invoke(cli, ["add", "--role", "user"], input="What is your name?", catch_exceptions=False)
        result = runner.invoke(cli, ["answer"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "WHAT IS YOUR NAME?" in result.output
