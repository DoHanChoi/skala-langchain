from __future__ import annotations

import pytest

from rolelens.agents.model import MissingModelCredentials, require_model_credentials
from rolelens.config import Settings
from rolelens.domain.models import AnalysisResponse
from rolelens.ui.gradio_app import format_response


def test_error_response_clears_previous_outputs() -> None:
    outputs = format_response(
        AnalysisResponse(status="error", user_message="DB를 확인하세요.")
    )
    assert "분석을 완료하지 못" in outputs[0]
    assert outputs[1] == ""
    assert outputs[2] is None
    assert outputs[3].empty


@pytest.mark.parametrize("api_key", [None, "", "   "])
def test_app_runtime_requires_env_api_key(api_key: str | None) -> None:
    settings = Settings(_env_file=None, MODEL_API_KEY=api_key, OPENAI_API_KEY=None)

    with pytest.raises(MissingModelCredentials, match=r"\.env"):
        require_model_credentials(settings)
