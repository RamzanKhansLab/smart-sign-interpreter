from __future__ import annotations

import time

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from app.schemas import (
    LabelRequest,
    RawSensorData,
    RenameLabelRequest,
    RetrainRequest,
    SaveBatchRequest,
)

router = APIRouter()


@router.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def home(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "home.html")


@router.get("/interpret", response_class=HTMLResponse)
def interpretation_tool(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "interpretation.html")


@router.get("/collect", response_class=HTMLResponse)
def data_collection_tool(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "data_collection.html")


@router.get("/api/health")
def health(request: Request):
    config = request.app.state.config
    pipeline = request.app.state.pipeline
    ml_service = request.app.state.ml_service
    return {
        "status": "ok",
        "timestamp_ms": int(time.time() * 1000),
        "model_loaded": ml_service.loaded,
        "has_latest": pipeline.get_latest_message() is not None,
        "dataset_path": str(config.DATASET_PATH),
        "model_path": str(config.MODEL_PATH),
        "demo_enabled": bool(getattr(config, "ENABLE_DEMO", False)),
    }


@router.post("/api/demo/publish")
def demo_publish(
    request: Request,
    payload: RawSensorData | None = Body(default=None),
):
    config = request.app.state.config
    if not getattr(config, "ENABLE_DEMO", False):
        raise HTTPException(status_code=404, detail="Demo endpoints are disabled")

    pipeline = request.app.state.pipeline

    if payload is None:
        payload = RawSensorData(
            channels={"s1": 100, "s2": 200, "s3": 300, "s4": 400, "s5": 500},
            timestamp=int(time.time() * 1000),
        )

    return pipeline.process_sensor_data(payload, source="demo")


@router.post("/api/sensor-data")
def ingest_sensor_data(request: Request, payload: RawSensorData):
    pipeline = request.app.state.pipeline
    return pipeline.process_sensor_data(payload, source="http")


@router.get("/api/latest")
def get_latest(request: Request):
    pipeline = request.app.state.pipeline
    message = pipeline.get_latest_message()
    if not message:
        raise HTTPException(status_code=404, detail="No sensor data available")
    return message


@router.get("/api/model/status")
def model_status(request: Request):
    ml_service = request.app.state.ml_service
    return {"model_loaded": ml_service.loaded}


@router.post("/api/dataset/save-latest")
def save_latest_sample(request: Request, payload: LabelRequest):
    pipeline = request.app.state.pipeline
    recorder = request.app.state.dataset_recorder
    if not pipeline.latest_data:
        raise HTTPException(status_code=400, detail="No sensor data available")
    try:
        recorder.save_sample(pipeline.latest_data, payload.label)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "saved": 1}


@router.post("/api/dataset/save-batch")
def save_batch(request: Request, payload: SaveBatchRequest):
    recorder = request.app.state.dataset_recorder
    samples = [
        (s.model_dump() if hasattr(s, "model_dump") else s.dict()) for s in payload.samples
    ]
    try:
        saved = recorder.save_samples(samples, payload.label)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "saved": saved}


@router.get("/api/dataset/stats")
def dataset_stats(request: Request):
    recorder = request.app.state.dataset_recorder
    return recorder.stats()


@router.get("/api/dataset/rows")
def dataset_rows(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    label: str | None = Query(default=None),
):
    recorder = request.app.state.dataset_recorder
    return recorder.list_rows(limit=limit, offset=offset, label=label)


@router.post("/api/dataset/rename-label")
def dataset_rename_label(request: Request, payload: RenameLabelRequest):
    recorder = request.app.state.dataset_recorder
    updated = recorder.rename_label(payload.from_label, payload.to_label)
    return {"status": "ok", "updated": updated}


@router.post("/api/dataset/delete-label")
def dataset_delete_label(request: Request, payload: LabelRequest):
    recorder = request.app.state.dataset_recorder
    deleted = recorder.delete_label(payload.label)
    return {"status": "ok", "deleted": deleted}


@router.post("/api/dataset/delete-empty-labels")
def dataset_delete_empty_labels(request: Request):
    recorder = request.app.state.dataset_recorder
    deleted = recorder.delete_empty_labels()
    return {"status": "ok", "deleted": deleted}


@router.post("/api/dataset/clear")
def dataset_clear(request: Request):
    recorder = request.app.state.dataset_recorder
    recorder.clear()
    return {"status": "ok"}


@router.post("/api/model/reset")
def reset_model(request: Request):
    ml_service = request.app.state.ml_service
    ml_service.reset(delete_file=True)
    return {"status": "ok", "model_loaded": ml_service.loaded}


@router.post("/api/model/retrain")
def retrain_model(request: Request, payload: RetrainRequest):
    config = request.app.state.config
    ml_service = request.app.state.ml_service
    try:
        metrics = ml_service.retrain(config.DATASET_PATH, model_type=payload.model_type)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "metrics": metrics}
