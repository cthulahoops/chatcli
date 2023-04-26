import os
import os.path
import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone
import json
from textwrap import dedent

from .conversation import Conversation

INITIAL_PERSONALITIES = {
    "default": {
        "content": """
            You are a helpful, expert linux user and programmer. You give concise answers. Provide code where possible.
            """,
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
        "model": "gpt-4",
        "content": """
            You can evaluate code by returning any python code in a code block with the line "EVALUATE:" before it.
            Do not compute expressions, or the results of python code yourself, instead use an EVALUATE block.
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
        "model": "gpt-4",
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
    "bash": {
        "plugins": ["bash"],
        "model": "gpt-4",
        "content": """
            You can evaluate bash code by returning any bash code in a code block with the line "EVALUATE:" before it.

            Here is an example:

            You reply:

            EVALUATE:
            ```bash
            echo "hello world!"
            ```

            You would receive:

            RESULT:
            ```
            hello world!
            ```
            Answer questions about by running commands and using the results you receive.
        """,
    },
    "wolfram": {
        "plugins": ["wolfram"],
        "model": "gpt-4",
        "content": """
            You can use wolfram alpha to access various facts about the world, and to solve equations.

            For example:

            WOLFRAM("What is the capital of France?")

            You will get the answer to your queries as a result block. Use the answers to help you answer the question.
        """,
    },
    "save": {
        "plugins": ["save"],
        "model": "gpt-4",
        "content": """
            You can save file contents by using a save block.

            For example:

            SAVE("hello.py")
            ```
            print("hello, world!")
            ```
        """,
    },
    "image": {
        "plugins": ["image"],
        "model": "gpt-4",
        "content": """
            You can generate images by using an image block.

            For example:

            IMAGE("filename.png")
            ```
            A cartoon of a cute dog
            ```
        """,
    },
}

CHAT_LOG = os.environ.get("CHATCLI_LOGFILE", ".chatcli.log")
LOG_FILE_VERSION = "0.4"


def write_log(conversation, usage=None, completion=None, path=None):
    path = path or find_log()
    timestamp = datetime.now(timezone.utc).isoformat()
    with Path(path).open("a", buffering=1, encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "messages": conversation.messages,
                    "completion": completion,
                    "usage": usage,
                    "tags": conversation.tags or [],
                    "timestamp": timestamp,
                    "plugins": conversation.plugins or [],
                    "model": conversation.model,
                },
            )
            + "\n",
        )


def create_initial_log(reinit):
    if not reinit and Path(CHAT_LOG).exists():
        raise FileExistsError(CHAT_LOG)

    if not Path(CHAT_LOG).exists():
        with Path(CHAT_LOG).open("w", encoding="utf-8") as fh:
            fh.write(json.dumps({"version": LOG_FILE_VERSION}) + "\n")

    for key, value in INITIAL_PERSONALITIES.items():
        write_log(
            Conversation(
                {
                    "messages": [{"role": "system", "content": dedent(value["content"]).strip()}],
                    "tags": ["^" + key],
                    "plugins": value.get("plugins"),
                    "model": value.get("model"),
                },
            ),
            path=CHAT_LOG,
        )


def conversation_log():
    log_path = find_log()
    with log_path.open(encoding="utf-8") as fh:
        line = json.loads(fh.readline())
        version = line.get("version")
        if version is None:
            fh.close()
            lines = list(convert_log_pre_0_4(log_path))
            backup_file = log_path.with_suffix(".log.bak.0_3")
            sys.stderr.write(f"Upgrading log file. Making backup in: {backup_file}\n")
            shutil.copyfile(log_path, backup_file)
            rewrite_log(log_path, lines)
            return [Conversation(json.loads(line)) for line in lines]
        return [Conversation(json.loads(line)) for line in fh]


def rewrite_log(path, lines):
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"version": LOG_FILE_VERSION}) + "\n")
        for line in lines:
            fh.write(line + "\n")


def find_log():
    path = CHAT_LOG
    for directory in Path(path).resolve().parents:
        if (directory / path).exists():
            return directory / path
    raise FileNotFoundError(CHAT_LOG)


def search_conversations(offsets, search, tag):
    for idx, conversation in enumerate(reversed(conversation_log()), start=1):
        if offsets and idx not in offsets:
            continue

        if search and search not in conversation:
            continue
        if tag and tag not in conversation.tags:
            continue
        yield idx, conversation


def convert_log_pre_0_4(filename):
    with Path(filename).open(encoding="utf-8") as fh:
        for line in fh:
            data = json.loads(line)

            messages = data["messages"]
            usage = data["usage"]

            if usage and "request_tokens" in usage:
                usage["prompt_tokens"] = usage["request_tokens"]
                del usage["request_tokens"]

            tags = data.get("tags", [])
            completion = data.get("completion") or data.get("response")

            timestamp = (
                data.get("timestamp")
                or (completion and datetime.fromtimestamp(completion.get("created"), tz=timezone.utc).isoformat())
                or datetime.now(tz=timezone.utc).isoformat()
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
                "model": data.get("model"),
            }
            yield json.dumps(converted_data)
