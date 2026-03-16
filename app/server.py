from __future__ import annotations

from . import create_app

app = create_app()

if __name__ == "__main__":
    config = app.config["CONFIG"]
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT)
