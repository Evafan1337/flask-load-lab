"""Run a single-process Waitress server, on loopback by default."""

import argparse
import os

from waitress import serve

from . import create_app


def main():
    parser = argparse.ArgumentParser(description="Flask Load Lab / Waitress")
    parser.add_argument("--host", default=os.environ.get("APP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("APP_PORT", "5000")))
    parser.add_argument("--threads", type=int, default=int(os.environ.get("APP_THREADS", "8")))
    args = parser.parse_args()
    if not 1 <= args.threads <= 64:
        parser.error("--threads must be between 1 and 64")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    print(f"Flask Load Lab: http://{args.host}:{args.port} | Waitress threads={args.threads}", flush=True)
    serve(create_app(), host=args.host, port=args.port, threads=args.threads)


if __name__ == "__main__":
    main()
