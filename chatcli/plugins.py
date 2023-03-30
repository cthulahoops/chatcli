import re
import io
import sys
import contextlib
import ast
import traceback

def evaluate_code_block(response_text):
    blocks = extract_blocks(response_text)
    if not blocks:
        return None
    output = exec_python(blocks[0])
    return format_block(output)

def extract_blocks(response_text):
    block_pattern = r"EVALUATE:\n+```(?:python)?\n(.*?)```"
    matches = re.findall(block_pattern, response_text, re.DOTALL)
    return matches

def exec_python(code):
    buffer = io.StringIO()

    with contextlib.redirect_stdout(buffer):
        global_scope = globals()
        try:
            mod = ast.parse(code, mode='exec')
            if isinstance(mod.body[-1], ast.Expr):
                last_expr = mod.body.pop()
                exec(compile(mod, '<ast>', 'exec'), global_scope)
                result = eval(compile(ast.Expression(last_expr.value), '<ast>', 'eval'), global_scope)
                if result is not None:
                    print(result)
            else:
                exec(code, global_scope)
        except Exception: # pylint: disable=broad-except
            print(traceback.format_exc())

    return buffer.getvalue().strip()


def format_block(output):
    formatted_output = f"RESULT:\n```\n{output}\n```"
    return formatted_output

if __name__ == '__main__':
    input_text = sys.stdin.read()
    print(evaluate_code_block(input_text))
