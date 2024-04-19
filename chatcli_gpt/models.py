import os
import sys
from pathlib import Path
import json

import click
from click_default_group import DefaultGroup

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

MODEL_CACHE = Path.home() / ".chatcli.models.json"

OPENAI_MODELS = [
    {
        "id": "gpt-4-1106-preview",
        "pricing": {"prompt": 0.01 / 1000, "completion": 0.03 / 1000},
    },
    {
        "id": "gpt-3.5-turbo-1106",
        "pricing": {"prompt": 0.001 / 1000, "completion": 0.002 / 1000},
    },
    {
        "id": "gpt-4",
        "pricing": {"prompt": 0.03 / 1000, "completion": 0.06 / 1000},
    },
    {
        "id": "gpt-3.5-turbo",
        "pricing": {"prompt": 0.002 / 1000, "completion": 0.002 / 1000},
    },
]


_MODELS = None


def get_models():
    global _MODELS  # noqa: PLW0603

    if _MODELS is None:
        _MODELS = []
        _MODELS.extend(OPENAI_MODELS)
        if MODEL_CACHE.exists():
            _MODELS += json.load(MODEL_CACHE.open())
    return _MODELS


MODELS = get_models()


@click.group(
    cls=DefaultGroup,
    default="list",
    default_if_no_args=True,
    help="View and manage models",
)
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
