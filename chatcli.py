import json
import os.path
import itertools
import click
from click_default_group import DefaultGroup
import openai
from prompt_toolkit import prompt
import tiktoken

ENGINE = "gpt-3.5-turbo"
CHAT_LOG = "chatlog.log"

INITIAL_PERSONALITIES = {
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
@click.option('-p', '--personality', default='concise')
@click.option('-f', '--file', type=click.Path(exists=True), multiple=True, help="Add a file to the conversation for context.")
@click.option('-r', '--retry', is_flag=True, help="Retry previous question")
@click.option('--stream/--sync', default=True, help="Stream or sync mode.")
@click.option('-n', '--offset', type=int, help="Continue conversation from a given message offset.")
@click.option('-s', '--search', help="Select by search term")
@click.option('-t', '--tag', help="Select by tag")
def chat(quick, continue_conversation, personality, file, retry, stream, **search_options):
    if (continue_conversation or retry) and not search_options['offset']:
        search_options["offset"] = 1
    elif personality and not search_options['tag'] and not search_options['search']:
        search_options["tag"] = "^" + personality

    exchange = get_logged_exchange(**search_options)
    request_messages = exchange['request']
    if exchange['response']:
        request_messages.append(exchange['response']['choices'][0]['message'])

    for filename in file:
        with open(filename, encoding="utf-8") as fh:
            file_contents = fh.read()
        request_messages.append({"role": "user", "content": f"The file {file} contains:\n```\n{file_contents}```"})

    if retry:
        response = answer(request_messages[:-1], stream)
        if not quick:
            request_messages.append(response)
            conversation(request_messages, stream)
    elif quick:
        question(request_messages, stream, multiline=False)
    else:
        conversation(request_messages, stream)

@cli.command(help="Add new personality.")
@click.argument('name')
def add(name):
    description = prompt("Description: ")
    exchange = {'request': [{"role": "system", "content": description}], 'response': None, 'tags': ["^" + name]}
    write_log(exchange)


@cli.command(help="List tags.")
def tags():
    for exchange in conversation_log():
        for tag in exchange.get("tags", []):
            click.echo(tag)

@cli.command(help="Add tags to an exchange.")
@click.option('-n', '--offset', type=int, help="Message offset")
@click.option('-s', '--search', help="Select by search term")
@click.option('-t', '--tag', help="Select by tag")
@click.argument('tags', nargs=-1)
def tag(tags, **search_options):
    exchange = get_logged_exchange(**search_options)
    exchange['tags'] = [tag for tag in exchange.get('tags', []) if tag not in tags]
    exchange['tags'].extend(tags)
    write_log(exchange)


@cli.command(help="Show a conversation.")
@click.option('-n', '--offset', type=int, help="Message offset")
@click.option('-s', '--search', help="Select by search term")
@click.option('-t', '--tag', help="Select by tag")
@click.option('-l/-s', '--long/--short', help="Show full conversation or just the most recent message.")
def show(long, **search_options):
    print(search_options)
    exchange = get_logged_exchange(**search_options)
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
@click.option('-n', '--offset', type=int, help="Message offset")
@click.option('-s', '--search', help="Filter by search term")
@click.option('-t', '--tag', help="Filter by tag")
@click.option('-l', '--limit', type=int, help="Limit number of results")
def log(limit, **search_options):
    for offset, exchange in reversed(list(itertools.islice(search_exchanges(**search_options), limit))):
        question = exchange['request'][-1]['content']

        trimmed_message = question.split('\n', 1)[0][:80]
        tags = click.style(f"{' '.join(exchange.get('tags', []))}", fg='green')
        click.echo(f"{click.style(f'{offset: 3d}:', fg='blue')} {trimmed_message} {tags}")

def conversation(request_messages, stream=True, multiline=True):
    if multiline:
        click.echo("(Finish input with <Alt-Enter> or <Esc><Enter>)")

    while True:
        response_message = question(request_messages, stream, multiline)
        if not response_message:
            break
        request_messages.append(response_message)

def question(request_messages, stream=True, multiline=True):
    try:
        message = prompt(">> ", multiline=multiline, prompt_continuation=".. ")
    except EOFError:
        return None
    message = message.strip()
    if not message:
        return None
    click.echo("....")
    request_messages.append({"role": "user", "content": message})
    return answer(request_messages, stream)


def synchroneous_request(request_messages):
    completion = openai.ChatCompletion.create(
        model=ENGINE,
        messages=request_messages)
    click.echo(completion["choices"][0]["message"]["content"])
    return completion

def stream_request(request_messages):
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
    return completion

def answer(request_messages, stream=True):
    if stream:
        completion = stream_request(request_messages)
    else:
        completion = synchroneous_request(request_messages)

    write_log({'request': request_messages, 'response': completion})

#   click.echo(f"Usage: ${cost(completion['usage']['total_tokens']):.3f}")
#    click.echo(response_message["content"])
    response_message = completion["choices"][0]["message"]
    return response_message

def cost(tokens):
    return tokens / 1000 * 0.002

def write_log(message):
    with open(CHAT_LOG, "a", buffering=1, encoding='utf-8') as fh:
        fh.write(json.dumps(message) + "\n")


def create_initial_log():
    for key, value in INITIAL_PERSONALITIES.items():
        write_log({"request": [{"role": "system", "content": value}], "response": {}, "tags": ["^" + key]})

def conversation_log():
    if not os.path.exists(CHAT_LOG):
        create_initial_log()

    with open(CHAT_LOG, encoding='utf-8') as fh:
        return [json.loads(line) for line in fh]

def search_exchanges(offset, search, tag):
    for idx, exchange in enumerate(reversed(conversation_log()), start=1):
        # TODO This only exists because my log file still contains entries from earlier versions.
        if 'request' not in exchange:
            continue
        if offset and idx != offset:
            continue
        if search and search not in exchange['request'][-1]['content']:
            continue
        if tag and tag not in exchange.get('tags', []):
            continue
        yield idx, exchange

def get_logged_exchange(offset, search=None, tag=None):
    return next(search_exchanges(offset, search, tag))[1]

def get_tagged_exchange(tag):
    for exchange in reversed(conversation_log()):
        if 'tags' in exchange and tag in exchange['tags']:
            return exchange
    raise click.ClickException(f"No exchange with tag {tag} found.")

@cli.command(help="Display number of tokens and token cost.")
def usage():
    tokens = sum(line["response"]["usage"]["total_tokens"] for line in conversation_log() if line["response"])
    click.echo(f'Tokens: {tokens}')
    click.echo(f'Cost: ${cost(tokens):.2f}')

if __name__ == '__main__':
    cli()
