import typer
import requests
import os
import re
from rich import print as coolPrint
from pathlib import Path
import toml

API_URL = "http://127.0.0.1:8000"


def get_config_path() -> Path:
    """Gets the path to the project's config file."""

    return Path(os.getcwd()) / ".hermit" / "config.toml"


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
    timeout = 120 if stream else 60

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


def parse_error_filepath(log: str) -> str | None:
    """Finds the last file path mentioned in a traceback using multiple patterns."""

    patterns = [r'File "([^"]+)"', r"([a-zA-Z]:\\[^:]+|/[^:]+):\d+"]
    for pattern in patterns:
        matches = re.findall(pattern, log)
        if matches:
            return matches[-1].strip()
    return None
