from __future__ import annotations


def get_app():
    from app.main import app

    return app


__all__ = ["get_app"]