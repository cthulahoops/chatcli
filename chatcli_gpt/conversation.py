import json


class Conversation:
    def __init__(self, messages=None, plugins=None, tags=None, model=None, usage=None, completion=None, timestamp=None):
        self.messages = messages or []
        self.plugins = plugins or []
        self.tags = tags or []
        self.model = model
        self.usage = usage
        self.completion = completion
        self.timestamp = timestamp

    def append(self, message):
        self.messages.append(message)

    def __contains__(self, search_term):
        if len(self.messages) > 1:
            question = self.messages[-2]["content"]
        else:
            question = self.messages[-1]["content"]
        return search_term in question

    def to_json(self):
        return json.dumps(self.__dict__)
