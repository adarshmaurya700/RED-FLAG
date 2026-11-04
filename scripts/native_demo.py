"""Local process supervisor. Secrets are inherited through environment, never arguments."""

import os
import argparse
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
load_dotenv(root / ".env", override=False)


def main(web_port=3000):
    # This supervisor binds both services to localhost for password-free R&D.
    os.environ.update(
        APP_ENV="development",
        HOSTED_OPERATOR_PASSWORD="",
        HOSTED_DEMO="false",
        NEXT_PUBLIC_HOSTED_DEMO="false",
    )
    for port in (8000, web_port):
        with socket.socket() as connection:
            if connection.connect_ex(("127.0.0.1", port)) == 0:
                raise SystemExit(
                    f"Port {port} is already in use. Stop the previous demo before starting another."
                )
    for arguments in (
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        [sys.executable, "seed_demo_data.py"],
    ):
        subprocess.run(arguments, cwd=root / "backend", check=True)
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node.js 24 LTS is required")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--no-access-log",
        ],
        cwd=root / "backend",
        creationflags=creationflags,
    )
    web = None
    try:
        print(
            f"red flag: http://127.0.0.1:{web_port} | API: http://127.0.0.1:8000/docs",
            flush=True,
        )
        web = subprocess.Popen(
            [
                node,
                str(root / "node_modules/next/dist/bin/next"),
                "dev",
                str(root / "frontend"),
                "--hostname",
                "127.0.0.1",
                "--port",
                str(web_port),
            ],
            cwd=root,
        )
        web.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in (web, backend):
            if process is not None and process.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or args.port == 8000:
        parser.error("Choose a web port from 1024 to 65535, excluding API port 8000")
    main(args.port)
