import ollama
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import logging
from typing import Optional
import os
import toml

app = FastAPI()

class PromptRequest(BaseModel):
    prompt: str
    model: str = "llama3.1"

class DiffRequest(BaseModel):
    diff: str

class ErrorRequest(BaseModel):
    error_log: str
    source_code: Optional[str] = None #source code not needed since theres a chance the operation can fail
    file_extension: Optional[str] = None#filepath also not needed 

class SaveConfigRequest(BaseModel):
    project_path: str
    default_model: str

async def stream_ollama_responses(payload: dict):
    """An async generator that streams responses from the ollama.chat function."""

    stream = ollama.chat(
        model=payload['model'], 
        messages=[{'role': 'user', 'content': payload['prompt']}], 
        stream=True
    )
    for chunk in stream:
        yield chunk['message']['content']

@app.get("/api/config/models")#route to just list our ollama models not for use by user but helper function 
async def get_ollama_models():
    """Fetches the list of locally installed Ollama models."""

    try:
        models = ollama.list()['models']
        model_list = []
        for model in models:
            model_list.append(model["model"])
        return {"models": model_list}
    except Exception as err:#if we dont have it installed this happens
        logging.error(f"Could not connect to Ollama to list models: {err}")
        return {"models": []}

@app.post("/api/config/save")
async def save_project_config(request: SaveConfigRequest):
    """Saves the selected model to a project-specific config file."""

    config_dir = os.path.join(request.project_path, ".hermit")#path for folder
    config_file = os.path.join(config_dir, "config.toml")#path for file 

    try:
        os.makedirs(config_dir, exist_ok=True)#makes our folder
        
        config_data = {
            "model": {
                "default": request.default_model
            }
        }
        
        with open(config_file, "w") as file:#write mode to make out toml file 
            toml.dump(config_data, file)
            
        return {"model": request.default_model}#for now just return the model
    
    except OSError as err:
        logging.error(f"Failed to save config file at {config_file}: {err}")
        
        raise HTTPException(
            status_code=500,
            detail=f"Error: Could not write to configuration file. Check permissions for the path: {config_dir}"
        )


@app.post("/api/ponder")
async def ponder(request: PromptRequest):
    """
    This api route handles the hermit ponder "question" cli tool
    """
    payload = request.model_dump()
    return StreamingResponse(
        stream_ollama_responses(payload), 
        media_type="text/plain"
    )


@app.post("/api/semantic-commit")
async def semantic_commit_from_diff(request: DiffRequest):
    """
    Receives a git diff, crafts a prompt, and returns a semantic commit message.
    """

    #custom prompt as well as console response from our git command
    commit_prompt = f"""
    Based on the following git diff, please generate a concise and conventional semantic commit message.
    The message should start with a type (e.g., feat, fix, chore, docs), followed by a short description.
    Do not feel the need to explain yourself so much and do not give conversation to ask more questions about it.

    Diff:
    ```diff
    {request.diff}
    ```
    """

    response = ollama.chat(
        model="llama3.1", 
        messages=[{'role': 'user', 'content': commit_prompt}],
        stream=False # We want the full message at once for this
    )

    """
    Ollama might give us JSON that looks something like this

    {
    "model": "llama3.1",
    "created_at": "2025-09-20T21:08:10...",
    "message": {
        "role": "assistant",
        "content": "feat: Add user login functionality"
    },
    "done": true,
    "total_duration": 1565018600,
    ...
    }

    """

    commit_message = response['message']['content']#we extract the content and return the following 
    return {"commit_message": commit_message}

#diagnose command to figure out errors in single runtime errors for files and general commands
@app.post("/api/diagnose")
async def diagnose_error_handler(request: ErrorRequest):
    """Receives an error log and uses Ollama to explain it."""

    if request.source_code:
        source_code_block = f"```\n{request.source_code}\n```"
    else:
        source_code_block = "Not provided."
    
   
    analysis_prompt = f"""
    You are an expert debugging assistant, skilled in diagnosing both programming errors from files and general command-line issues.

    **Task:** Analyze the provided error log and provide a helpful, easy-to-understand diagnosis.

    **Analysis Steps:**
    1.  **Identify the Error Type:** First, determine if the error is from a script (a file path and source code will likely be present) or a general shell command error (e.g., 'command not found', a typo like 'gitttt').
    2.  **Analyze Based on Type:**
        * **If it is a script error:** Use the file extension to infer the programming language. Analyze the error log and the source code together to find the root cause.
        * **If it is a shell command error:** Focus on the command itself. Analyze the error message to identify issues like typos, incorrect arguments, or a missing program.
    3.  **Provide a Solution:** In all cases, explain the root cause of the error in simple terms and provide a clear, numbered list of the most likely solutions.

    ---
    **Provided Context:**
    - File Extension: `{request.file_extension or "Not available"}`
    - Source Code: {source_code_block}

    **Error Log to Analyze:**
    ```
    {request.error_log}
    ```
    """

    payload = {"prompt": analysis_prompt, "model": "llama3.1"} 

    return StreamingResponse(
        stream_ollama_responses(payload), 
        media_type="text/plain"
    )
