"""Provider-specific model factory behind environment settings."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from rolelens.config import Settings, get_settings


class MissingModelCredentials(RuntimeError):
    pass


def require_model_credentials(settings: Settings) -> None:
    if (
        settings.model_api_key is None
        or not settings.model_api_key.get_secret_value().strip()
    ):
        raise MissingModelCredentials(
            ".env 파일을 생성하고 MODEL_API_KEY 또는 OPENAI_API_KEY를 설정하세요."
        )


def create_chat_model(settings: Settings | None = None) -> ChatOpenAI:
    settings = settings or get_settings()
    require_model_credentials(settings)
    return ChatOpenAI(
        model=settings.model_id,
        api_key=settings.model_api_key.get_secret_value(),
        temperature=0,
        timeout=30,
        max_retries=1,
    )
