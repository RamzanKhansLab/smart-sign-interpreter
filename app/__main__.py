from __future__ import annotations

import argparse

import uvicorn

from app.config import get_config


def main() -> None:
    config = get_config()

    parser = argparse.ArgumentParser(description='Smart Sign Interpreter (FastAPI)')
    parser.add_argument('--host', default=config.APP_HOST, help='Bind host')
    parser.add_argument('--port', type=int, default=config.APP_PORT, help='Bind port')
    parser.add_argument(
        '--log-level',
        default=str(config.LOG_LEVEL).lower(),
        help='Uvicorn log level (debug/info/warning/error/critical)',
    )
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload (dev only)')

    args = parser.parse_args()

    uvicorn.run(
        'app.main:app',
        host=args.host,
        port=args.port,
        reload=bool(args.reload),
        log_level=str(args.log_level).lower(),
    )


if __name__ == '__main__':
    main()