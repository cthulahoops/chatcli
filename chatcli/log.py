import os.path
import datetime
import json

INITIAL_PERSONALITIES = {
    "concise": "You are a helpful, expert linux user and programmer. You give concise answers, providing code where possible.",
    "code": "You only answer questions with a single example code block only, and no other explanations.",
    "commit": """You generate commit messages from diffs. Every line of commit message should be less than eighty characters.
You never output anything that does not belong in the commit message.""",
}

CHAT_LOG = "chatlog.log"


def write_log(messages, completion=None, usage=None, tags=None):
    assert isinstance(messages, list)
    assert isinstance(tags, list) or tags is None
    assert isinstance(completion, dict) or completion is None
    assert isinstance(usage, dict) or usage is None
    timestamp = datetime.datetime.now().isoformat()
    with open(CHAT_LOG, "a", buffering=1, encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "messages": messages,
                    "completion": completion,
                    "usage": usage,
                    "tags": tags or [],
                    "timestamp": timestamp,
                }
            )
            + "\n"
        )


def create_initial_log():
    for key, value in INITIAL_PERSONALITIES.items():
        write_log(messages=[{"role": "system", "content": value}], tags=["^" + key])


def conversation_log():
    if not os.path.exists(CHAT_LOG):
        create_initial_log()

    with open(CHAT_LOG, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def search_exchanges(offset, search, tag):
    for idx, exchange in enumerate(reversed(conversation_log()), start=1):
        if offset and idx != offset:
            continue

        if len(exchange["messages"]) > 1:
            question = exchange["messages"][-2]["content"]
        else:
            question = exchange["messages"][-1]["content"]

        if search and search not in question:
            continue
        if tag and tag not in exchange.get("tags", []):
            continue
        yield idx, exchange


def get_logged_exchange(offset, search=None, tag=None):
    return next(search_exchanges(offset, search, tag))[1]
