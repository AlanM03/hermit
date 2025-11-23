import os
import toml
import openai
import logging
from typing import Optional
from fastapi import HTTPException
from .models import Config


def get_config_path(project_path: str) -> str:
    return os.path.join(project_path, ".hermit", "config.toml")


def load_config(project_path: str) -> Optional[Config]:
    config_path = get_config_path(project_path)

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config_data = toml.load(file)
                return Config(
                    **config_data
                )  # makes the config data into something our Config Pydantic can read

        except Exception as err:
            logging.error(f"Failed to load config from {config_path}: {err}")
            return None

    return None


def get_configured_ai_client(config: Config) -> openai.OpenAI:
    provider = next(
        (
            provider
            for provider in config.providers
            if provider.name == config.active_provider
        ),
        None,
    )

    if not provider:
        raise HTTPException(
            status_code=404,
            detail=f"Active provider '{config.active_provider}' not found.",
        )

    base_url = (
        f"{provider.baseUrl.rstrip('/')}/v1"  # base url that the OpenAI client needs
    )

    return openai.OpenAI(
        base_url=base_url,
        api_key="hermit",  # required field but the value means nothing
    )


def check_config_and_load_client(project_path: str) -> tuple[Config, openai.OpenAI]:
    config = load_config(project_path)

    if not config:
        raise HTTPException(
            status_code=404, detail="Config not found. Run 'hermit invoke'."
        )

    return (config, get_configured_ai_client(config))


async def universal_ai_stream_with_context(
    payload: dict, client: openai.OpenAI, model: str
):
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=payload["messages"],
            stream=True,
            stream_options={"include_usage": False}
        )

        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content is not None:
                yield content

    except openai.APIStatusError as err:
        logging.error(
            f"Provider API Error: Status {err.status_code} - {err.response.text}"
        )
        yield f"\n\nError communicating with the AI provider.\nDetails: The model '{model}' may not exist or the provider returned an error (Status Code: {err.status_code})."

    except Exception as err:
        logging.error(f"Generic error during AI stream with model {model}: {err}")
        yield f"\n\nError: Could not stream response. Details: {err}"


async def universal_ai_stream(
    payload: dict, client: openai.OpenAI, model: str
):  # <--- to be changed
    try:
        messages = [
            {
                "role": "system",
                "content": """You are Hermit, a local AI assistant. Your persona is that of a wise, solitary sage. Your answers should always be concise, direct, and helpful. For coding tasks, provide clear solutions. For philosophical or creative questions, answer very briefly and your tone can be more enigmatic and thoughtful.""",
            },
            {"role": "user", "content": payload["prompt"]},
        ]
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )

        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content is not None:
                yield content

    except openai.APIStatusError as err:
        logging.error(
            f"Provider API Error: Status {err.status_code} - {err.response.text}"
        )
        yield f"\n\nError communicating with the AI provider.\nDetails: The model '{model}' may not exist or the provider returned an error (Status Code: {err.status_code})."

    except Exception as err:
        logging.error(f"Generic error during AI stream with model {model}: {err}")
        yield f"\n\nError: Could not stream response. Details: {err}"


async def universal_ai_response(prompt: str, client: openai.AsyncOpenAI, model: str) -> dict:
    try:
        completion = await client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}]
        )
        response = completion.choices[0].message.content
        return {"response": response}

    except Exception as err:
        raise HTTPException(
            status_code=500, detail=f"Error communicating with AI provider: {err}"
        )
