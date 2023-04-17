from pathlib import Path
from unittest import mock
from click.testing import CliRunner
from chatcli_gpt.plugins import evaluate_plugins, format_block


def test_simple_code():
    assert evaluate_plugins(block("print(3 + 4)"), ["pyeval"]) == result("7")


def test_sqrt_example():
    assert evaluate_plugins(block("import math; math.sqrt(4)"), ["pyeval"]) == result("2.0")


def test_use_defined_function():
    assert evaluate_plugins(block("def double(x):\n  return 2 * x\ndouble(4)\n"), ["pyeval"]) == result("8")


def test_python_exception():
    assert "ZeroDivisionError: division by zero" in evaluate_plugins(block("print(3 / 0)"), ["pyeval"])


def test_python_statement():
    assert "ValueError" in evaluate_plugins(block("raise ValueError(7)"), ["pyeval"])


def test_recursive_function():
    assert evaluate_plugins(
        block("def fact(n):\n if n <= 1:\n  return n\n return fact(n - 1) * n\nfact(6)\n"),
        ["pyeval"],
    ) == result("720")


@mock.patch("chatcli_gpt.plugins.duckduckgo_search.ddg", return_value='[{"content": "Some guy"}]')
def test_simple_search(mock_ddg):
    assert "Some guy" in evaluate_plugins('SEARCH("Who is the president of the USA?")', ["search"])
    assert mock_ddg.call_args.args[0] == "Who is the president of the USA?"


@mock.patch("chatcli_gpt.plugins.wolframalpha")
@mock.patch("os.environ", {"WOLFRAM_ALPHA_API_KEY": "TRUE"})
def test_wolfram(mock_wolfram):
    next(mock_wolfram.Client().query().results).text = "Paris"
    assert "Paris" in evaluate_plugins('WOLFRAM("What is the capital of France?")', ["wolfram"])


def test_bash():
    assert evaluate_plugins(block("let a=4+5; echo $a", "bash"), ["bash"]) == result("9")


def test_multiple_blocks():
    assert evaluate_plugins(block("print(3 + 4)") + block("import math; math.sqrt(4)"), ["pyeval"]) == result(
        7,
    ) + "\n" + result(2.0)


def test_evaluate_multiple_plugins():
    assert evaluate_plugins(block("print(3 * 4)") + block("echo hi", "bash"), ["pyeval", "bash"]) == result(
        12,
    ) + "\n" + result("hi")


def test_save_file():
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert evaluate_plugins(
            block(
                "Hello, world",
                "",
                "SAVE('hello.txt')",
            ),
            ["save"],
        ) == result(
            "Saved to: hello.txt",
        )
        with Path("hello.txt").open("r", encoding="utf-8") as fh:
            assert fh.read() == "Hello, world\n"


def result(result_text, error=""):
    return format_block({"result": result_text, "error": error})


def block(code, block_type="python", block_header="EVALUATE:"):
    return f"{block_header}\n```{block_type}\n{code}\n```\n"
