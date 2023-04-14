import re
import io
import os
import sys
import contextlib
import ast
import traceback
import json
import subprocess
import duckduckgo_search
import wolframalpha


BLOCK_PATTERNS = {
    "bash": r"EVALUATE:\n+```(?:bash)?\n(.*?)```",
    "pyeval": r"EVALUATE:\n+```(?:python)?\n(.*?)```",
    "search": r"SEARCH\((.*)\)",
    "wolfram": r"WOLFRAM\((.*)\)",
    "save": r"SAVE\((.*?)\)\n```\w*\n(.*?)```",
}


def evaluate_plugins(response_text, plugins):
    formatted_output = []
    for active_plugin in plugins:
        blocks = extract_blocks(response_text, active_plugin)
        for block in blocks:
            match active_plugin:
                case "pyeval":
                    output = exec_python(block)
                case "bash":
                    output = exec_bash(block)
                case "search":
                    search_term = block.strip()
                    if search_term[0] in "\"'":
                        search_term = ast.literal_eval(search_term)
                    output = exec_duckduckgo(search_term)
                case "wolfram":
                    search_term = block.strip()
                    if search_term[0] in "\"'":
                        search_term = ast.literal_eval(search_term)
                    output = exec_wolfram(search_term)
                case "save":
                    filename, contents = block
                    if filename[0] in "\"'":
                        filename = ast.literal_eval(filename)
                    with open(filename, "w", encoding="utf-8") as fh:
                        fh.write(contents)
                    output = {"result": f"Saved to: {filename}"}

            formatted_output.append(format_block(output))
    return "\n".join(formatted_output)


def extract_blocks(response_text, plugin):
    block_pattern = BLOCK_PATTERNS[plugin]
    matches = re.findall(block_pattern, response_text, re.DOTALL)
    return matches


def exec_bash(code):
    result = subprocess.run(["/bin/bash", "-c", code], capture_output=True, text=True, check=False)

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
    return {"result": json.dumps(duckduckgo_search.ddg(search_term, max_results=5), indent=2)}


def exec_wolfram(query):
    api_key = os.environ.get("WOLFRAM_ALPHA_API_KEY")
    if not api_key:
        return {"error": "WOLFRAM_ALPHA_API_KEY is not configured. (Set as an environment variable.)"}
    client = wolframalpha.Client(api_key)
    result = client.query(query)
    return {"result": next(result.results).text}


# TODO: Truncate the output to meet token requirement and save $$.
def format_block(output):
    output_blocks = []
    if output.get("result"):
        output_blocks.append(f"RESULT:\n```\n{output['result']}\n```")
    if output.get("error"):
        output_blocks.append(f"ERROR:\n```\n{output['error']}\n```")
    return "\n".join(output_blocks)


if __name__ == "__main__":
    input_text = sys.stdin.read()
    print(evaluate_plugins(input_text, sys.argv[1:]))
