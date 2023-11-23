import os
import sys
from pathlib import Path
import json

import click
from click_default_group import DefaultGroup

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

MODEL_CACHE = Path("/home/akelly/.chatcli.models.json")

OPENAI_MODELS = [
    "gpt-4-1106-preview",
    "gpt-3.5-turbo-1106",
    "gpt-4",
    "gpt-3.5-turbo",
]

# Create the above LIST but in the format [{ "id": "gpt-4-1106-preview" }, ...]
OPENAI_MODELS = [
    {
        "id": "gpt-4-1106-preview",
        "pricing": {"prompt": 0.01, "completion": 0.03},
    },
    {
        "id": "gpt-3.5-turbo-1106",
        "pricing": {"prompt": 0.001, "completion": 0.002},
    },
    {
        "id": "gpt-4",
        "pricing": {"prompt": 0.03, "completion": 0.06},
    },
    {
        "id": "gpt-3.5-turbo",
        "pricing": {"prompt": 0.002, "completion": 0.002},
    },
]

MODELS = OPENAI_MODELS
if MODEL_CACHE.exists():
    MODELS += json.load(MODEL_CACHE.open())


@click.group(cls=DefaultGroup, default="list", default_if_no_args=True, help="View and manage models")
def models():
    pass


@models.command(name="list", help="List available models")
def list_models():
    for model in MODELS:
        click.echo(f"{model['id']}")


@models.command(name="fetch", help="Fetch models from a source.")
@click.argument("source", type=click.Choice(choices=["openrouter"]))
def fetch(source):
    if source == "openrouter":
        if not OPENROUTER_API_KEY:
            click.echo("OPENROUTER_API_KEY not set", file=sys.stderr)
            sys.exit(1)
        models = list(fetch_openrouter_models())
        json.dump(models, MODEL_CACHE.open("w"))


def fetch_openrouter_models():
    import openai

    for model in openai.Model.list(
        api_base=api_base("openrouter/"),
        api_key=api_key("openrouter/"),
    )["data"]:
        model["id"] = f"openrouter/{model['id']}"
        yield model


def api_base(model):
    if model.startswith("openrouter/"):
        return "https://openrouter.ai/api/v1"
    return "https://api.openai.com/v1"


def api_key(model):
    if model.startswith("openrouter/"):
        return os.environ.get("OPENROUTER_API_KEY")
    return os.environ.get("OPENAI_API_KEY")


def api_model_name(model):
    if model.startswith("openrouter/"):
        return model[len("openrouter/") :]
    return model
