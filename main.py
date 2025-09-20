import ollama
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()

class PromptRequest(BaseModel):
    prompt: str
    model: str = "llama3.1"

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

@app.post("/api/generate")
async def generate(request: PromptRequest):
    """
    The main API route. It receives a prompt and streams back the response.
    """
    payload = request.model_dump()
    return StreamingResponse(
        stream_ollama_responses(payload), 
        media_type="text/plain"
    )
