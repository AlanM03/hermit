import typer
import json
import subprocess
import os
from rich import print as coolPrint
import questionary
from questionary import Style
from rich.console import Console
import toml
from typing import Optional
import datetime
from pathlib import Path

from .cli_utils import (
    get_config_path,
    make_api_request,
    parse_error_filepath,
    transcribe_stream,
    get_themed_phrases,
    get_chats_path,
    slugify,
    save_chat,
    run_chat_loop,
)

app = typer.Typer(
    no_args_is_help=True, help="A local-first AI assistant. For devs, by devs."
)
chat_app = typer.Typer(help="Manage and interact with persistent chat sessions.")
app.add_typer(chat_app, name="chat")
console = Console()


@app.command(name="invoke", help="Initialize or re-configure Hermit for a project.")
def invoke():
    """A multi-step wizard to configure the AI provider and model."""

    config_path = get_config_path()

    # might change later just hardcoding the providers basically
    config = {
        "active_provider": "",
        "active_model": "",
        "providers": [
            {"name": "ollama", "baseUrl": "http://localhost:11434/"},
            {"name": "lm-studio", "baseUrl": "http://localhost:1234/"},
            {"name": "koboldcpp", "baseUrl": "http://localhost:5001/"},
            {"name": "jan", "baseUrl": "http://localhost:1337/"},
            {"name": "gpt4all", "baseUrl": "http://localhost:4891/"},
        ],
    }

    if config_path.exists():
        existing_config = toml.load(config_path)
        config.update(existing_config)

    providers = config.get("providers", [])
    provider_names = [provider["name"] for provider in providers]

    hermit_style = Style(
        [
            ("question", "fg:#A0A0A0"),
            ("pointer", "fg:#FFFFFF bold"),
            ("highlighted", "fg:#FFFFFF bold"),
            ("selected", "fg:#DCDCDC"),
            ("answer", "fg:#FFFFFF bold"),
            ("instruction", "fg:#A0A0A0"),
        ]
    )

    selected_provider_name = questionary.select(
        "Which local AI provider would you like to use?",
        choices=provider_names,
        use_indicator=False,
        pointer="->",
        qmark="",
        style=hermit_style,
    ).ask()

    if not selected_provider_name:
        raise typer.Exit()

    # can change this later
    selected_provider = next(
        provider for provider in providers if provider["name"] == selected_provider_name
    )

    coolPrint(f"\n[#A0A0A0]Fetching models from {selected_provider_name}...[/#A0A0A0]")
    response = make_api_request("/hermit/provider/models", payload=selected_provider)
    models = response.json().get("models", [])

    if not models:
        coolPrint(
            f"[bold red]Error:[/bold red] [#DCDCDC]No models found for[/#DCDCDC] [#A0A0A0]{selected_provider_name}[/#A0A0A0][#DCDCDC]. Is the server running?[/#DCDCDC]"
        )
        raise typer.Exit(code=1)

    selected_model = questionary.select(
        f"Select a default model from {selected_provider_name}:",
        choices=models,
        use_indicator=False,
        pointer="->",
        qmark="",
        style=hermit_style,
    ).ask()

    if not selected_model:
        raise typer.Exit()

    config["active_provider"] = selected_provider_name
    config["active_model"] = selected_model

    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as file:
            toml.dump(config, file)

        coolPrint(
            f"\n[#DCDCDC]Success![/#DCDCDC] [#A0A0A0]Hermit is now configured to use[/#A0A0A0] [bold #FFFFFF]{selected_model}[/bold #FFFFFF] [#A0A0A0]via[/#A0A0A0] [bold #FFFFFF]{selected_provider_name}[/bold #FFFFFF][#A0A0A0].[/#A0A0A0]"
        )

    except OSError as err:
        coolPrint(
            f"[bold red]Error[/bold red] [#DCDCDC]saving configuration file:[/#DCDCDC] [bold red]{err}[/bold red]"
        )
        raise typer.Exit(code=1)


@app.command(name="ponder")
def ponder(prompt: str):
    """Hermit ponders on your question and gives its best answer."""

    payload = {"prompt": prompt, "project_path": os.getcwd()}
    transcribe_stream(payload, "ponder")
    print("\n")


@chat_app.command(name="new")
def chat_new(
    session_name: Optional[str] = typer.Argument(
        None, help="Optional: A name for your new chat session."
    ),
):
    """Hermit makes a new convo with you"""

    final_session_name = ""
    if session_name:
        final_session_name = session_name
    else:
        now = datetime.datetime.now()
        final_session_name = now.strftime("%b-%d-at-%I-%M%p")

    chat_directory = get_chats_path()
    chat_name = slugify(final_session_name)
    file_path = os.path.join(chat_directory, chat_name)

    data = {
        "role": "system",
        "content": """You are Hermit, a local AI assistant. Your persona is that of a wise, solitary sage. Your answers should always be concise, direct, and helpful. For coding tasks, provide clear solutions. For philosophical or creative questions, answer very briefly and your tone can be more enigmatic and thoughtful.""",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    save_chat(file_path, data)
    run_chat_loop(file_path, [data])


@chat_app.command(name="recall")
def chat_recall():
    """Hermit lists all conversations and asks you to pick one and you go into an interactive convo"""

    chat_directory = get_chats_path()
    chat_names = os.listdir(chat_directory)

    hermit_style = Style(
        [
            ("question", "fg:#A0A0A0"),
            ("answer", "fg:#FFFFFF bold"),
            ("instruction", "fg:#A0A0A0"),
            ("text", "fg:#FFFFFF"),
            ("completion-menu.completion", "bg:#2C2C2C fg:#A0A0A0"),
            ("completion-menu.completion.current", "bg:#FFFFFF fg:#1C1C1C"),
            ("completion-menu.scrollbar.arrow", "fg:#FFFFFF"),
        ]
    )

    selected_session = questionary.autocomplete(
        "Which chat session would you like to recall? (Start typing to filter)",
        choices=chat_names,
        validate_while_typing=False,
        style=hermit_style,
    ).ask()

    target_file = os.path.join(chat_directory, selected_session)
    history = []

    if Path(target_file).exists():
        with open(target_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    history.append(json.loads(line))
                except json.JSONDecodeError:
                    coolPrint(
                        f"[bold yellow]Warning: Skipping malformed line in {selected_session}.jsonl[/bold yellow]"
                    )
    run_chat_loop(target_file, history)


@app.command(name="scribe")
def scribe():
    """Generates a semantic commit message from staged changes."""

    try:
        git_diff_command = ["git", "diff", "--staged"]
        diff_process = subprocess.run(
            git_diff_command,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        staged_diff = diff_process.stdout
        if not staged_diff:
            coolPrint("[bold red]No staged changes found.[/bold red]")
            raise typer.Exit()

    except subprocess.CalledProcessError as err:
        coolPrint(f"[bold red]Error running git diff:[/bold red]\n{err.stderr}")
        raise typer.Exit(code=1)

    payload = {"diff": staged_diff, "project_path": os.getcwd()}

    loading_phrase, completion_phrase = get_themed_phrases()

    # for spinner, can totally make this more consise in a helper later idk how many we will do like this
    with console.status(loading_phrase, spinner="moon"):
        response = make_api_request(endpoint="/hermit/scribe", payload=payload)

    coolPrint(completion_phrase)
    commit_message = response.json().get("response")

    coolPrint("\n" + "=" * 50)
    coolPrint("[#A0A0A0]Suggested Commit Message:[/#A0A0A0]")
    coolPrint("=" * 50 + "\n")
    coolPrint(f"[#FFFFFF]{commit_message}[/#FFFFFF]")
    print("\n")


@app.command(
    name="diagnose",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def run_and_diagnose(ctx: typer.Context):
    """Runs a command and diagnoses it if it fails."""

    command_to_run = ctx.args

    if not command_to_run:
        coolPrint("[bold red]Please provide a command to run.[/bold red]")
        raise typer.Exit()

    coolPrint(
        f"[#DCDCDC]Running command:[/#DCDCDC] [#A0A0A0]{' '.join(command_to_run)}[/#A0A0A0]\n"
    )
    coolPrint("[#A0A0A0]»»»[/#A0A0A0]" * 50 + "\n\n")

    try:
        process = subprocess.Popen(
            command_to_run,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

    except FileNotFoundError:
        coolPrint(
            f"[bold red]Error: Command not found -> '{command_to_run[0]}'.[/bold red]"
        )
        raise typer.Exit(code=1)

    full_log = []
    for line in process.stdout:
        coolPrint(f"[bold red]{line}[/bold red]", end="")
        full_log.append(line)

    process.wait()
    return_code = process.returncode

    print("\n")
    coolPrint("[#A0A0A0]»»»[/#A0A0A0]" * 50)

    if return_code != 0:
        coolPrint(
            f"\n[#DCDCDC]Command failed with exit code[/#DCDCDC] [bold red]{return_code}[/bold red][#DCDCDC].[/#DCDCDC] \n[#A0A0A0]Sending to Hermit for diagnosis...[/#A0A0A0]"
        )
        log_content = "".join(full_log)
        source_code, file_extension = None, None

        filepath = parse_error_filepath(log_content)

        if filepath and os.path.exists(filepath):
            coolPrint(
                f"[#DCDCDC]Found error in file: {filepath}. Reading for context...[/#DCDCDC]"
            )
            file_extension = os.path.splitext(filepath)[1]
            with open(filepath, "r", encoding="utf-8") as f:
                source_code = f.read()

        payload = {
            "error_log": log_content,
            "source_code": source_code,
            "language": file_extension or "shell",
            "project_path": os.getcwd(),
        }

        transcribe_stream(payload, "diagnose")
        print("\n")
    else:
        coolPrint("Command finished successfully.")


if __name__ == "__main__":
    app()
