import json
import os.path
import os
import sys
import itertools
import functools
import click
from click_default_group import DefaultGroup
import openai
import prompt_toolkit
import tiktoken

ENGINE = "gpt-3.5-turbo"
CHAT_LOG = "chatlog.log"

INITIAL_PERSONALITIES = {
    "concise": "You are a helpful, expert linux user and programmer. You give concise answers, providing code where possible.",
    "code": "You only answer questions with a single example code block only, and no other explanations.",
    "commit": """You generate commit messages from diffs. Every line of commit message should be less than eighty characters.
You never output anything that does not belong in the commit message."""
}

@click.group(cls=DefaultGroup, default='chat', default_if_no_args=True)
def cli():
    pass

def cli_search_options(command):
    @click.option('-n', '--offset', type=int, help="Message offset")
    @click.option('-s', '--search', help="Select by search term")
    @click.option('-t', '--tag', help="Select by tag")
    @functools.wraps(command)
    def wrapper(*args, offset=None, search=None, tag=None, **kwargs):
        return command(*args, search_options={
            'offset': offset,
            'search': search,
            'tag': tag}, **kwargs)
    return wrapper

@cli.command(help="Ask a question of ChatGPT.")
@click.option('-q', '--quick', is_flag=True, help="Just handle a one single-line question.")
@click.option('-c', '--continue_conversation', '--continue', is_flag=True, help="Continue previous conversation.")
@click.option('-p', '--personality', default='concise')
@click.option('-f', '--file', type=click.Path(exists=True), multiple=True, help="Add a file to the conversation for context.")
@click.option('-r', '--retry', is_flag=True, help="Retry previous question")
@click.option('--stream/--sync', default=True, help="Stream or sync mode.")
@cli_search_options
def chat(quick, continue_conversation, personality, file, retry, stream, search_options):
    if (continue_conversation or retry) and not search_options['offset']:
        search_options["offset"] = 1
    elif personality and not search_options['tag'] and not search_options['search'] and not search_options['offset']:
        search_options["tag"] = "^" + personality

    exchange = get_logged_exchange(**search_options)
    request_messages = exchange['messages']

    for filename in file:
        with open(filename, encoding="utf-8") as fh:
            file_contents = fh.read()
        request_messages.append({"role": "user", "content": f"The file {file} contains:\n```\n{file_contents}```"})

    tags = exchange.get('tags', [])
    if tags and not tags[-1].startswith("^"):
        tags_to_apply = [tags[-1]]
    else:
        tags_to_apply = []

    if retry:
        response = answer(request_messages[:-1], stream=stream, tags=tags_to_apply)
        if not quick:
            request_messages.append(response)
            conversation(request_messages, stream=stream, tags=tags_to_apply)
    elif quick or not os.isatty(0):
        conversation(request_messages, stream=stream, tags=tags_to_apply, quick=True, multiline=False)
    else:
        conversation(request_messages, stream=stream, tags=tags_to_apply)

@cli.command(help="Add a message to a new or existing conversation.")
@click.option('--multiline/--singleline', default=True)
@click.option('-p', '--personality')
@click.option('--role', type=click.Choice(['system', 'user', 'assistant']), default='system')
@cli_search_options
def add(personality, role, multiline, search_options):
    if any(search_options.values()):
        exchange = get_logged_exchange(**search_options)
        messages = exchange['messages']
    else:
        messages = []

    tags = []
    if personality:
        tags.append("^" + personality)

    if multiline and os.isatty(0):
        click.echo("(Finish input with <Alt-Enter> or <Esc><Enter>)")
    description = prompt(multiline=True)
    messages.append({"role": role, "content": description})
    write_log(messages=messages, tags=tags)


@cli.command(help="List tags.", name="tags")
def list_tags():
    tags = set()
    for exchange in conversation_log():
        for tag in exchange.get("tags", []):
            tags.add(tag)
    for tag in sorted(tags):
        click.echo(tag)

@cli.command(help="Add tags to an exchange.", name="tag")
@cli_search_options
@click.argument('tags', nargs=-1)
def add_tag(tags, search_options):
    exchange = get_logged_exchange(**search_options)
    new_tags = [tag for tag in exchange.get('tags', []) if tag not in tags]
    new_tags.extend(tags)

    write_log(messages=exchange['messages'], tags=new_tags)

@cli.command(help="Remove tags from an exchange.")
@cli_search_options
@click.argument('tags', nargs=-1)
def untag(tags, search_options):
    exchange = get_logged_exchange(**search_options)
    new_tags = [t for t in exchange.get('tags', []) if t not in tags]
    write_log(messages=exchange['messages'], tags=new_tags)

@cli.command(help="Current tag")
@cli_search_options
def show_tag(search_options):
    exchange = get_logged_exchange(**search_options)
    tags = exchange.get('tags', [])

    if tags:
        click.echo(tags[-1])

@cli.command(help="Show a conversation.")
@cli_search_options
@click.option('-l/-s', '--long/--short', help="Show full conversation or just the most recent message.")
def show(long, search_options):
    exchange = get_logged_exchange(**search_options)
    if long:
        messages = exchange["messages"]
    else:
        messages = exchange["messages"][-1:]

    for message in messages:
        prefix = ""
        if message['role'] == 'user':
            color = (186, 85, 211)
            prefix = ">> "
        elif message['role'] == 'system':
            color = (100, 150, 200)
        else:
            color = None
        click.echo(click.style(prefix + message["content"], fg=color))


@cli.command(help="List all the questions we've asked")
@cli_search_options
@click.option('-l', '--limit', type=int, help="Limit number of results")
def log(limit, search_options):
    for offset, exchange in reversed(list(itertools.islice(search_exchanges(**search_options), limit))):
        messages = exchange['messages']
        if len(messages) > 1:
            question = exchange['messages'][-2]['content']
        else:
            question = exchange['messages'][-1]['content']

        trimmed_message = question.split('\n', 1)[0][:80]
        tags = click.style(f"{' '.join(exchange.get('tags', []))}", fg='green')
        click.echo(f"{click.style(f'{offset: 3d}:', fg='blue')} {trimmed_message} {tags}")


# Add command to convert old chatlog format:
@cli.command(help="Convert old chatlog format to new format.")
@click.argument('filename', type=click.Path(exists=True))
def convert(filename, inplace=False):
    with open(filename, "r") as fh:
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

            tags = data.get("tags", [])
            completion = data.get("completion") or data.get("response")

            assert isinstance(messages, list), data
            assert isinstance(tags, list), data
            assert isinstance(completion, dict) or completion is None, (completion, data)
            assert isinstance(usage, dict) or usage is None, (usage, data)

            converted_data = {
                "messages": messages,
                "completion": completion,
                "tags": tags,
                "usage": usage,
            }
            print(json.dumps(converted_data))


def conversation(request_messages, tags=None, stream=True, multiline=True, quick=False):
    if multiline and os.isatty(0):
        click.echo("(Finish input with <Alt-Enter> or <Esc><Enter>)")

    while True:
        question = prompt(multiline=multiline)
        if not question:
            break
        request_messages.append({"role": "user", "content": question})
        response_message = answer(request_messages, stream=stream, tags=tags)
        request_messages.append(response_message)

        if quick:
            break

def prompt(multiline=True):
    if os.isatty(0):
        try:
            return prompt_toolkit.prompt(">> ", multiline=multiline, prompt_continuation=".. ").strip()
        except EOFError:
            return None
        click.echo("....")
    else:
        return sys.stdin.read().strip()


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

    click.echo()
    return completion

def completion_usage(request_messages, completion):
    if 'usage' in completion:
        return completion['usage']

    encoding = tiktoken.encoding_for_model(ENGINE)
    request_text = ' '.join("role: " + x['role'] + " content: " + x['content'] + "\n" for x in request_messages)
    request_tokens = len(encoding.encode(request_text))
    completion_tokens = len(encoding.encode(completion["choices"][0]["message"]["content"]))
    return {
            "request_tokens": request_tokens,
             "completion_tokens": completion_tokens,
             "total_tokens": request_tokens + completion_tokens}

def answer(request_messages, stream=True, tags=None):
    if stream:
        completion = stream_request(request_messages)
    else:
        completion = synchroneous_request(request_messages)

    response_message = completion["choices"][0]["message"]

    write_log(
            messages = request_messages + [response_message],
            completion = completion,
            usage = completion_usage(request_messages, completion),
            tags = tags)

    return response_message

def cost(tokens):
    return tokens / 1000 * 0.002

def write_log(messages, completion=None, usage=None, tags=None):
    assert isinstance(messages, list)
    assert isinstance(tags, list) or tags is None
    assert isinstance(completion, dict) or completion is None
    assert isinstance(usage, dict) or usage is None
    with open(CHAT_LOG, "a", buffering=1, encoding='utf-8') as fh:
        fh.write(json.dumps({
            "messages": messages,
            "completion": completion,
            "usage": usage,
            "tags": tags or []}) + "\n")


def create_initial_log():
    for key, value in INITIAL_PERSONALITIES.items():
        write_log(messages=[{"role": "system", "content": value}], tags=["^" + key])

def conversation_log():
    if not os.path.exists(CHAT_LOG):
        create_initial_log()

    with open(CHAT_LOG, encoding='utf-8') as fh:
        return [json.loads(line) for line in fh]

def search_exchanges(offset, search, tag):
    for idx, exchange in enumerate(reversed(conversation_log()), start=1):
        if offset and idx != offset:
            continue

        if len(exchange['messages']) > 1:
            question = exchange['messages'][-2]['content']
        else:
            question = exchange['messages'][-1]['content']

        if search and search not in question:
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

@cli.command(help="Display number of tokens and token cost.", name="usage")
def show_usage():
    tokens = sum(exchange["usage"]["total_tokens"] for exchange in conversation_log() if exchange["usage"])
    click.echo(f'Tokens: {tokens}')
    click.echo(f'Cost: ${cost(tokens):.2f}')

if __name__ == '__main__':
    cli()
