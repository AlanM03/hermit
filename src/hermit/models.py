from pydantic import BaseModel, Field
from typing import Optional, List


class BaseProjectRequest(BaseModel):
    project_path: str = Field(
        ..., description="The absolute path of the user's project directory"
    )


class PromptRequest(BaseProjectRequest):  # to be changed or removed
    prompt: str


class ChatRequest(BaseProjectRequest):  # for persistant memory
    messages: List[dict]


class ScribeRequest(BaseProjectRequest):  # to be changed or removed
    diff: str


class ErrorRequest(BaseProjectRequest):
    error_log: str
    source_code: Optional[str] = None
    language: Optional[str] = "text"


class Provider(BaseModel):
    name: str
    baseUrl: str


class Config(BaseModel):
    active_provider: str
    active_model: str
    providers: List[Provider]


class ProviderModelRequest(BaseModel):
    baseUrl: str
    name: str
