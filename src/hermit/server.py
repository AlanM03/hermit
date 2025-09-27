import toml
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import logging
import os
import httpx

from .server_utils import (
    check_config_and_load_client,
    universal_ai_stream,
    get_config_path,
)

from .models import (
    PromptRequest,
    SaveConfigRequest,
    ProviderModelRequest,
    ScribeRequest,
    ErrorRequest,
)

logging.basicConfig(level=logging.INFO)


app = FastAPI()


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


@app.post("/hermit/config/save")
async def save_project_config(request: SaveConfigRequest):
    config_file = get_config_path(request.project_path)
    config_dir = os.path.dirname(config_file)

    try:
        os.makedirs(config_dir, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as file:
            toml.dump(request.config, file)
        return {"message": "Configuration saved successfully."}

    except OSError as err:
        logging.error(f"Failed to save config file at {config_file}: {err}")
        raise HTTPException(status_code=500, detail="Error writing config file.")


@app.post("/hermit/ponder")
async def ponder(request: PromptRequest):
    config, client = check_config_and_load_client(request.project_path)
    payload = request.model_dump()

    return StreamingResponse(
        universal_ai_stream(payload, client, config.active_model),
        media_type="text/plain",
    )


@app.post("/hermit/scribe")
async def scribe(request: ScribeRequest):
    config, client = check_config_and_load_client(request.project_path)
    commit_prompt = f"Based on the following git diff, generate a conventional commit message. Only output the commit message itself, with no conversational text.\n\nDiff:\n```diff\n{request.diff}\n```"

    # non streaming call
    try:
        response = client.chat.completions.create(
            model=config.active_model,
            messages=[{"role": "user", "content": commit_prompt}],
        )
        commit_message = response.choices[0].message.content
        return {"commit_message": commit_message}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error communicating with AI provider: {e}"
        )


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
