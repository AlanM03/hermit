from pydantic import BaseModel, Field
from typing import Optional, List


class BaseProjectRequest(BaseModel):
    project_path: str = Field(
        ..., description="The absolute path of the user's project directory"
    )


class PromptRequest(BaseProjectRequest):
    prompt: str


class ScribeRequest(BaseProjectRequest):
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


class SaveConfigRequest(BaseModel):
    project_path: str
    config: dict


class ProviderModelRequest(BaseModel):
    baseUrl: str
    name: str
