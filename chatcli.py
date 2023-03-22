import json
from collections import defaultdict
import click
from click_default_group import DefaultGroup
import openai
from prompt_toolkit import prompt
import tiktoken

ENGINE = "gpt-3.5-turbo"
CHAT_LOG = "chatlog.log"

PERSONALITIES = {
    "concise": "You are a helpful, expert linux user and programmer. You give concise answers, providing code where possible.",
    "code": "You only answer questions with a single example code block only, and no other explanations.",
    "italiano": "You answer all questions in italian.",
}

@click.group(cls=DefaultGroup, default='chat', default_if_no_args=True)
def cli():
    pass

@cli.command(help="Ask a question of ChatGPT.")
@click.option('-q', '--quick', is_flag=True, help="Just handle a one single-line question.")
@click.option('-c', '--continue_conversation', '--continue', is_flag=True, help="Continue previous conversation.")
@click.option('-n', '--offset', type=int, help="Continue conversation from a given message offset.")
@click.option('-p', '--personality', default='concise', type=click.Choice(list(PERSONALITIES), case_sensitive=False))
@click.option('-f', '--file', type=click.Path(exists=True), multiple=True, help="Add a file to the conversation for context.")
@click.option('-r', '--retry', is_flag=True, help="Retry previous question")
def chat(quick, continue_conversation, offset, personality, file, retry):
    if (continue_conversation or retry) and not offset:
        offset = 1
    if offset:
        exchange = get_logged_exchange(offset)
        request_messages = exchange['request']
        request_messages.append(exchange['response']['choices'][0]['message'])
    else:
        request_messages = [
            {"role": "system", "content": PERSONALITIES[personality]},
        ]

    for filename in file:
        with open(filename, encoding="utf-8") as fh:
            file_contents = fh.read()
        request_messages.append({"role": "user", "content": f"The file {file} contains:\n```\n{file_contents}```"})

    if retry:
        response = answer(request_messages[:-1])
        if not quick:
            request_messages.append(response)
            conversation(request_messages)
    elif quick:
        question(request_messages, multiline=False)
    else:
        conversation(request_messages)

@cli.command(help="Show a conversation.")
@click.option('-n', '--offset', default=1, help="Message offset")
@click.option('-l/-s', '--long/--short', help="Show full conversation or just the most recent message.")
def show(offset, long):
    exchange = get_logged_exchange(offset)
    if long:
        for message in exchange['request']:
            prefix = ""
            if message['role'] == 'user':
                color = (186, 85, 211)
                prefix = ">> "
            elif message['role'] == 'system':
                color = (100, 150, 200)
            else:
                color = None
            click.echo(click.style(prefix + message["content"], fg=color))
    click.echo(exchange['response']['choices'][0]['message']["content"])

@cli.command(help="List all the questions we've asked")
@click.option('-s', '--search', help="Filter by search term")
def log(search):
    for offset, exchange in reversed(list(enumerate(reversed(conversation_log()), start=1))):
        # TODO This only exists because my log file still contains entries from earlier versions.
        if 'request' not in exchange:
            continue
        question = exchange['request'][-1]['content']
        if search and search not in question:
            continue

        trimmed_message = question.split('\n', 1)[0]
        click.echo(f"{click.style(f'{offset: 3d}:', fg='blue')} {trimmed_message}")

def conversation(request_messages, multiline=True):
    if multiline:
        click.echo("(Finish input with <Alt-Enter> or <Esc><Enter>)")

    while True:
        response_message = question(request_messages, multiline)
        if not response_message:
            break
        request_messages.append(response_message)

def question(request_messages, multiline=True):
    try:
        message = prompt(">> ", multiline=multiline, prompt_continuation=".. ")
    except EOFError:
        return None
    message = message.strip()
    if not message:
        return None
    click.echo("....")
    request_messages.append({"role": "user", "content": message})
    return answer(request_messages)

def answer(request_messages):
    completion = {}
    for chunk in openai.ChatCompletion.create(
            model=ENGINE,
            messages = request_messages,
            stream=True):

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
        if content_chunk:
            click.echo(content_chunk, nl=False)

    encoding = tiktoken.encoding_for_model(ENGINE)
    request_text = ' '.join("role: " + x['role'] + " content: " + x['content'] + "\n" for x in request_messages)
    request_tokens = len(encoding.encode(request_text))
    completion_tokens = len(encoding.encode(completion["choices"][0]["message"]["content"]))
    completion["usage"] = {
            "request_tokens": request_tokens,
             "completion_tokens": completion_tokens,
             "total_tokens": request_tokens + completion_tokens}

    click.echo()

    with open(CHAT_LOG, "a", buffering=1, encoding='utf-8') as fh:
        fh.write(json.dumps({
            'request': request_messages,
            'response': completion}) + "\n")

#   click.echo(f"Usage: ${cost(completion['usage']['total_tokens']):.3f}")
#    click.echo(response_message["content"])
    response_message = completion["choices"][0]["message"]
    return response_message

def cost(tokens):
    return tokens / 1000 * 0.002

def conversation_log():
    with open(CHAT_LOG, encoding='utf-8') as fh:
        return [json.loads(line) for line in fh]

def get_logged_exchange(offset):
    return conversation_log()[-offset]

@cli.command(help="Display number of tokens and token cost.")
def usage():
    tokens = sum(line["response"]["usage"]["total_tokens"] for line in conversation_log())
    click.echo(f'Tokens: {tokens}')
    click.echo(f'Cost: ${cost(tokens):.2f}')

if __name__ == '__main__':
    cli()
