# ChatCLI

ChatCLI is a command-line tool that uses the OpenAI GPT-3.5/GPT-4 API to
provide a chat bot interface that can answer your questions. It provides a
simple and intuitive way to interact with GPT by asking questions and getting
relevant answers.

This command is in early development and the interface and log file format are
unstable and changing rapidly. I'd love to get feedback on what would make this
tool more useful.

WARNING: This version supports EVALUATE blocks that allow GPT to evaluate code.
This should only work if the pyeval plugin is enabled, either using "--plugin pyeval"
or "--personality pyeval". There is no sandboxing, so GPT can run any code it
likes if you enable this!

## Installation

The following steps will guide you through the installation process:

1. Install with pip:

```
pip install chatcli-gpt
```

### Running chatcli

2. Initialise the log:

```
chatcli init
```

3. Set your OpenAI API key in the environment variable `OPENAI_API_KEY`.

4. Run chatcli

```
chatcli
```

5. See all the commands available:
```
chatcli --help
```

## Usage

### Ask a question

To ask a question, just run chatcli:

```
chatcli
```

This will start a conversation with the chat bot, which will prompt you for a
question. You can also include a text file as context for your question by
using the `-f` or `--file` option:

```
chatcli --file myfile.txt
```

You can continue a previous conversation with the `--continue` option:

```
chatcli --continue
```

You can select the model you wish to use with the `--model` option, and retry
the previous interaction with `--retry`. So to retry the previous question with GPT-4
just do:

```
chatcli --retry --model gpt-4
```

### Conversations

A conversation consists of a list messages, and some flags. Conversations typically start with
system message, and then alternate between user and assistant messages but you can create
conversations with any sequence of messages you like.

You can create a new conversation and add messages to it with the `add` command:

```
echo "You are a mouse and only squeak." | chatcli add
echo "Hello!" | chatcli add --role user --continue
echo "Squeak!" | chatcli add --role assistant --continue
echo "How are you?" | chatcli add --role user --continue
```

You can use the `answer` command to get GPT to add a message to the conversation:

```
$ chatcli answer
Squeak squeak!
```

You can show the contents of a conversation the `show` command. By default it will show the most
recent message only. Use `--long` to view the full conversation.

```
$ chatcli show --long
You are a mouse and only squeak.
>> Hello!
Squeak!
>> How are you?
Squeak squeak!
```

### The Log

ChatCLI keeps an append only log file with a snapshot of every conversation.
When you create or modify a conversation a new entry is added to the log.

Create a log file in the current directory with:

```
chatcli init
```

Chatcli will search for a log file in the current directory, or in any parent
directory. You can create a single log file in your home directory and store
your full conversation history there, or create per project log files in
project directories.

By default logs are saved in ".chatcli.log". You can override by setting
environment variable `CHATCLI_LOGFILE`.

View the log using the log command.

```
chatcli log --limit 10
```

You can select messages from the log using their `offset`. Most commands accept
an offset. For example, to continue from the third most recent entry in the log
you can use

```
chatcli 3
```

Similiarly, you can search for a keyword using the `--search` option. For example,
view the most recent conversation mentioning python with

```
chatcli show --search python
```


### Personalities

A personality is just a conversation that is intended as the starting point of
future conversations. You can see the default personality with:

```
chatcli show -p default
```

and list all available personalities with:

```
chatcli personalities
```

You can start a conversation from with any personality with:

```
chatcli --personality checker
```

You can create a new personality using the `add` command with the `--personality` or `-p` flag.

```
$ chatcli add --personality checker
(Finish input with <Alt-Enter> or <Esc><Enter>)
>> You are spelling and grammar checker. Respond to every message with a list of
spelling and grammatical errors. (If any.)
..
```

You can also create more complex personalities by calling `add` repeatedly to build up longer
conversation including examples of how the assistant should respond. For example, we can teach
the image personality to generate images like this:

````
chatcli add --plugin image --model gpt-4 <<- END
        You have the ability to create images from prompts using DALL-E.

        To do this provide an image block with the filename to save the
        image to and a prompt.
END

chatcli add -c --role user <<- 'END'
        Generate a nice landscape.
END

chatcli add -c --role assistant <<- 'END'
        IMAGE("landscape.png")
        ```
        A painting of the sun setting over mountains.
        ```
END

chatcli add -c --role user <<- 'END'
        RESULT:
        ```
        Image saved to landscape.png
        ```
END

chatcli add -p image -c --role assistant <<- 'END'
        Your image is in landscape.png!
END
````

### Plugins


A plugin allows the answers from GPT to be fed to another program (eg: python,
a search engine, etc.), and the result fed back to GPT.

For example, we can use the `pyeval` to work out how many days are left in the year:

````
$ chatcli --personality pyeval
(Finish input with <Alt-Enter> or <Esc><Enter>)
>> How many days are left in the year?
..
EVALUATE:
```
from datetime import date, timedelta

today = date.today()
end_of_year = date(today.year, 12, 31)
days_left = (end_of_year - today).days
days_left
```

RESULT:
```
227
```
There are 227 days left in the year.
````

A plugin usually consists of the plugin itself and a personality that prompts
gpt to explain how to interact with the plugin. Plugins usually require `gpt-4`
to work well.

As a user, you won't normally interact with the plugin directly, you can just
specify a personality with a plugin enabled.

Show the prompt for the pyeval plugin with:

```
chatcli show --personality pyeval
```

You could create this personality yourself by this and providing a prompt that
explains the use of the plugin.

```
chatcli add --plugin pyeval --model gpt-4
```


### Tags

Conversations can be tagged so you can name them and refer back to them later. You
can add a tag to a conversation with:

```
chatcli tag mytag
```

You can then continue the conversation with:

```
chatcli --tag mytag --continue
```

Whenever you extend a tagged conversation the most recently added tag is added to the
new conversation snapshot. In this way you can use tags like branches in git. (View the
active tag with `chatcli show-tag`)

Remove a tag the `untag` command:

```
chatcli untag mytag
```

View all tags with the `tags` command:

```
chatcli tags
```

You'll see that personalities are listed with tags. A personality is just a tag that starts with
a `^`. When you add a new message to a personality, the personality tag is not copied forward.

### Display usage

To display the number of tokens used and the token cost, use the `usage` command:

```
chatcli usage
```

Or, just view today's usage with:

```
chatcli usage --today
```

## Examples

### Generate a README for this project

```
chatcli --quick --file chatcli_gpt/cli.py --personality code
>> Generate a README.md for this project.
```

### Using ChatGPT to create commit messages

1. Make some changes to your code and stage them for commit:

```
git add -p
```

2. Use `git diff` to see the changes you've made and pipe them to chatcli
   script to generate a commit message:

```
git diff --cached | chatcli -p commit
```

3. Make a commit with the generated message:

```
git commit --edit -m "$(chatcli show)"
```

This will use the `show` command to display the last message generated by GPT,
which is then used as the commit message.

That's it! You've successfully used ChatGPT to generate a commit message based
on the changes you've made to your code.

## Contributing

If you wish to contribute to this project, please fork the repository and submit a pull request.
