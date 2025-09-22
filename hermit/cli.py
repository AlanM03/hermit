import typer
import requests
import subprocess
import os

API_URL = "http://127.0.0.1:8000"

app = typer.Typer(no_args_is_help=True)

#this function acts as a helper function that makes our api requests with error handling
def make_api_request(endpoint: str, payload: dict, stream: bool = False):
    """Handles the bloat of repeated post requests to ollama in a unified function"""

    url = f"{API_URL}{endpoint}"
    timeout = 60 if stream else 30

    try: 
        response = requests.post(url, json=payload, stream=stream, timeout=timeout)
        response.raise_for_status()
        return response
    
    except requests.exceptions.ConnectionError:
        print("✗ Error ✗: Could not connect to the Hermit daemon. Please make sure it's running.")
        raise typer.Exit(code=1)
    except requests.exceptions.Timeout:
        print("✗ Error ✗: The connection to the Hermit daemon timed out.")
        raise typer.Exit(code=1)
    except requests.exceptions.HTTPError as err:
        print(f"✗ Error ✗: The Hermit daemon returned an error (Status Code: {err.response.status_code}).")
        print(f"Response: {err.response.text}")
        raise typer.Exit(code=1)
    except requests.exceptions.RequestException as err:
        print(f"✗ Error ✗: An unexpected network error occurred: {err}")
        raise typer.Exit(code=1)


#since chromadb is not up yet this is a placeholder
@app.command(name="init", help="Initialize Hermit for a new project.")
def initialize_project():
    """
    Sets up project.
    """
    print("Initializing Hermit...")
    project_path = os.getcwd()

    try:
        api_url = "http://127.0.0.1:8000/api/project/initialize"
        response = requests.post(api_url, json={"path": project_path})
        response.raise_for_status()

        report = response.json().get("report", [])
        for message in report:
            print(message)

    except requests.exceptions.RequestException as e:
        print(f"✗ Error ✗: Could not connect to the Hermit daemon. Is it running?")
        raise typer.Exit(code=1)

@app.command(name="ponder")
def ponder(prompt: str):
    """Hermit ponders on your question and gives its best answer."""

    print("Starting thought...\n")
    payload = {"prompt": prompt}

    with make_api_request(endpoint="/api/ponder/", payload=payload, stream=True) as response:
        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            print(chunk, end="", flush=True)
    print("\n")

@app.command(name="scribe", help="Generate a semantic commit message from staged changes.")
def semantic_commit():
    """Gets staged git changes and asks the local AI daemon to generate a commit message."""

    print("Getting staged changes...")
    try:
        
        git_diff_command = ["git", "diff", "--staged"]#runs command git diff --staged
        diff_process = subprocess.run(git_diff_command, capture_output=True, text=True, check=True, encoding='utf-8')#cli commands run a 0 on success so we check to see if that happened with 'check=True'
        staged_diff = diff_process.stdout
        payload = {"diff": staged_diff}

        if not staged_diff:#if no staged changes are found quit cli
            print("No staged changes found. Please `git add` files to commit.")
            raise typer.Exit()
        
    except subprocess.CalledProcessError as err: #if the subprocess returns a code other than 0 because of the check above we can give this specific error
        print("✗ Error ✗: The 'git diff --staged' command failed.")
        print(f"Git returned a non-zero exit code: {err.returncode}")#gives code back
        print("\n--- Error from Git ---")
        print(err.stderr)#gives desc of actual error
        print("----------------------")
        raise typer.Exit(code=1)

    print("Hermit Generating...")

    response = make_api_request(endpoint="/api/semantic-commit/", payload=payload, stream=False)

    commit_message = response.json().get("commit_message")#take successful response and print it out as desired
    print("\n" + "="*100)
    print("Suggested Commit Message:")
    print("="*100 + "\n")
    print(commit_message)
    print("\n")


if __name__ == "__main__":
    app()