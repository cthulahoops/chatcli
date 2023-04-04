#!/usr/bin/env sh

docker run -it \
    -e OPENAI_API_KEY="$OPENAI_API_KEY" \
    -v "$(pwd)":/home \
    -v "/tmp":/tmp gpt_in_box:latest \
    poetry run chatcli $@
