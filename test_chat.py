from unittest.mock import patch
import pytest
from click.testing import CliRunner
from chat import cli


@pytest.fixture(autouse=True)
def fake_assistant(mocker):
    def advanced_ai(model, messages):
        return {
            "choices": [{"message": {"role": "assistant", "content": messages[-1]["content"].upper()}}],
            "usage": {"total_tokens": 5000},
        }
    mocker.patch("chat.openai.ChatCompletion.create", advanced_ai)


def test_chat_code(mocker):
    mocker.patch("chat.prompt", return_value="Say hello in python")
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            cli, ["chat", "--quick", "-p", "code"], catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "SAY HELLO IN PYTHON" in result.output


def test_show_short(mocker):
    runner = CliRunner()
    with runner.isolated_filesystem():
        mocker.patch("chat.prompt", return_value="What is your name?")
        result = runner.invoke(cli, ["chat", "-q"], catch_exceptions=False)
        result = runner.invoke(cli, ["show", "-s"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "What is your name?" not in result.output
        assert "WHAT IS YOUR NAME?" in result.output


def test_show_long(mocker):
    runner = CliRunner()
    with runner.isolated_filesystem():
        mocker.patch("chat.prompt", return_value="What is your name?")
        result = runner.invoke(cli, ["chat", "-q"], catch_exceptions=False)
        result = runner.invoke(cli, ["show", "-l"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "expert linux user" in result.output
        assert "What is your name?" in result.output
        assert "WHAT IS YOUR NAME?" in result.output


def test_log(mocker):
    runner = CliRunner()
    with runner.isolated_filesystem():
        mocker.patch("chat.prompt", return_value="What is your name?")
        result = runner.invoke(
            cli, ["chat", "--quick", "-p", "concise"], catch_exceptions=False
        )
        mocker.patch("chat.prompt", return_value="What is your quest?")
        result = runner.invoke(
            cli, ["chat", "--quick", "-c", "-p", "italiano"], catch_exceptions=False
        )
        result = runner.invoke(cli, ["log"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "2: What is your name?" in result.output
        assert "1: What is your quest?" in result.output

def test_chat_log_search(mocker):
    runner = CliRunner()
    with runner.isolated_filesystem():
        mocker.patch("chat.prompt", return_value="What is your name?")
        result = runner.invoke(
            cli, ["chat", "--quick", "-p", "concise"], catch_exceptions=False
        )
        mocker.patch("chat.prompt", return_value="What is your quest?")
        result = runner.invoke(
            cli, ["chat", "--quick", "-c", "-p", "italiano"], catch_exceptions=False
        )
        result = runner.invoke(cli, ["log", "-s", "name"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "2: What is your name?" in result.output
        assert "1: What is your quest?" not in result.output

def test_usage(mocker):
    mocker.patch("chat.prompt", return_value="What is your name?")

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["chat", "--quick"], catch_exceptions=False)
        result = runner.invoke(cli, ["chat", "--quick"], catch_exceptions=False)
        result = runner.invoke(cli, ["usage"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Tokens: 10000" in result.output
        assert "Cost: $0.02" in result.output


def test_chat_retry(mocker):
    runner = CliRunner()
    with runner.isolated_filesystem():
        with patch("chat.prompt", return_value="What is your name?"):
            result = runner.invoke(cli, ["chat", "--quick"], catch_exceptions=False)
        result = runner.invoke(
            cli, ["chat", "--quick", "--retry"], catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "WHAT IS YOUR NAME?" in result.output
