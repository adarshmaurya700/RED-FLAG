"""Local process supervisor. Secrets are inherited through environment, never arguments."""

import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
load_dotenv(root / ".env", override=False)


def main():
    for port in (8000, 3000):
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
            "red flag: http://localhost:3000 | API: http://localhost:8000/docs",
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
                "3000",
            ],
            cwd=root,
        )
        web.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in (web, backend):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    main()
