import os
import os.path
import datetime
import json
from textwrap import dedent

INITIAL_PERSONALITIES = {
    "concise": {
        "content": "You are a helpful, expert linux user and programmer. You give concise answers, providing code where possible.",
    },
    "code": {"content": "You only answer questions with a single example code block only, and no other explanations."},
    "commit": {
        "content": """
                You generate commit messages from diffs. Every line of commit message should be less than eighty characters.
                You never output anything that does not belong in the commit message.
                """,
    },
    "pyeval": {
        "plugins": ["pyeval"],
        "content": """
                You can evaluate code by returning any python code in a code block with the line "EVALUATE:" before it.
                Do you not attempt to compute expressions, or the results of python code yourself, instead use an EVALUATE block.
                You will get the result of running the code you provide in a result block.

                For example:

                EVALUATE:
                ```
                print(4 + 5)
                ```

                And you would then receive

                RESULT:
                ```
                9
                ```
                as the next message.

                Use the result to help you answer the question.
            """,
    },
    "search": {
        "plugins": ["search"],
        "content": """
            You can search the internet by returning query in the form SEARCH("query")
            Whenever you are asked a question, you should first search the internet for an answer.
            Search the internet by using the search command:

            For example:

            SEARCH("president of the united states")

            Use the result to help you answer the question.

            Run additional queries as necessary to answer further questions.
        """,
    },
}

CHAT_LOG = os.environ.get("CHATCLI_LOGFILE", ".chatcli.log")


def write_log(messages, completion=None, usage=None, tags=None, plugins=None, path=None):
    assert isinstance(messages, list)
    assert isinstance(tags, list) or tags is None
    assert isinstance(completion, dict) or completion is None
    assert isinstance(usage, dict) or usage is None
    assert isinstance(plugins, (list, tuple)) or plugins is None
    timestamp = datetime.datetime.now().isoformat()

    path = path or find_log()

    with open(path, "a", buffering=1, encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "messages": messages,
                    "completion": completion,
                    "usage": usage,
                    "tags": tags or [],
                    "timestamp": timestamp,
                    "plugins": plugins or [],
                }
            )
            + "\n"
        )


def create_initial_log(reinit):
    if not reinit and os.path.exists(CHAT_LOG):
        raise FileExistsError(CHAT_LOG)

    for key, value in INITIAL_PERSONALITIES.items():
        write_log(
            messages=[{"role": "system", "content": dedent(value["content"].strip())}],
            tags=["^" + key],
            plugins=value.get("plugins"),
            path=CHAT_LOG,
        )


def conversation_log():
    log_path = find_log()
    with open(log_path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def find_log():
    path = CHAT_LOG
    while not os.path.exists(path):
        if os.path.dirname(os.path.abspath(path)) == "/":
            raise FileNotFoundError(CHAT_LOG)
        path = "../" + path
    return path


def search_conversations(offset, search, tag):
    for idx, conversation in enumerate(reversed(conversation_log()), start=1):
        if offset and idx != offset:
            continue

        if len(conversation["messages"]) > 1:
            question = conversation["messages"][-2]["content"]
        else:
            question = conversation["messages"][-1]["content"]

        if search and search not in question:
            continue
        if tag and tag not in conversation.get("tags", []):
            continue
        yield idx, conversation


def get_logged_conversation(offset, search=None, tag=None):
    return next(search_conversations(offset, search, tag))[1]


def convert_log(filename):
    with open(filename, "r", encoding="utf-8") as fh:
        for line in fh:
            data = json.loads(line)

            if "request" in data:
                if data["response"]:
                    assistant_message = data["response"]["choices"][0]["message"]
                    if "role" not in assistant_message:
                        assistant_message["role"] = "assistant"
                    messages = data["request"] + [assistant_message]
                    usage = data["response"].get("usage")
                else:
                    messages = data["request"]
                    usage = None
            elif "response" in data:
                messages = [data["response"]["choices"][0]["message"]]
                usage = data["response"]["usage"]
            else:
                messages = data["messages"]
                usage = data["usage"]

            if usage and "request_tokens" in usage:
                usage["prompt_tokens"] = usage["request_tokens"]
                del usage["request_tokens"]

            tags = data.get("tags", [])
            completion = data.get("completion") or data.get("response")

            timestamp = (
                data.get("timestamp")
                or (completion and datetime.datetime.fromtimestamp(completion.get("created")).isoformat())
                or datetime.datetime.now().isoformat()
            )

            assert isinstance(messages, list), data
            assert isinstance(tags, list), data
            assert isinstance(completion, dict) or completion is None, (
                completion,
                data,
            )
            assert isinstance(usage, dict) or usage is None, (usage, data)

            converted_data = {
                "messages": messages,
                "completion": completion,
                "tags": tags,
                "usage": usage,
                "timestamp": timestamp,
                "plugins": data.get("plugins", []),
            }
            yield json.dumps(converted_data)
