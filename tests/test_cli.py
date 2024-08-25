# pylint: disable=redefined-outer-name
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from chatcli_gpt.cli import cli
from click.testing import CliRunner


def test_chat_default(chatcli):
    result = chatcli("--quick", input="What is your name?")
    assert "WHAT IS YOUR NAME?" in result.output
    result = chatcli("show --json")
    data = json.loads(result.output)
    assert (
        data["messages"][0]["content"]
        == "You are a helpful, expert linux user and programmer. You give concise answers. Provide code where possible."
    )
    assert data["model"] == "gpt-3.5-turbo-1106"


def test_chat_code(chatcli):
    result = chatcli("chat --quick -p code", input="Say hello in python")
    assert "SAY HELLO IN PYTHON" in result.output


def test_chat_sync(chatcli):
    result = chatcli("chat --quick -p code --sync", input="Say hello in python")
    assert "SAY HELLO IN PYTHON" in result.output


def test_chat_with_file(chatcli):
    with Path("test.txt").open("w", encoding="utf-8") as fh:
        fh.write("Hello, world!")
    chatcli("-f test.txt", input="What's in this file?")
    result = chatcli("show --json")
    assert (
        json.loads(result.output)["messages"][1]["content"]
        == "The file 'test.txt' contains:\n```\nHello, world!```"
    )


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
    chatcli("chat --quick -p default", input="What is your name?")
    chatcli("chat --quick -c", input="What is your quest?")
    result = chatcli("log")
    assert "2: What is your name?" in result.output
    assert "1: What is your quest?" in result.output


def test_log_everything(chatcli):
    chatcli("chat --quick -p default", input="What is your name?")
    chatcli("chat --quick -c", input="What is your quest?")
    result = chatcli("log --usage --model --cost")
    assert "What is your name?" in result.output
    assert "What is your quest?" in result.output


def test_log_json(chatcli):
    chatcli("chat --quick -p default", input="What is your name?")
    chatcli("chat --quick -c", input="What is your quest?")
    result = chatcli("log --json -l 2")
    data = [json.loads(line) for line in result.output.splitlines()]
    assert len(data) == 2


def test_chat_log_search(chatcli):
    chatcli("chat --quick -p default", input="What is your name?")
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
        dt.now.return_value = datetime.now(tz=timezone.utc) - timedelta(seconds=100000)
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
    chatcli("chat --quick -p default", input="What is your name?")
    chatcli("tag test_tag")
    result = chatcli("log -t test_tag")
    assert len(result.output.splitlines()) == 1
    assert "test_tag" in result.output


def test_tag_preserves_model(chatcli):
    chatcli("chat --quick -p default --model gpt-4", input="What is your name?")
    chatcli("tag test_tag")
    result = chatcli("show --json")
    assert json.loads(result.output)["model"] == "gpt-4-1106-preview"


def test_tags(chatcli):
    chatcli("chat --quick -p default", input="What is your name?")
    chatcli("tag test_tag")
    chatcli("tag test_tag2")
    result = chatcli("tags")
    assert "test_tag" in result.output
    assert "test_tag2" in result.output


def test_personalities(chatcli):
    result = chatcli("personalities")
    assert "default" in result.output
    assert "wolfram" in result.output


def test_tag_delete(chatcli):
    chatcli("chat --quick -p default", input="What is your name?")
    chatcli("tag test_tag")
    chatcli("untag test_tag")
    result = chatcli("log -l 1")
    assert "test_tag" not in result.output


def test_show_tag(chatcli):
    chatcli("chat --quick -p default", input="What is your name?")
    chatcli("tag test_tag")
    result = chatcli("show-tag")
    assert "test_tag" in result.output


def test_show_not_existing_tag(chatcli):
    with pytest.raises(AssertionError):
        chatcli("show --tag this_doesnt_exist")


def test_current_tag_follows_conversation(chatcli):
    chatcli("chat --quick -p default", input="What is your name?")
    chatcli("tag test_tag")
    chatcli("chat --continue --quick", input="What is your quest?")
    result = chatcli("show-tag")
    assert "test_tag" in result.output


def test_add_personality(chatcli):
    chatcli("add -p test_personality", input="You are a test personality.")
    result = chatcli("log")
    assert "^test_personality" in result.output


def test_add_personality_with_pyeval_and_evaluate(chatcli):
    chatcli(
        "add -p test_personality --plugin pyeval", input="You are a test personality."
    )
    result = chatcli("log --plugins")
    assert "^test_personality" in result.output


def test_default_personality_cannot_evaluate(chatcli):
    result = chatcli("chat", input="evaluate: 6 * 7")
    assert "42" not in result.output


def test_pyeval(chatcli):
    result = chatcli("chat -p pyeval", input="evaluate: 6 * 7")
    assert "42" in result.output


def test_parents_log(chatcli):
    Path("subdir").mkdir()
    os.chdir(Path("subdir"))
    chatcli("log")


def test_fresh_logfile_no_upgrade(chatcli):
    chatcli("show")
    assert not Path(".chatcli.log.bak.0_3").exists()


def test_no_log():
    runner = CliRunner()
    with runner.isolated_filesystem(), pytest.raises(FileNotFoundError):
        runner.invoke(cli, ["log"], catch_exceptions=False)


def test_reinit(chatcli):
    chatcli("init", expected_exit_code=1)


def test_reinit_keeps_history(chatcli):
    chatcli("add --role user", input="What is your name?")
    chatcli("init --reinit")
    result = chatcli("log")
    assert "What is your name?" in result.output


def test_logfile_upgrade(chatcli):
    with Path(".chatcli.log").open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"messages": [], "usage": {"request_tokens": 100}}) + "\n")
        fh.write(json.dumps({"messages": [], "usage": {"total_tokens": 0}}) + "\n")
    chatcli("show")
    assert Path(".chatcli.log.bak.0_3").exists()


def test_answer(chatcli):
    chatcli("add --role user", input="What is your name?")
    result = chatcli("answer")
    assert "WHAT IS YOUR NAME?" in result.output


def test_answer_doesnt_change_personality(chatcli):
    chatcli("add --role user --personality name", input="What is your name?")
    chatcli("answer")
    data = last_conversation_data(chatcli)
    assert data["tags"] == []


def test_answer_with_model(chatcli):
    chatcli("add --role user --personality name", input="What is your name?")
    chatcli("answer --model=name_is_alice")
    assert last_message(chatcli) == "My name is Alice."


def test_models(chatcli):
    result = chatcli("models")

    assert "name_is_alice" in result.output.split()


def test_merge(chatcli):
    chatcli("add --role user --plugin a", input="What is your name?")
    chatcli("add --role assistant --plugin b --model gpt-4", input="My name is Bob.")
    chatcli("merge -p test 1 2")
    data = last_conversation_data(chatcli)
    assert data["tags"] == ["^test"]
    assert data["plugins"] == ["a", "b"]
    assert data["model"] == "gpt-4-1106-preview"


def test_edit(chatcli):
    chatcli("add --role user", input="What is your name?")
    chatcli("edit 1", input="What is your quest?")
    assert last_message(chatcli) == "What is your quest?"


def test_edit_model(chatcli):
    chatcli("add --role user", input="What is your name?")
    chatcli("edit 1 --no-prompt --model gpt-3.5")
    data = last_conversation_data(chatcli)
    assert data["model"] == "gpt-3.5-turbo-1106"


def test_drop(chatcli):
    chatcli("add --role user", input="What is your name?")
    chatcli("add --role assistant --continue", input="My name is Bob.")
    chatcli("drop 1")
    assert last_message(chatcli) == "What is your name?"


def last_message(chatcli):
    data = last_conversation_data(chatcli)
    return data["messages"][-1]["content"]


def last_conversation_data(chatcli):
    result = chatcli("show --json")
    return json.loads(result.stdout)
