"""Dedicated training launcher: no production environment or credentials needed."""
import argparse
import asyncio
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Hidden Oasis isolated Inventory Training")
    parser.add_argument("--data", type=Path, default=Path.home() / ".local/share/inventory-training")
    parser.add_argument("--port", type=int, default=8400)
    args = parser.parse_args()
    # Windows builds asyncio's private wake-up socket pair using a loopback
    # connect. Initialize that OS primitive before installing the egress guard;
    # all application imports, requests and workers remain guarded afterward.
    with asyncio.Runner() as runner:
        runner.get_loop()
        from training.main import create_training_app
        app = create_training_app(args.data)
        import uvicorn
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, loop="asyncio"))
        runner.run(server.serve())


if __name__ == "__main__":
    main()
