import ollama
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import logging
from typing import Optional

app = FastAPI()

class PromptRequest(BaseModel):
    prompt: str
    model: str = "llama3.1"

class DiffRequest(BaseModel):
    diff: str

class ErrorRequest(BaseModel):
    error_log: str
    source_code: Optional[str] = None #source code not needed since theres a chance the operation can fail

async def stream_ollama_responses(payload: dict):
    """
    An async generator that streams responses from the ollama.chat function.
    """
    stream = ollama.chat(
        model=payload['model'], 
        messages=[{'role': 'user', 'content': payload['prompt']}], 
        stream=True
    )
    for chunk in stream:
        yield chunk['message']['content']


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


@app.post("/api/diagnose")
async def diagnose_error_handler(request: ErrorRequest):
    """Receives an error log and uses Ollama to explain it.
    """
    code_context = ""
    if request.source_code:
        code_context = f"""
        Here is the full source code of the file where the error occurred:
        ```python
        {request.source_code}
        ```
        """
    else:
        "In this case the file path can not be found so acknowledge that and give general advice to solve error"

    analysis_prompt = f"""
    You are an expert developer and debugging assistant.
    Analyze the following terminal output and error traceback.
    {code_context} 
    Based on the error log and the provided source code, explain the root cause of the error in simple terms.
    Then, provide a list of the most likely solutions to fix it.

    Error Log:
    ```
    {request.error_log}
    ```
    """

    payload = {"prompt": analysis_prompt, "model": "llama3.1"} 

    return StreamingResponse(
        stream_ollama_responses(payload), 
        media_type="text/plain"
    )
