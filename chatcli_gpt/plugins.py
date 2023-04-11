import re
import io
import sys
import contextlib
import ast
import traceback
import json
import subprocess
import duckduckgo_search


BLOCK_PATTERNS = {
    "bash": r"EVALUATE:\n+```(?:bash)?\n(.*?)```",
    "pyeval": r"EVALUATE:\n+```(?:python)?\n(.*?)```",
    "search": r"SEARCH\((.*)\)",
}


def evaluate_plugins(response_text, plugins):
    active_plugin = plugins[0]
    blocks = extract_blocks(response_text, active_plugin)
    if not blocks:
        return None
    if active_plugin == "pyeval":
        output = exec_python(blocks[0])
    elif active_plugin == "bash":
        output = exec_bash(blocks[0])
    elif active_plugin == "search":
        search_term = blocks[0].strip()
        if search_term[0] in "\"'":
            search_term = ast.literal_eval(search_term)
        output = exec_duckduckgo(search_term)
    return format_block(output)


def extract_blocks(response_text, plugin):
    block_pattern = BLOCK_PATTERNS[plugin]
    matches = re.findall(block_pattern, response_text, re.DOTALL)
    return matches


def exec_bash(code):
    try:
        result = subprocess.run(["/bin/bash", "-c", code], capture_output=True, text=True)
    except Exception:  # pylint: disable=broad-except
        print(traceback.format_exc())

    return {
        "result": result.stdout.strip(),
        "error": result.stderr.strip(),
    }


def exec_python(code):
    stdout = io.StringIO()
    stderr = io.StringIO()

    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        global_scope = globals()
        try:
            mod = ast.parse(code, mode="exec")
            if isinstance(mod.body[-1], ast.Expr):
                last_expr = mod.body.pop()
                exec(compile(mod, "<ast>", "exec"), global_scope)
                result = eval(
                    compile(ast.Expression(last_expr.value), "<ast>", "eval"),
                    global_scope,
                )
                if result is not None:
                    print(result)
            else:
                exec(code, global_scope)
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())

    return {
        "result": stdout.getvalue().strip(),
        "error": stderr.getvalue().strip(),
    }


def exec_duckduckgo(search_term):
    return {"result": json.dumps(duckduckgo_search.ddg(search_term, max_results=5))}


# TODO: Truncate the output to meet token requirement and save $$.
def format_block(output):
    output_blocks = []
    if output["result"]:
        output_blocks.append(f"RESULT:\n```\n{output['result']}\n```")
    if output["error"]:
        output_blocks.append(f"ERROR:\n```\n{output['error']}\n```")
    return "\n".join(output_blocks)


if __name__ == "__main__":
    input_text = sys.stdin.read()
    print(evaluate_plugins(input_text, ["search"]))
