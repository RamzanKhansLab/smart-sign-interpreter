from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.schemas import LabelRequest, RawSensorData, RetrainRequest, SaveBatchRequest

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse("home.html", {"request": request})


@router.get("/interpret", response_class=HTMLResponse)
def interpretation_tool(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse("interpretation.html", {"request": request})


@router.get("/collect", response_class=HTMLResponse)
def data_collection_tool(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse("data_collection.html", {"request": request})


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
    recorder.save_sample(pipeline.latest_data, payload.label)
    return {"status": "ok", "saved": 1}


@router.post("/api/dataset/save-batch")
def save_batch(request: Request, payload: SaveBatchRequest):
    recorder = request.app.state.dataset_recorder
    samples = [
        (s.model_dump() if hasattr(s, "model_dump") else s.dict()) for s in payload.samples
    ]
    saved = recorder.save_samples(samples, payload.label)
    return {"status": "ok", "saved": saved}


@router.get("/api/dataset/stats")
def dataset_stats(request: Request):
    recorder = request.app.state.dataset_recorder
    return recorder.stats()


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
