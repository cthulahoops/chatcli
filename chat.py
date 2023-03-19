import json
import sys
import click
from click_default_group import DefaultGroup
import openai
from prompt_toolkit import prompt

ENGINE = "gpt-3.5-turbo"
CHAT_LOG = "chatlog.log"

@click.group(cls=DefaultGroup, default='chat', default_if_no_args=True)
def cli():
    pass

@cli.command()
@click.option('-q', '--quick', is_flag=True, help="Just handle a one single-line question.")
@click.option('-c', '--continue_conversation', is_flag=True, help="Continue previous conversation.")
@click.option('-n', '--offset', default=1, help="Message offset")
def chat(quick, continue_conversation, offset):
    if continue_conversation:
        exchange = get_logged_exchange(offset)
        request_messages = exchange['request']
        request_messages.append(exchange['response']['choices'][0]['message'])
    else:
        request_messages = [
            {"role": "system", "content": "You are helpful, expert linux user and programmer. You give concise answers, providing code where possible."},
        ]

    if quick:
        question(request_messages, multiline=False)
    else:
        conversation(request_messages)

@cli.command()
@click.option('-n', '--offset', default=1, help="Message offset")
def show(offset):
    exchange = get_logged_exchange(offset)
    print(exchange['response']['choices'][0]['message']["content"])


def conversation(request_messages):
    while True:
        response_message = question(request_messages)
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
    print("....")
    request_messages.append({"role": "user", "content": message})

    completion = openai.ChatCompletion.create(
        model=ENGINE,
        messages = request_messages
    )

    with open(CHAT_LOG, "a", buffering=1, encoding='utf-8') as fh:
        fh.write(json.dumps({
            'request': request_messages,
            'response': completion}) + "\n")

    print(f"Usage: ${cost(completion['usage']['total_tokens']):.3f}")
    response_message = completion["choices"][0]["message"]
    print(response_message["content"])
    return response_message

def cost(tokens):
    return tokens / 1000 * 0.002

def get_logged_exchange(offset):
    with open(CHAT_LOG, encoding='utf-8') as fh:
        return json.loads(fh.readlines()[-offset])

@cli.command()
def usage():
    with open(CHAT_LOG, encoding="utf-8") as fh:
        click.echo(f'${cost(sum(json.loads(line)["response"]["usage"]["total_tokens"] for line in fh)):.2f}')

if __name__ == '__main__':
    cli()
