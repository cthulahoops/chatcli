import re
import io
import sys
import contextlib
import ast
import traceback
import json
from duckduckgo_search import ddg


def evaluate_plugins(response_text, plugins):
    block_patterns = {"pyeval": r"EVALUATE:\n+```(?:python)?\n(.*?)```", "search": r"SEARCH\((.*)\)"}
    active_plugin = plugins[0]
    blocks = extract_blocks(response_text, block_patterns[active_plugin])
    if not blocks:
        return None
    if active_plugin == "pyeval":
        output = exec_python(blocks[0])
    elif active_plugin == "search":
        output = exec_duckduckgo(blocks[0])
    return format_block(output)


def extract_blocks(response_text, block_pattern):
    matches = re.findall(block_pattern, response_text, re.DOTALL)
    return matches


def exec_python(code):
    buffer = io.StringIO()

    with contextlib.redirect_stdout(buffer):
        global_scope = globals()
        try:
            mod = ast.parse(code, mode="exec")
            if isinstance(mod.body[-1], ast.Expr):
                last_expr = mod.body.pop()
                exec(compile(mod, "<ast>", "exec"), global_scope)
                result = eval(compile(ast.Expression(last_expr.value), "<ast>", "eval"), global_scope)
                if result is not None:
                    print(result)
            else:
                exec(code, global_scope)
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())

    return buffer.getvalue().strip()


def exec_duckduckgo(search_term):
    return json.dumps(ddg(search_term, max_results=5))


def format_block(output):
    formatted_output = f"RESULT:\n```\n{output}\n```"
    return formatted_output


if __name__ == "__main__":
    input_text = sys.stdin.read()
    print(evaluate_plugins(input_text, ["search"]))
