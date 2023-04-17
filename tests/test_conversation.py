from chatcli_gpt.conversation import Conversation


def test_find_recent_message():
    conversation = Conversation(
        {
            "messages": [
                {"role": "assistant", "message": "???"},
                {"role": "user", "message": "hello"},
                {"role": "assistant", "message": "hi"},
                {"role": "user", "message": "how are you?"},
            ],
        },
    )

    def predicate(msg):
        return msg["role"] == "assistant"

    result = conversation.find(predicate)
    expected = {"role": "assistant", "message": "hi"}

    assert result == expected
