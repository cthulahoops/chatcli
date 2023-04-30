import json
import signal
from contextlib import contextmanager
from dataclasses import dataclass


class Conversation:
    def __init__(self, conversation_data):
        self.messages = conversation_data.get("messages", [])
        self.plugins = conversation_data.get("plugins", [])
        self.tags = conversation_data.get("tags", [])
        self.model = conversation_data.get("model")
        self.usage = conversation_data.get("usage")
        self.completion = conversation_data.get("completion")
        self.timestamp = conversation_data.get("timestamp")

    def append(self, role, content):
        self.messages.append({"role": role, "content": content})

    def __contains__(self, search_term):
        question = self.messages[-2]["content"] if len(self.messages) > 1 else self.messages[-1]["content"]
        return search_term in question

    def to_json(self):
        return json.dumps(self.__dict__)

    def find(self, predicate):
        for message in reversed(self.messages):
            if predicate(message):
                return message
        raise ValueError("No matching message found")

    def complete(self, *, stream=True, callback=None):
        if stream:
            completion = stream_request(self.messages, self.model, callback)
        else:
            completion = synchroneous_request(self.messages, self.model, callback)

        # TODO: handle multiple choices
        response_message = completion["choices"][0]["message"]
        self.append(**response_message)
        self.completion = completion
        self.usage = completion_usage(self.messages[:-1], self.model, completion)

        return response_message


def completion_usage(request_messages, model, completion):
    if "usage" in completion:
        return completion["usage"]

    import tiktoken

    encoding = tiktoken.encoding_for_model(model)
    request_text = " ".join("role: " + x["role"] + " content: " + x["content"] + "\n" for x in request_messages)
    request_tokens = len(encoding.encode(request_text))
    completion_tokens = len(encoding.encode(completion["choices"][0]["message"]["content"]))
    return {
        "prompt_tokens": request_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": request_tokens + completion_tokens,
    }


def synchroneous_request(request_messages, model, callback):
    import openai

    completion = openai.ChatCompletion.create(model=model, messages=request_messages)
    if callback:
        callback(completion["choices"][0]["message"]["content"])
    return completion


@contextmanager
def handle_sigint():
    @dataclass
    class State:
        running: bool

    state = State(running=True)

    def handle_sigint(_signal, _frame):
        state.running = False

    try:
        signal.signal(signal.SIGINT, handle_sigint)
        yield state
    finally:
        signal.signal(signal.SIGINT, signal.SIG_DFL)


def stream_request(request_messages, model, callback):
    import openai

    completion = {}
    with handle_sigint() as state:
        for chunk in openai.ChatCompletion.create(model=model, messages=request_messages, stream=True):
            if not completion:
                for key, value in chunk.items():
                    completion[key] = value
                completion["choices"] = [{"message": {}} for choice in chunk["choices"]]

            for choice in chunk["choices"]:
                if choice.get("delta"):
                    for key, value in choice["delta"].items():
                        message = completion["choices"][choice["index"]]["message"]
                        if key not in message:
                            message[key] = ""
                        message[key] += value

            content_chunk = chunk["choices"][0]["delta"].get("content")
            if content_chunk and callback:
                callback(content_chunk, nl=False)

            if not state.running:
                callback("\nInterrupted by user.\n")
                break

        callback()

    return completion
