import typer
import requests
import subprocess
import os

app = typer.Typer(no_args_is_help=True)

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
        print(f"Error: Could not connect to the Hermit daemon. Is it running?")
        raise typer.Exit(code=1)


@app.command(name="ponder")
def ponder(prompt: str):
    """
    Hermit ponders on your question and gives its best answer
    """
    print("Starting thought...\n")
    try:
        api_url = "http://127.0.0.1:8000/api/ponder"

        #how request is streamed back to user
        with requests.post(api_url, json={"prompt": prompt}, stream=True, timeout=30) as response:
            response.raise_for_status()
            
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                print(chunk, end="", flush=True)
        
        print("\n")

    except requests.exceptions.RequestException as err: #if general error
        print("❌ An unexpected error occurred.")
        print(err)
        raise typer.Exit(code=1)

@app.command(name="scribe", help="Generate a semantic commit message from staged changes.")
def semantic_commit():
    """
    Gets staged git changes and asks the local AI daemon to generate a commit message.
    """
    print("Getting staged changes...")
    try:
        
        git_diff_command = ["git", "diff", "--staged"]#runs command git diff --staged
        diff_process = subprocess.run(git_diff_command, capture_output=True, text=True, check=True, encoding='utf-8')#cli commands run a 0 on success so we check to see if that happened with 'check=True'
        staged_diff = diff_process.stdout

        if not staged_diff:#if no staged changes are found quit cli
            print("No staged changes found. Please `git add` files to commit.")
            raise typer.Exit()
        
    except subprocess.CalledProcessError as err: #if the subprocess returns a code other than 0 because of the check above we can give this specific error
        print("❌ Error: The 'git diff --staged' command failed.")
        print(f"Git returned a non-zero exit code: {err.returncode}")#gives code back
        print("\n--- Error from Git ---")
        print(err.stderr)#gives desc of actual error
        print("----------------------")
        raise typer.Exit(code=1)

    print("Hermit Generating...")

    #if first try works we can attempt the api call
    try:
        api_url = "http://127.0.0.1:8000/api/semantic-commit"
        response = requests.post(api_url, json={"diff": staged_diff}, timeout=60)
        response.raise_for_status()

    except requests.exceptions.ConnectionError:#if server isnt running at all
        print("❌ Error: Could not connect to the Hermit daemon. Please make sure it's running.")
        raise typer.Exit(code=1)

    except requests.exceptions.Timeout:# if we pass timeout
        print("❌ Error: The connection to the Hermit daemon timed out.")
        raise typer.Exit(code=1)
    
    except requests.exceptions.HTTPError as err:# if serverside error
        print("❌ Error: The Hermit daemon returned an error.")
        print(f"Status Code: {err.response.status_code}")
        print(f"Response: {err.response.text}")
        raise typer.Exit(code=1)

    except requests.exceptions.RequestException as err: #if general error
        print("❌ An unexpected error occurred.")
        print(err)
        raise typer.Exit(code=1)

    commit_message = response.json().get("commit_message")#take successful response and print it out as desired
    print("\n" + "="*100)
    print("Suggested Commit Message:")
    print("="*100 + "\n")
    print(commit_message)
    print("\n")


if __name__ == "__main__":
    app()