import os
from pathlib import Path
import json

import click
from click_default_group import DefaultGroup

OPEN_ROUTER_API_KEY = os.environ.get("OPEN_ROUTER_API_KEY")

MODEL_CACHE = Path("/home/akelly/.chatcli.models.json")

OPEN_AI_MODELS = [
    "gpt-4-1106-preview",
    "gpt-3.5-turbo-1106",
    "gpt-4",
    "gpt-3.5-turbo",
]

# Create the above LIST but in the format [{ "id": "gpt-4-1106-preview" }, ...]
OPEN_AI_MODELS = [
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

MODELS = OPEN_AI_MODELS
if MODEL_CACHE.exists():
    MODELS += json.load(MODEL_CACHE.open())


@click.group(cls=DefaultGroup, default="list", default_if_no_args=True)
def models():
    pass


@models.command(name="list")
def list_models():
    for model in MODELS:
        click.echo(f"{model['id']}")


@models.command(name="fetch")
def fetch():
    models = list(fetch_models())
    json.dump(models, MODEL_CACHE.open("w"))


def fetch_models():
    if OPEN_ROUTER_API_KEY:
        for model in fetch_open_router_models():
            model["id"] = f"openrouter/{model['id']}"
            yield model


def fetch_open_router_models():
    import openai

    return openai.Model.list(
        api_base="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPEN_ROUTER_API_KEY"),
    )["data"]


def api_base(model):
    if model.startswith("openrouter/"):
        return "https://openrouter.ai/api/v1"
    return "https://api.openai.com/v1"


def api_key(model):
    if model.startswith("openrouter/"):
        return os.environ.get("OPEN_ROUTER_API_KEY")
    return os.environ.get("OPEN_AI_API_KEY")


def api_model_name(model):
    if model.startswith("openrouter/"):
        return model[len("openrouter/") :]
    return model
