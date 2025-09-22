import ollama
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()

class PromptRequest(BaseModel):
    prompt: str
    model: str = "llama3.1"

class DiffRequest(BaseModel):
    diff: str

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
