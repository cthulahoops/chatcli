from textwrap import dedent
from chatcli.plugins import extract_blocks, exec_python

def test_extract_block():
    response_text = dedent("""
    This is an example text with an evaluation block.

    EVALUATE:
    ```
    print("3 + 4")
    ```

    There could be more text after the block.
    """)

    blocks = extract_blocks(response_text, 'pyeval')

    assert blocks == ['print("3 + 4")\n']


def test_simple_code():
    assert exec_python("print(3 + 4)") == '7'

def test_sqrt_example():
    assert exec_python("import math; math.sqrt(4)") == '2.0'

def test_use_defined_function():
    assert exec_python("def double(x):\n  return 2 * x\ndouble(4)\n") == '8'

def test_recursive_function():
    assert exec_python("def fact(n):\n if n <= 1:\n  return n\n return fact(n - 1) * n\nfact(6)\n") == '720'
