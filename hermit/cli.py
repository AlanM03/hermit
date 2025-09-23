import typer
import requests
import subprocess
import os
import re

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
    
def parse_error_filepath(log: str) -> str | None:
    """Finds the last file path mentioned in a Python traceback."""
    matches = re.findall(r'File "([^"]+)"', log)#regex to get filepath
    if matches:
        return matches[-1] # Return the last file path found
    return None


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

    with make_api_request(endpoint="/api/ponder", payload=payload, stream=True) as response:
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

    response = make_api_request(endpoint="/api/semantic-commit", payload=payload, stream=False)# we give this paylaod back to fast api class

    commit_message = response.json().get("commit_message")#take successful response and print it out as desired
    print("\n" + "="*100)
    print("Suggested Commit Message:")
    print("="*100 + "\n")
    print(commit_message)
    print("\n")

@app.command(name="diagnose", help="Runs a command and diagnoses it if it fails.", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})# to not throw errors
def run_and_diagnose(words_after_dashes: typer.Context):# to get commands after the --
    """Runs a command and streams its output in real-time. If the command fails, it sends the full output to the daemon for analysis."""

    command_to_run = words_after_dashes.args 

    if not command_to_run:
        print("Please provide a command to run. Example: `hermit run -- python my_script.py`")
        raise typer.Exit()

    print(f"Running command: {' '.join(command_to_run)}")#for looks
    print("-" * 100)

    # Use Popen to run the command and open a stream
    process = subprocess.Popen(
        command_to_run,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # Combine stdout and stderr into one stream
        text=True,
        encoding='utf-8',
        bufsize=1 
    )

    full_log = []
    # Read and print the output line by line, in real-time
    for line in process.stdout:
        print(line, end="")
        full_log.append(line)

    # Wait for the process to finish and get the return code
    process.wait()
    return_code = process.returncode
    
    print("-" * 100)

    # If the command failed, send the captured log for diagnosis
    if return_code != 0:
        print(f"✗ Command failed with exit code {return_code}. ✗ \n\n Sending to Hermit for diagnosis...")

        print("\n" + "="*12)
        print("  Analysis: ")
        print("="*12 + "\n")
        
        log_content = "".join(full_log)
        source_code = None

        #looks at your log error produced which holds your filepath and analyses code from file as such
        filepath = parse_error_filepath(log_content)
        if filepath and os.path.exists(filepath):
            print(f"Found error in file: {filepath}. Reading for context...")
            with open(filepath, 'r', encoding='utf-8') as f:
                source_code = f.read()
        else:#if not found let the user know
            print(f"File with error not found analyzing general error")
    
        payload = {"error_log": log_content, "source_code": source_code} # Add source_code to payload
       
        with make_api_request(endpoint="/api/diagnose", payload=payload, stream=True) as response:
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                print(chunk, end="", flush=True)
        print("\n")
    
    else:
        print("There were no errors and the code ran sucessfully!")


if __name__ == "__main__":
    app()