from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import logging
import httpx
from contextlib import asynccontextmanager
from localgrid import preload_tokenizers

from .server_utils import (
    check_config_and_load_client,
    universal_ai_stream,
    universal_ai_response,
    universal_ai_stream_with_context,
)

from .models import (
    PromptRequest,
    ProviderModelRequest,
    ScribeRequest,
    ErrorRequest,
    ChatRequest,
)

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Preloading tokenizers...")
    await preload_tokenizers()  
    yield

app = FastAPI(lifespan=lifespan)


@app.post("/hermit/provider/models")
async def get_models_for_provider(request: ProviderModelRequest):
    # standard open ai route to list models
    api_url = f"{request.baseUrl.rstrip('/')}/v1/models"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, timeout=10)
            response.raise_for_status()

            response_data = response.json()
            # different open ai compatible apis might return these models in either data as the key or as models
            models_list = response_data.get("data", response_data.get("models", []))
            # here we check for keys id and for fallback name
            model_names = [model.get("id", model.get("name")) for model in models_list]
            return {"models": model_names}

    except httpx.RequestError as err:
        logging.error(f"Could not connect to provider at {request.baseUrl}: {err}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to provider at {request.baseUrl}. Is the server running?",
        )

    except Exception as err:
        logging.error(f"Error parsing models from {request.baseUrl}: {err}")
        raise HTTPException(
            status_code=500,
            detail="Received an unexpected or invalid response from the provider.",
        )


@app.post("/hermit/ponder")
async def ponder(request: PromptRequest):
    config, client = check_config_and_load_client(request.project_path)
    payload = request.model_dump()

    return StreamingResponse(
        universal_ai_stream(payload, client, config.active_model),
        media_type="text/plain",
    )


@app.post("/hermit/chat")
async def chat(request: ChatRequest):
    config, client = check_config_and_load_client(request.project_path)
    payload = request.model_dump()

    return StreamingResponse(
        universal_ai_stream_with_context(payload, client, config.active_model),
        media_type="text/plain",
    )

@app.post("/hermit/summarize")
async def summarize(request: ChatRequest):
    config, client = check_config_and_load_client(request.project_path)
    prompt = f"Please summarize the following conversation accurately and concisely."

    return universal_ai_response(prompt,client, config.active_model)

@app.post("/hermit/scribe")
async def scribe(request: ScribeRequest):
    config, client = check_config_and_load_client(request.project_path)
    commit_prompt = f"Based on the following git diff, generate a conventional commit message. Only output the commit message itself, with no conversational text.\n\nDiff:\n```diff\n{request.diff}\n```"
    return universal_ai_response(commit_prompt, client, config.active_model)


@app.post("/hermit/diagnose")
async def diagnose(request: ErrorRequest):
    config, client = check_config_and_load_client(request.project_path)
    source_code_block = (
        f"```\n{request.source_code}\n```" if request.source_code else "Not provided."
    )

    analysis_prompt = f"""
    You are an expert debugging assistant. Your task is to analyze an error log and provide a helpful diagnosis.
    1. Explain the root cause of the error in simple terms.
    2. Provide a clear, numbered list of the most likely solutions.
    - File Extension: `{request.language or "Not available"}`
    - Source Code: {source_code_block}
    - Error Log to Analyze:
    ```
    {request.error_log}
    ```
    """

    payload = {"prompt": analysis_prompt}
    return StreamingResponse(
        universal_ai_stream(payload, client, config.active_model),
        media_type="text/plain",
    )

def run():
    """Entry point for hermit-daemon command."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)