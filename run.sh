#!/usr/bin/env sh

docker run -it \
    -e OPENAI_API_KEY="$OPENAI_API_KEY" \
    -v "$(pwd)":/code \    # mount the current src directory
    -v "/tmp":/tmp gpt_in_box:latest \
    poetry run chatcli $@
