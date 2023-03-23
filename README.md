# ChatCLI

ChatCLI is a command-line tool that uses the OpenAI GPT-3 API to provide a chat bot interface that can answer your questions. It provides a simple and intuitive way to interact with GPT-3 by asking questions and getting relevant answers.

## Installation

The following steps will guide you through the installation process:

1. Clone the repository with the following command:
```
git clone https://github.com/cthulahoops/chatcli.git
```

2. Install the required dependencies:
```
pip install -r requirements.txt
```

3. Set your OpenAI API key in the environment variable `OPENAI_API_SECRET_KEY`.

## Usage

### Ask a question

To ask a question, use the `chat` command:
```
python chatcli.py chat
```
This will start a conversation with the chat bot, which will prompt you for a question. You can also include a text file as context for your question by using the `-f` or `--file` option:
```
python chatcli.py chat --file myfile.txt
```

You can also specify the personality that the chat bot should use with the `-p` or `--personality` option:
```
python chatcli.py chat --personality concise
```

### Continue a conversation

To continue a previous conversation, use the `chat` command with the `--continue` option:
```
python chatcli.py chat --continue
```

### Show a conversation

To show a previous conversation, use the `show`:
```
python chatcli.py show
```

### List all conversations

To list all the conversations that have been logged, use the `log` command:
```
python chatcli.py log
```

### Tag a conversation

You can tag a conversation using the `tag` command:
```
python chatcli.py tag mytag
```

### List all tags

To list all the tags that have been used, use the `tags` command:
```
python chatcli.py tags
```

### Filter by tag

You can filter conversations by tag using the `-t` or `--tag` option:
```
python chatcli.py log --tag mytag
```

### Remove a tag

You can remove a tag from a conversation using the `untag` command:
```
python chatcli.py untag mytag
```

### Display usage

To display the number of tokens used and the token cost, use the `usage` command:
```
python chatcli.py usage
```

## Examples

### Generate a README for this project

```
python chatcli.py --quick --file chatcli.py --personality code
>> Generate a README.md for this project.
```

## Contributing

If you wish to contribute to this project, please fork the repository and submit a pull request.
