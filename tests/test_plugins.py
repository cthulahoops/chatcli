from unittest import mock
from chatcli_gpt.plugins import evaluate_plugins, format_block


def test_simple_code():
    assert evaluate_plugins(block("print(3 + 4)"), ["pyeval"]) == result("7")


def test_sqrt_example():
    assert evaluate_plugins(block("import math; math.sqrt(4)"), ["pyeval"]) == result("2.0")


def test_use_defined_function():
    assert evaluate_plugins(block("def double(x):\n  return 2 * x\ndouble(4)\n"), ["pyeval"]) == result("8")


def test_recursive_function():
    assert evaluate_plugins(
        block("def fact(n):\n if n <= 1:\n  return n\n return fact(n - 1) * n\nfact(6)\n"), ["pyeval"]
    ) == result("720")


@mock.patch("chatcli_gpt.plugins.duckduckgo_search.ddg", return_value='[{"content": "Some guy"}]')
def test_simple_search(mock_ddg):
    assert "Some guy" in evaluate_plugins('SEARCH("Who is the president of the USA?")', ["search"])
    assert mock_ddg.call_args.args[0] == "Who is the president of the USA?"


def test_bash():
    assert evaluate_plugins(block("let a=4+5; echo $a", "bash"), ["bash"]) == result("9")


def result(result_text, error=""):
    return format_block({"result": result_text, "error": error})


def block(code, block_type="python"):
    return f"EVALUATE:\n```{block_type}\n{code}\n```"
