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

3. Set your OpenAI API key in the environment variable `OPENAI_API_KEY`.

## Demos

### Generate a README for this project

```
python chatcli.py --quick -f chatcli.py -p code
>> Generate a README.md for this project.
```

## Usage

### Ask a question

To ask a question, use the `chat` command:
```
python chatcli.py chat
```
This will start a conversation with the chat bot, which will prompt you for a question.

### Continue a conversation

To continue a previous conversation, use the `chat` command with the `-c` or `--continue_conversation` option:
```
python chatcli.py chat -c
```

### Specify a personality

You can specify a personality for the chat bot by using the `-p` or `--personality` option. For example, to specify the "code" personality, use the following command:
```
python chatcli.py chat -p code
```

### Show a conversation

To show a previous conversation, use the `show` command with the message offset:
```
python chatcli.py show -n 1
```

### List all questions

To list all the questions that have been asked, use the `log` command:
```
python chatcli.py log
```

### Display usage

To display the number of tokens used and the token cost, use the `usage` command:
```
python chatcli.py usage
```

## Contributing

If you wish to contribute to this project, please fork the repository and submit a pull request.
