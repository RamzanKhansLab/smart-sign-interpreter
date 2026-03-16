from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify, render_template, request

from .gesture_service import predict_gesture
from .validators import ValidationError, validate_sensor_payload

api_bp = Blueprint("api", __name__)


@api_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@api_bp.route("/gesture", methods=["POST"])
def gesture():
    logger = logging.getLogger("ssi")
    try:
        payload = request.get_json(silent=True)
        if payload is None:
            raise ValidationError("Invalid or missing JSON body")
        sensors = validate_sensor_payload(payload)
        logger.info("request_received", extra={"extra": {"payload": sensors}})

        model = current_app.config.get("MODEL")
        if model is None:
            return jsonify({"error": "model_not_loaded"}), 503

        gesture_text = predict_gesture(model, sensors)
        logger.info("prediction", extra={"extra": {"gesture": gesture_text}})

        tts = current_app.config.get("TTS")
        if tts:
            tts.speak(gesture_text)

        return jsonify({"gesture": gesture_text})
    except ValidationError as exc:
        logger.warning("validation_error", extra={"extra": {"errors": exc.errors}})
        return (
            jsonify({"error": "validation_error", "details": exc.errors or [str(exc)]}),
            exc.status_code,
        )
    except Exception:
        logger.exception("server_error")
        return jsonify({"error": "server_error"}), 500
