import typer
from rich.console import Console
import requests
import os
import json
import re
from rich import print as coolPrint
from pathlib import Path
from rich.text import Text
import toml
import random
import datetime
from localgrid import get_context_limit, count_tokens
from contextlib import contextmanager
import time
import asyncio
import httpx
import threading

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


def _make_request(
    endpoint: str, payload: dict = None, method: str = "POST", timeout: int = 120
):
    """Internal function to make HTTP requests"""
    url = f"{API_URL}{endpoint}"

    try:
        if method.upper() == "POST":
            response = requests.post(url, json=payload, timeout=timeout)
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


async def _make_request_async(
    endpoint: str, payload: dict = None, method: str = "POST", timeout: int = 120
):
    """Internal async function to make HTTP requests"""
    url = f"{API_URL}{endpoint}"

    try:
        async with httpx.AsyncClient() as client:
            if method.upper() == "POST":
                response = await client.post(url, json=payload, timeout=timeout)
            else:
                response = await client.get(url, timeout=timeout)

            response.raise_for_status()
            return response

    except httpx.HTTPStatusError as err:
        coolPrint(
            f"[bold red]Error from Hermit Daemon (Status Code: {err.response.status_code}):[/bold red]"
        )
        try:
            detail = err.response.json().get("detail", err.response.text)
        except (json.JSONDecodeError, ValueError, AttributeError):
            detail = err.response.text
        coolPrint(f"[italic #A0A0A0]{detail}[/italic #A0A0A0]")
        raise typer.Exit(code=1)

    except httpx.RequestError as err:
        coolPrint(
            f"[bold red]Error connecting to Hermit Daemon:[/bold red] [#A0A0A0]{err}[/#A0A0A0]"
        )
        coolPrint(
            "[italic #A0A0A0]Is the Hermit daemon running? You can start it with 'hermit-daemon'.[/italic #A0A0A0]"
        )
        raise typer.Exit(code=1)


# For non-streaming requests (sync)
def make_api_request(endpoint: str, payload: dict = None, method: str = "POST"):
    """Make a simple API request (non-streaming)"""
    return _make_request(endpoint, payload, method, timeout=120)


# For non-streaming requests (async)
async def make_api_request_async(
    endpoint: str, payload: dict = None, method: str = "POST"
):
    """Make an async API request (non-streaming)"""
    return await _make_request_async(endpoint, payload, method, timeout=120)


# For streaming requests (sync)
@contextmanager
def make_streaming_request(endpoint: str, payload: dict, method: str = "POST"):
    """Make a streaming API request (use with 'with' statement)"""
    response = _make_request(endpoint, payload, method, timeout=180)
    try:
        yield response
    finally:
        response.close()


def transcribe_stream(payload: dict, header: str) -> str:
    """Handles streaming content from LLM"""

    full_response = ""
    loading_phrase, completion_phrase = get_themed_phrases()

    with console.status(loading_phrase, spinner="moon") as status:
        with make_streaming_request(
            endpoint=f"/hermit/{header}",
            payload=payload,
        ) as response:
            is_first_chunk = True

            for chunk in response.iter_content(chunk_size=1, decode_unicode=True):
                if not chunk:
                    continue

                if is_first_chunk:
                    status.stop()
                    coolPrint(completion_phrase)
                    print()
                    is_first_chunk = False

                styled_chunk = Text(chunk, style="italic #FFFFFF")
                console.print(styled_chunk, end="")
                console.file.flush()
                time.sleep(0.002)
                full_response += chunk

    print()
    return full_response


def parse_error_filepath(log: str) -> str | None:
    """Finds the last file path mentioned in a traceback using multiple patterns."""

    patterns = [r'File "([^"]+)"', r"([a-zA-Z]:\\[^:]+|/[^:]+):\d+"]
    for pattern in patterns:
        matches = re.findall(pattern, log)
        if matches:
            return matches[-1].strip()
    return None


def save_chat(file_path: str, data: dict):
    """Appends a single turn (user or assistant message) to the history file."""
    chat_directory = os.path.dirname(file_path)
    try:
        json_line = json.dumps(data)
        os.makedirs(chat_directory, exist_ok=True)
        with open(file_path, "a", encoding="utf-8") as file:
            file.write(json_line + "\n")

    except OSError as err:
        coolPrint(
            f"[bold red]Failed[/bold red] [#DCDCDC]to save to chat file at: [/#DCDCDC] [#A0A0A0]{file_path}[/#A0A0A0][#DCDCDC]:[/#DCDCDC] [bold red]{err}[/bold red]"
        )
        raise typer.Exit(code=1)


def run_chat_loop(file_path: str, history: list):
    """The main interactive chat loop that handles the conversation."""

    try:
        config = load_config()
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as err:
        coolPrint(f"[bold red]Failed to load config: {err}[/bold red]")
        raise typer.Exit(code=1)

    total_tokens = sum(
        count_tokens(msg["content"], config["active_model"]) for msg in history
    )
    context_limit = get_context_limit(config["active_model"])
    max_context = int(context_limit * 0.80)

    coolPrint(
        f"🧙 Chatting in session: [bold #FFFFFF]{os.path.basename(file_path)}[/bold #FFFFFF]. Type '/bye' to exit."
    )
    coolPrint(f"Model in use: [bold #FFFFFF]{config['active_model']}[/bold #FFFFFF]")

    while True:
        prompt = typer.prompt(">", default="").strip()

        if prompt.lower() == "/bye":
            coolPrint("\n[italic #A0A0A0]Farewell[/italic #A0A0A0]\n")
            break

        if not prompt:
            continue

        user_turn = {"role": "user", "content": prompt}

        user_tokens = count_tokens(prompt, config["active_model"])
        total_tokens += user_tokens

        history.append(user_turn)

        user_turn["timestamp"] = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        save_chat(file_path, user_turn)

        payload = {"messages": history, "project_path": os.getcwd()}

        ai_response = transcribe_stream(payload, "chat")
        ai_turn = {"role": "assistant", "content": ai_response}

        ai_tokens = count_tokens(ai_response, config["active_model"])
        total_tokens += ai_tokens

        history.append(ai_turn)

        ai_turn["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_chat(file_path, ai_turn)

        coolPrint(
            f"Context: [bold #FFFFFF]{total_tokens}/{context_limit}[/bold #FFFFFF] tokens"
        )
        if (total_tokens) >= max_context:

            def run_summarization():
                nonlocal history, total_tokens
                asyncio.run(
                    summarize_text(history.copy(), int(context_limit * 0.60), file_path)
                )
                # After summarization completes, reload history and recalculate tokens
                history.clear()
                history.extend(load_chat_history(file_path))
                total_tokens = sum(
                    count_tokens(msg["content"], config["active_model"])
                    for msg in history
                )

            thread = threading.Thread(target=run_summarization, daemon=True)
            thread.start()


def load_chat_history(file_path: str) -> list:
    """Load chat history from a file."""
    history = []
    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                history.append(json.loads(line))
    return history


async def summarize_text(history: list[dict], max_context: int, file_path: str) -> None:
    """asyncronously runs a summarize operation seamlessly in the background"""
    window_count = 0
    messages_to_summarize = []
    config = load_config()
    system_msg = history[0]["content"]

    for msg in history:
        if msg == history[0]:
            continue
        extra_tokens = count_tokens(msg["content"], config["active_model"])
        if (window_count + extra_tokens) < max_context:
            window_count += extra_tokens
            messages_to_summarize.append(msg)
        else:
            break

    coolPrint(
        f"Summarizing [bold #FFFFFF]{len(messages_to_summarize)}[/bold #FFFFFF] messages..."
    )
    formatted_history = "\n".join(
        [f"{msg['role'].upper()}: {msg['content']}" for msg in messages_to_summarize]
    )

    prompt = f"""You are summarizing a conversation for context retention. 

    PERSONA CONTEXT:
    {system_msg}

    CONVERSATION TO SUMMARIZE:
    {formatted_history}

    Generate a concise summary following these rules:
    1. Capture key facts, questions asked, and decisions made
    2. Preserve user preferences or technical details mentioned
    3. Note any ongoing tasks or unresolved questions
    4. Ignore spam, repeated characters, or meaningless input (like "fffffssssqqq...")
    5. Keep the summary under 150 words
    6. Structure as bullet points for clarity

    Output only the summary, no additional commentary."""

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "project_path": os.getcwd(),
    }

    res = await make_api_request_async(endpoint="/hermit/summarize", payload=payload)
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    system_line = lines[0]
    lines_to_keep = lines[
        1 + len(messages_to_summarize) :
    ]  # Everything after the removed ones

    summary_msg = {
        "role": "system",
        "content": f"Summary: {res.json().get('response', '')}",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    summary_line = json.dumps(summary_msg) + "\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(system_line)
        f.write(summary_line)
        f.writelines(lines_to_keep)
