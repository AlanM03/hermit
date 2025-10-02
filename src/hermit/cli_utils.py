import typer
from rich.console import Console
import requests
import os
import re
from rich import print as coolPrint
from pathlib import Path
from rich.text import Text
import toml
import random

API_URL = "http://127.0.0.1:8000"
console = Console()


def get_themed_phrases() -> tuple[str, str]:
    """Selects a random, corresponding pair of loading and completion phrases."""

    phrase_pairs = [
        ("Pondering in solitude...", "A thought has emerged."),
        (
            "Consulting the ancient scrolls...",
            "The scrolls have revealed their secrets.",
        ),
        ("Brewing a thought...", "The brew is complete."),
        ("Stoking the embers of an idea...", "The embers glow with an answer."),
        ("Listening to the silence...", "Silence has spoken."),
        ("Carving a response...", "The carving is done."),
        ("Gazing into the abyss...", "The abyss has answered."),
        ("Translating runic code...", "The runes are clear."),
        ("Following a thread of logic...", "The thread has led to an answer."),
        ("Distilling a complex idea...", "The essence has been captured."),
    ]
    loading, completion = random.choice(phrase_pairs)

    formatted_loading = f"[#A0A0A0]{loading}[/#A0A0A0]"
    formatted_completion = f"🌕 [#A0A0A0]{completion}[/#A0A0A0]"

    return formatted_loading, formatted_completion


def get_config_path() -> Path:
    """Gets the path to the project's config file."""

    return Path(os.getcwd()) / ".hermit" / "config.toml"


def get_chats_path() -> Path:
    return Path(os.getcwd()) / ".hermit" / "chats"


def slugify(text: str) -> str:
    """Converts a string into a URL-friendly slug."""
    text = text.strip().lower()

    # Replace spaces and repeated hyphens with a single hyphen
    text = re.sub(r"[\s-]+", "-", text)

    # Remove characters that are not alphanumeric or a hyphen
    text = re.sub(r"[^a-z0-9-]", "", text)

    return text + ".json"


def load_config() -> dict:
    """Loads the project config if it exists, otherwise returns a default."""

    config_path = get_config_path()
    if config_path.exists():
        return toml.load(config_path)
    return {}


def make_api_request(
    endpoint: str, payload: dict, stream: bool = False, method: str = "POST"
):  # handles post and get for now
    """Handles making API requests to the daemon."""

    url = f"{API_URL}{endpoint}"
    timeout = 180 if stream else 120

    try:
        if method.upper() == "POST":
            response = requests.post(url, json=payload, stream=stream, timeout=timeout)
        else:
            response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response

    except requests.exceptions.HTTPError as err:
        coolPrint(
            f"[bold red]Error from Hermit Daemon (Status Code: {err.response.status_code}):[/bold red]"
        )

        try:
            detail = err.response.json().get("detail", err.response.text)

        except requests.exceptions.JSONDecodeError:
            detail = err.response.text

        coolPrint(f"[italic #A0A0A0]{detail}[/italic #A0A0A0]")
        raise typer.Exit(code=1)

    except requests.exceptions.RequestException as err:
        coolPrint(
            f"[bold red]Error connecting to Hermit Daemon:[/bold red] [#A0A0A0]{err}[/#A0A0A0]"
        )
        coolPrint(
            "[italic #A0A0A0]Is the Hermit daemon running? You can start it with 'hermit-daemon'.[/italic #A0A0A0]"
        )
        raise typer.Exit(code=1)


def transcribe_stream(payload: dict, header: str) -> None:
    """Handles streaming content from LLM aswell as implements loading icons and phrases"""

    loading_phrase, completion_phrase = get_themed_phrases()
    with console.status(loading_phrase, spinner="moon") as status:
        with make_api_request(
            endpoint=f"/hermit/{header}", payload=payload, stream=True
        ) as response:
            is_first_chunk = True
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                if is_first_chunk:
                    status.stop()
                    coolPrint(completion_phrase)
                    print()
                    is_first_chunk = False
                coolPrint(Text(chunk, style="italic #FFFFFF"), end="", flush=True)
    print()


def parse_error_filepath(log: str) -> str | None:
    """Finds the last file path mentioned in a traceback using multiple patterns."""

    patterns = [r'File "([^"]+)"', r"([a-zA-Z]:\\[^:]+|/[^:]+):\d+"]
    for pattern in patterns:
        matches = re.findall(pattern, log)
        if matches:
            return matches[-1].strip()
    return None
