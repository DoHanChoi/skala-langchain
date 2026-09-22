#!/usr/bin/env python3
"""Launch the real Gradio UI with deterministic acceptance dependencies for capture."""

from rolelens.services.insight_service import build_service
from rolelens.ui.gradio_app import build_app


if __name__ == "__main__":
    app = build_app(build_service(offline_acceptance_mode=True))
    app.queue(default_concurrency_limit=1).launch(
        server_name="127.0.0.1",
        server_port=7861,
        show_error=True,
        quiet=True,
    )
