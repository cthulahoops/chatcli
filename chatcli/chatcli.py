import os.path
import os
import sys
import itertools
import functools
import textwrap
import click
from click_default_group import DefaultGroup
import openai
import prompt_toolkit
import tiktoken
from .log import (
    write_log,
    search_conversations,
    get_logged_conversation,
    conversation_log,
    convert_log,
    create_initial_log,
)
from .plugins import evaluate_code_block

MODELS = [
    "gpt-4",
    "gpt-3.5-turbo",
]

MESSAGE_COLORS = {
    "user": (186, 85, 211),
    "system": (100, 150, 200),
    "assistant": None,
}


@click.group(cls=DefaultGroup, default="chat", default_if_no_args=True)
def cli():
    pass


def cli_search_options(command):
    @click.option("-n", "--offset", type=int, help="Message offset")
    @click.option("-s", "--search", help="Select by search term")
    @click.option("-t", "--tag", help="Select by tag")
    @functools.wraps(command)
    def wrapper(*args, offset=None, search=None, tag=None, **kwargs):
        return command(
            *args,
            search_options={"offset": offset, "search": search, "tag": tag},
            **kwargs,
        )

    return wrapper


@cli.command(help="Ask a question of ChatGPT.")
@click.option("-q", "--quick", is_flag=True, help="Just handle a one single-line question.")
@click.option(
    "-c",
    "--continue_conversation",
    "--continue",
    is_flag=True,
    help="Continue previous conversation.",
)
@click.option("-p", "--personality", default="concise")
@click.option(
    "-f",
    "--file",
    type=click.Path(exists=True),
    multiple=True,
    help="Add a file to the conversation for context.",
)
@click.option("-r", "--retry", is_flag=True, help="Retry previous question")
@click.option("--stream/--sync", default=True, help="Stream or sync mode.")
@click.option("--model", type=click.Choice(MODELS), default="gpt-4")
@cli_search_options
def chat(quick, continue_conversation, personality, file, retry, stream, model, search_options):
    if (continue_conversation or retry) and not search_options["offset"]:
        search_options["offset"] = 1
    elif personality and not search_options["tag"] and not search_options["search"] and not search_options["offset"]:
        search_options["tag"] = "^" + personality

    conversation = get_logged_conversation(**search_options)
    request_messages = conversation["messages"]

    for filename in file:
        with open(filename, encoding="utf-8") as fh:
            file_contents = fh.read()
        request_messages.append(
            {
                "role": "user",
                "content": f"The file {file} contains:\n```\n{file_contents}```",
            }
        )

    tags = conversation.get("tags", [])
    if tags and not tags[-1].startswith("^"):
        tags_to_apply = [tags[-1]]
    else:
        tags_to_apply = []

    if retry:
        response = answer(request_messages[:-1], model, stream=stream, tags=tags_to_apply)
        if not quick:
            request_messages.append(response)
            run_conversation(request_messages, model, stream=stream, tags=tags_to_apply)
    elif quick or not os.isatty(0):
        run_conversation(
            request_messages,
            model,
            stream=stream,
            tags=tags_to_apply,
            quick=True,
            multiline=False,
        )
    else:
        run_conversation(request_messages, model, stream=stream, tags=tags_to_apply)


@cli.command(help="Create initial conversation log.")
def init():
    try:
        create_initial_log()
    except FileExistsError as error:
        click.echo(f"{error}: Conversation log already exists.")
        sys.exit(1)


@cli.command(help="Add a message to a new or existing conversation.")
@click.option("--multiline/--singleline", default=True)
@click.option("-p", "--personality")
@click.option("--role", type=click.Choice(["system", "user", "assistant"]), default="system")
@cli_search_options
def add(personality, role, multiline, search_options):
    if any(search_options.values()):
        conversation = get_logged_conversation(**search_options)
        messages = conversation["messages"]
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
    for conversation in conversation_log():
        for tag in conversation.get("tags", []):
            tags.add(tag)
    for tag in sorted(tags):
        click.echo(tag)


@cli.command(help="Add tags to an conversation.", name="tag")
@cli_search_options
@click.argument("tags", nargs=-1)
def add_tag(tags, search_options):
    conversation = get_logged_conversation(**search_options)
    new_tags = [tag for tag in conversation.get("tags", []) if tag not in tags]
    new_tags.extend(tags)

    write_log(messages=conversation["messages"], tags=new_tags)


@cli.command(help="Remove tags from an conversation.")
@cli_search_options
@click.argument("tags", nargs=-1)
def untag(tags, search_options):
    conversation = get_logged_conversation(**search_options)
    new_tags = [t for t in conversation.get("tags", []) if t not in tags]
    write_log(messages=conversation["messages"], tags=new_tags)


@cli.command(help="Current tag")
@cli_search_options
def show_tag(search_options):
    conversation = get_logged_conversation(**search_options)
    tags = conversation.get("tags", [])

    if tags:
        click.echo(tags[-1])


@cli.command(help="Show a conversation.")
@cli_search_options
@click.option(
    "-l/-s",
    "--long/--short",
    help="Show full conversation or just the most recent message.",
)
def show(long, search_options):
    conversation = get_logged_conversation(**search_options)
    if long:
        messages = conversation["messages"]
    else:
        messages = conversation["messages"][-1:]

    for message in messages:
        prefix = ""
        if message["role"] == "user":
            prefix = ">> "
        click.echo(click.style(prefix + message["content"], fg=MESSAGE_COLORS[message["role"]]))


@cli.command(help="List all the questions we've asked")
@cli_search_options
@click.option("-l", "--limit", type=int, help="Limit number of results")
@click.option("-u", "--usage", is_flag=True, help="Show token usage")
def log(limit, usage, search_options):
    for offset, conversation in reversed(list(itertools.islice(search_conversations(**search_options), limit))):
        try:
            question = find_recent_message(lambda message: message["role"] != "assistant", conversation)["content"]
        except ValueError:
            question = conversation["messages"][-1]["content"]
        trimmed_message = question.split("\n", 1)[0][:80]

        fields = []
        offset = click.style(f"{offset: 4d}:", fg="blue")
        fields.append(offset)

        if usage:
            if conversation["usage"]:
                total_tokens = conversation["usage"]["total_tokens"]
            else:
                total_tokens = 0
            fields.append(f"{total_tokens: 5d}")

        fields.append(trimmed_message)
        if conversation.get("tags"):
            fields.append(click.style(f"{' '.join(conversation['tags'])}", fg="green"))

        click.echo(" ".join(fields))


@cli.command(
    help=textwrap.dedent(
        """Convert old chatlog format to new format.
    Recommended usage:

    \b
    cp -i chatlog.json chatlog.json.bak
    chatlog convert chatlog.json.bak > chatlog.json
    """
    )
)
@click.argument("filename", type=click.Path(exists=True))
def convert(filename):
    for line in convert_log(filename):
        print(line)


def run_conversation(request_messages, model, tags=None, stream=True, multiline=True, quick=False):
    if multiline and os.isatty(0):
        click.echo("(Finish input with <Alt-Enter> or <Esc><Enter>)")

    while True:
        question = prompt(multiline=multiline)
        if not question:
            break
        request_messages.append({"role": "user", "content": question})
        response_message = answer(request_messages, model, stream=stream, tags=tags)
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


def synchroneous_request(request_messages, model):
    completion = openai.ChatCompletion.create(model=model, messages=request_messages)
    click.echo(completion["choices"][0]["message"]["content"])
    return completion


def stream_request(request_messages, model):
    completion = {}
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
        if content_chunk:
            click.echo(content_chunk, nl=False)

    click.echo()
    return completion


def completion_usage(request_messages, model, completion):
    if "usage" in completion:
        return completion["usage"]

    encoding = tiktoken.encoding_for_model(model)
    request_text = " ".join("role: " + x["role"] + " content: " + x["content"] + "\n" for x in request_messages)
    request_tokens = len(encoding.encode(request_text))
    completion_tokens = len(encoding.encode(completion["choices"][0]["message"]["content"]))
    return {
        "prompt_tokens": request_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": request_tokens + completion_tokens,
    }


def answer(request_messages, model, stream=True, tags=None):
    if stream:
        completion = stream_request(request_messages, model)
    else:
        completion = synchroneous_request(request_messages, model)

    response_message = completion["choices"][0]["message"]

    write_log(
        messages=request_messages + [response_message],
        completion=completion,
        usage=completion_usage(request_messages, model, completion),
        tags=tags,
    )

    code_response = evaluate_code_block(response_message["content"])
    if code_response:
        print(code_response)
        return answer(request_messages + [response_message, {"role": "user", "content": code_response}], model, stream=stream, tags=tags)

    return response_message


def cost(tokens):
    return tokens / 1000 * 0.002


def find_recent_message(predicate, conversation):
    for message in reversed(conversation["messages"]):
        if predicate(message):
            return message
    raise ValueError("No matching message found")


@cli.command(help="Display number of tokens and token cost.", name="usage")
def show_usage():
    tokens = sum(conversation["usage"]["total_tokens"] for conversation in conversation_log() if conversation["usage"])
    click.echo(f"Tokens: {tokens}")
    click.echo(f"Cost: ${cost(tokens):.2f}")


def main():
    try:
        cli()
    except FileNotFoundError as error:
        click.echo(f"{error}: Chatlog not initialized. Run `chatlog init` first.")
        sys.exit(1)


if __name__ == "__main__":
    main()
