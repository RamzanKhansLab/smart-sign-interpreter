from __future__ import annotations

from pathlib import Path

from flask import Flask

from .config import get_config
from .logging_config import setup_logging
from .model_loader import load_model
from .routes import api_bp
from .tts_service import TTSService
from .utils import ensure_dirs, load_env_file


def create_app(config_overrides: dict | None = None) -> Flask:
    load_env_file()
    config = get_config()

    if config_overrides:
        for key, value in config_overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)

    ensure_dirs([Path(config.LOG_FILE).parent, Path(config.MODEL_PATH).parent])
    setup_logging(config)

    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parents[1] / "templates"),
    )

    app.config["CONFIG"] = config

    model = None
    try:
        model = load_model(config.MODEL_PATH)
    except FileNotFoundError:
        if not config.ALLOW_MISSING_MODEL:
            raise

    app.config["MODEL"] = model
    app.config["TTS"] = TTSService(enabled=config.ENABLE_TTS)

    app.register_blueprint(api_bp)

    return app
