# pylint: disable=redefined-outer-name
import os
import json
from unittest.mock import patch
from datetime import datetime, timedelta
import pytest
from click.testing import CliRunner
from chatcli_gpt.cli import cli, find_recent_message
from chatcli_gpt.conversation import Conversation


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

    mocker.patch("chatcli_gpt.cli.openai.ChatCompletion.create", advanced_ai)


@pytest.fixture()
def chatcli():
    runner = CliRunner()
    with runner.isolated_filesystem():

        def chatcli(*args, catch_exceptions=False, expected_exit_code=0, **kwargs):
            result = runner.invoke(cli, *args, catch_exceptions=catch_exceptions, **kwargs)
            assert result.exit_code == expected_exit_code
            return result

        chatcli("init")
        yield chatcli


def test_chat_code(chatcli):
    result = chatcli("chat --quick -p code", input="Say hello in python")
    assert "SAY HELLO IN PYTHON" in result.output


def test_chat_sync(chatcli):
    result = chatcli("chat --quick -p code --sync", input="Say hello in python")
    assert "SAY HELLO IN PYTHON" in result.output


def test_chat_with_file(chatcli):
    with open("test.txt", "w", encoding="utf-8") as fh:
        fh.write("Hello, world!")
    chatcli("-f test.txt", input="What's in this file?")
    result = chatcli("show --json")
    assert "The file 'test.txt' contains:\n```\nHello, world!```" == json.loads(result.output)["messages"][1]["content"]


def test_show_short(chatcli):
    result = chatcli("chat -q", input="What is your name?")
    result = chatcli("show -s")
    assert "What is your name?" not in result.output
    assert "WHAT IS YOUR NAME?" in result.output


def test_show_long(chatcli):
    chatcli("chat -q", input="What is your name?")
    result = chatcli("show -l")
    assert "expert linux user" in result.output
    assert "What is your name?" in result.output
    assert "WHAT IS YOUR NAME?" in result.output


def test_log(chatcli):
    chatcli("chat --quick -p concise", input="What is your name?")
    chatcli("chat --quick -c", input="What is your quest?")
    result = chatcli("log")
    assert "2: What is your name?" in result.output
    assert "1: What is your quest?" in result.output


def test_log_everything(chatcli):
    chatcli("chat --quick -p concise", input="What is your name?")
    chatcli("chat --quick -c", input="What is your quest?")
    result = chatcli("log --usage --model --cost")
    assert "What is your name?" in result.output
    assert "What is your quest?" in result.output


def test_log_json(chatcli):
    chatcli("chat --quick -p concise", input="What is your name?")
    chatcli("chat --quick -c", input="What is your quest?")
    result = chatcli("log --json -l 2")
    data = [json.loads(line) for line in result.output.splitlines()]
    assert len(data) == 2


def test_chat_log_search(chatcli):
    chatcli("chat --quick -p concise", input="What is your name?")
    chatcli("chat --quick -c", input="What is your quest?")
    result = chatcli("log -s name")
    assert "2: What is your name?" in result.output
    assert "1: What is your quest?" not in result.output


def test_usage(chatcli):
    chatcli("chat", input="What is your name?")
    chatcli("chat", input="What is your name?")
    result = chatcli("usage")
    assert "Tokens: 82" in result.output
    assert "Cost: $0.00" in result.output


def test_usage_today(chatcli):
    with patch("chatcli_gpt.log.datetime") as dt:
        dt.datetime.now.return_value = datetime.now() - timedelta(seconds=100000)
        chatcli("chat", input="What is your name?")
    chatcli("chat", input="What is your name?")
    result = chatcli("usage --today")
    assert "Tokens: 41" in result.output
    assert "Cost: $0.00" in result.output


def test_tag_usage(chatcli):
    chatcli("chat", input="What is your name?")
    chatcli("chat", input="What is your name?")
    chatcli("tag test_tag")
    result = chatcli("usage")
    assert "Tokens: 82" in result.output
    assert "Cost: $0.00" in result.output


def test_untag_usage(chatcli):
    chatcli("chat", input="What is your name?")
    chatcli("chat", input="What is your name?")
    chatcli("untag test_tag")
    result = chatcli("usage")
    assert "Tokens: 82" in result.output
    assert "Cost: $0.00" in result.output


def test_chat_retry(chatcli):
    chatcli("chat", input="What is your name?")
    result = chatcli("chat --quick --retry")
    assert "WHAT IS YOUR NAME?" in result.output


def test_tag(chatcli):
    chatcli("chat --quick -p concise", input="What is your name?")
    chatcli("tag test_tag")
    result = chatcli("log -t test_tag")
    assert len(result.output.splitlines()) == 1
    assert "test_tag" in result.output


def test_tag_preserves_model(chatcli):
    chatcli("chat --quick -p concise --model gpt-4", input="What is your name?")
    chatcli("tag test_tag")
    result = chatcli("show --json")
    assert "gpt-4" == json.loads(result.output)["model"]


def test_tags(chatcli):
    chatcli("chat --quick -p concise", input="What is your name?")
    chatcli("tag test_tag")
    chatcli("tag test_tag2")
    result = chatcli("tags")
    assert "test_tag" in result.output
    assert "test_tag2" in result.output


def test_tag_delete(chatcli):
    chatcli("chat --quick -p concise", input="What is your name?")
    chatcli("tag test_tag")
    chatcli("untag test_tag")
    result = chatcli("log -l 1")
    assert "test_tag" not in result.output


def test_show_tag(chatcli):
    chatcli("chat --quick -p concise", input="What is your name?")
    chatcli("tag test_tag")
    result = chatcli("show-tag")
    assert "test_tag" in result.output


def test_current_tag_follows_conversation(chatcli):
    chatcli("chat --quick -p concise", input="What is your name?")
    chatcli("tag test_tag")
    chatcli("chat --continue --quick", input="What is your quest?")
    result = chatcli("show-tag")
    assert "test_tag" in result.output


def test_add_personality(chatcli):
    chatcli("add -p test_personality", input="You are a test personality.")
    result = chatcli("log")
    assert "^test_personality" in result.output


def test_add_personality_with_pyeval_and_evaluate(chatcli):
    chatcli("add -p test_personality --plugin pyeval", input="You are a test personality.")
    result = chatcli("log --plugins")
    assert "^test_personality" in result.output


def test_default_personality_cannot_evaluate(chatcli):
    result = chatcli("chat", input="evaluate: 6 * 7")
    assert "42" not in result.output


def test_pyeval(chatcli):
    result = chatcli("chat -p pyeval", input="evaluate: 6 * 7")
    assert "42" in result.output


def test_find_recent_message():
    conversation = Conversation(
        **{
            "messages": [
                {"sender": "assistant", "message": "???"},
                {"sender": "user", "message": "hello"},
                {"sender": "assistant", "message": "hi"},
                {"sender": "user", "message": "how are you?"},
            ]
        }
    )

    def predicate(msg):
        return msg["sender"] == "assistant"

    result = find_recent_message(predicate, conversation)
    expected = {"sender": "assistant", "message": "hi"}

    assert result == expected


def test_parents_log(chatcli):
    os.mkdir("subdir")
    os.chdir("subdir")
    chatcli("log")


def test_fresh_logfile_no_upgrade(chatcli):
    chatcli("show")
    assert not os.path.exists(".chatcli.log.bak.0_3")


def test_no_log():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with pytest.raises(FileNotFoundError):
            runner.invoke(cli, ["log"], catch_exceptions=False)


def test_reinit(chatcli):
    chatcli("init", expected_exit_code=1)


def test_logfile_upgrade(chatcli):
    with open(".chatcli.log", "w") as fh:
        fh.write(json.dumps({"messages": [], "usage": {"request_tokens": 100}}) + "\n")
        fh.write(json.dumps({"messages": [], "usage": {"total_tokens": 0}}) + "\n")
    chatcli("show")
    assert os.path.exists(".chatcli.log.bak.0_3")


def test_answer(chatcli):
    chatcli("add --role user", input="What is your name?")
    result = chatcli("answer")
    assert "WHAT IS YOUR NAME?" in result.output


def test_merge(chatcli):
    chatcli("add --role user --plugin a", input="What is your name?")
    chatcli("add --role assistant --plugin b --model gpt-4", input="My name is Bob.")
    chatcli("merge -p test 1 2")
    result = chatcli("show --json")
    data = json.loads(result.stdout)
    assert data["tags"] == ["^test"]
    assert data["plugins"] == ["a", "b"]
    assert data["model"] == "gpt-4"
