from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router as api_router
from app.api.websocket import router as websocket_router
from app.config import get_config
from app.core.logging import setup_logging
from app.services.connection_manager import ConnectionManager
from app.services.dataset_recorder import DatasetRecorder
from app.services.ml_service import MLService
from app.services.processing import SensorPipeline


def create_app() -> FastAPI:
    config = get_config()

    log_file = Path(config.BASE_DIR) / 'logs' / 'app.log'
    setup_logging(config.LOG_LEVEL, log_file)

    ws_manager = ConnectionManager()
    recorder = DatasetRecorder(config.DATASET_PATH)
    ml_service = MLService(config.MODEL_PATH, config.ALLOW_MISSING_MODEL)
    pipeline = SensorPipeline(ws_manager, ml_service)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        pipeline.set_loop(asyncio.get_running_loop())
        yield

    app = FastAPI(title='Smart Sign Language Glove Backend', lifespan=lifespan)
    app.state.config = config
    app.state.templates = Jinja2Templates(directory='templates')

    if config.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.CORS_ORIGINS,
            allow_credentials=False,
            allow_methods=['*'],
            allow_headers=['*'],
        )

    app.mount('/static', StaticFiles(directory='static'), name='static')

    app.state.ws_manager = ws_manager
    app.state.dataset_recorder = recorder
    app.state.ml_service = ml_service
    app.state.pipeline = pipeline

    app.include_router(api_router)
    app.include_router(websocket_router)

    return app


app = create_app()