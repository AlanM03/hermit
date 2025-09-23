import typer
import requests
import subprocess
import os
import re
from rich import print as coolPrint

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
        coolPrint("[bold red]✗[/bold red] [#DCDCDC]Error[/#DCDCDC] [bold red]✗[/bold red][#DCDCDC]:[/#DCDCDC] [#A0A0A0]Could not connect to the Hermit daemon. Please make sure it's running.[/#A0A0A0]")
        raise typer.Exit(code=1)
    except requests.exceptions.Timeout:
        coolPrint(f"[bold red]✗[/bold red] [#DCDCDC]Error[/#DCDCDC] [/bold red]✗[bold red][#DCDCDC]:[/#DCDCDC] [#A0A0A0]The connection to the Hermit daemon timed out.[/#A0A0A0]")
        raise typer.Exit(code=1)
    except requests.exceptions.HTTPError as err:
        coolPrint(f"[bold red]✗[/bold red] [#DCDCDC]Error[/#DCDCDC] [bold red]✗[/bold red][#DCDCDC]:[/#DCDCDC] [#A0A0A0]The Hermit daemon returned an error (Status Code:[/#A0A0A0] [bold red]{err.response.status_code}[/bold red][#A0A0A0]).[/#A0A0A0]")
        coolPrint(f"[#A0A0A0]Response:[/#A0A0A0] [bold red]{err.response.text}[/bold red]")
        raise typer.Exit(code=1)
    except requests.exceptions.RequestException as err:
        coolPrint(f"[bold red]✗[/bold red] [#DCDCDC]Error[/#DCDCDC] [bold red]✗[/bold red][#DCDCDC]:[/#DCDCDC] [#A0A0A0]An unexpected network error occurred:[/#A0A0A0] [bold red]{err}[/bold red]")
        raise typer.Exit(code=1)
    
def parse_error_filepath(log: str) -> str | None:#only works with python for now
    """Finds the last file path mentioned in a Python traceback."""
    matches = re.findall(r'File "([^"]+)"', log)#regex to get filepath
    if matches:
        return matches[-1] # Return the last file path found
    return None


#since chromadb is not up yet this is a placeholder
@app.command(name="init", help="Initialize Hermit for a new project.")
def initialize_project():
    """Sets up project."""
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

    coolPrint(f"[#A0A0A0]Starting thought...[/#A0A0A0]\n")
    payload = {"prompt": prompt}

    with make_api_request(endpoint="/api/ponder", payload=payload, stream=True) as response:
        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            coolPrint(f"[italic #FFFFFF]{chunk}[/italic #FFFFFF]", end="", flush=True)
    print("\n")

@app.command(name="scribe", help="Generate a semantic commit message from staged changes.")
def semantic_commit():
    """Gets staged git changes and asks the local AI daemon to generate a commit message."""

    coolPrint(f"[#A0A0A0]Getting staged changes...[/#A0A0A0]\n")
    try:
        
        git_diff_command = ["git", "diff", "--staged"]#runs command git diff --staged
        diff_process = subprocess.run(git_diff_command, capture_output=True, text=True, check=True, encoding='utf-8')#cli commands run a 0 on success so we check to see if that happened with 'check=True'
        staged_diff = diff_process.stdout
        payload = {"diff": staged_diff}

        if not staged_diff:#if no staged changes are found quit cli
            coolPrint(f"[bold red]No staged changes found.[/bold red] [#DCDCDC]Please[/#DCDCDC] [#A0A0A0]`git add`[/#A0A0A0] [#DCDCDC]files to commit.[/#DCDCDC]\n")
            raise typer.Exit()
        
    except subprocess.CalledProcessError as err: #if the subprocess returns a code other than 0 because of the check above we can give this specific error
        coolPrint(f"[bold red]✗[/bold red] [#DCDCDC]Error[/#DCDCDC] [bold red]✗[/bold red][#DCDCDC]: The[/#DCDCDC] [#A0A0A0]'git diff --staged'[/#A0A0A0] [#DCDCDC]command failed.[/#DCDCDC]")
        coolPrint(f"[#DCDCDC]Git returned a non-zero exit code:[/#DCDCDC] [bold red]{err.returncode}[/bold red]")#gives code back
        coolPrint(f"\n[#A0A0A0]--- Error from Git ---[/#A0A0A0]")
        coolPrint(f"[bold red]{err.stderr}[/bold red]\n")#gives desc of actual error
        raise typer.Exit(code=1)

    coolPrint(f"[#DCDCDC]Hermit Generating...[/#DCDCDC]")

    response = make_api_request(endpoint="/api/semantic-commit", payload=payload, stream=False)# we give this paylaod back to fast api class

    commit_message = response.json().get("commit_message")#take successful response and print it out as desired
    coolPrint("\n" + "[#DCDCDC]=[/#DCDCDC]"*100)
    coolPrint(f"[#A0A0A0]Suggested Commit Message:[/#A0A0A0]")
    coolPrint(f"[#DCDCDC]=[/#DCDCDC]"*100 + "\n")
    coolPrint(f"[#FFFFFF]{commit_message}[/#FFFFFF]")
    print("\n")

@app.command(name="diagnose", help="Runs a command and diagnoses it if it fails.", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})# to not throw errors
def run_and_diagnose(words_after_dashes: typer.Context):# to get commands after the --
    """Runs a command and streams its output in real-time. If the command fails, it sends the full output to the daemon for analysis."""

    command_to_run = words_after_dashes.args 

    if not command_to_run:
        coolPrint(f"[bold red]Please provide a command to run.[/bold red] [#A0A0A0]Example: `hermit run -- python my_script.py`[/#A0A0A0]")
        raise typer.Exit()

    try:
        coolPrint(f"[#DCDCDC]Running command:[/#DCDCDC] [#A0A0A0]{' '.join(command_to_run)}[/#A0A0A0]\n")#for looks
        
        
        # This is the line that might fail
        process = subprocess.Popen(
            command_to_run,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
        )

    except FileNotFoundError:
        # This block runs ONLY if the command was not found
        coolPrint(f"[bold red]Error: Command not found ->[/bold red] [#DCDCDC]'{command_to_run[0]}'[/#DCDCDC]")
        coolPrint("[#A0A0A0]Please check if the command is correct and installed on your system.[/#A0A0A0]")
        raise typer.Exit(code=1) # Exit with an error code

    full_log = []
    # Read and print the output line by line, in real-time
    for line in process.stdout:
        coolPrint(f"[bold red]{line}[/bold red]", end="")
        full_log.append(line)

    # Wait for the process to finish and get the return code
    process.wait()
    return_code = process.returncode
    

    # If the command failed, send the captured log for diagnosis
    if return_code != 0:
        coolPrint(f"\n[bold red]✗[/bold red] [#DCDCDC]Command failed with exit code[/#DCDCDC] [bold red]{return_code}[/bold red][#DCDCDC].[/#DCDCDC] [bold red]✗[/bold red] \n\n [bold italic #A0A0A0]Sending to Hermit for diagnosis...[/bold italic #A0A0A0]")

        coolPrint(f"\n" + "[#DCDCDC]=[/#DCDCDC]"*13)
        coolPrint(f"  [#A0A0A0]Analysis:[/#A0A0A0]  ")
        coolPrint(f"[#DCDCDC]=[/#DCDCDC]"*13 + "\n")
        
        log_content = "".join(full_log)
        source_code = None

        #looks at your log error produced which holds your filepath and analyses code from file as such
        filepath = parse_error_filepath(log_content)
        if filepath and os.path.exists(filepath):
            coolPrint(f"[#DCDCDC]Found error in file:[/#DCDCDC] [bold #A0A0A0]{filepath}[/bold #A0A0A0] [#DCDCDC]Reading for context...[/#DCDCDC]\n")
            with open(filepath, 'r', encoding='utf-8') as f:
                source_code = f.read()
        else:#if not found let the user know
            coolPrint(f"[#DCDCDC]File with error not found:[/#DCDCDC] [#A0A0A0]analyzing general error[/#A0A0A0]\n")
    
        payload = {"error_log": log_content, "source_code": source_code}
       
        with make_api_request(endpoint="/api/diagnose", payload=payload, stream=True) as response:
            for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                coolPrint(f"[italic #FFFFFF]{chunk}[/italic #FFFFFF]", end="", flush=True)
        print("\n")
    
    else:
        coolPrint("[#FFFFFF]There were no errors and the code ran sucessfully![/#FFFFFF]\n")


if __name__ == "__main__":
    app()