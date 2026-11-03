import os
import tempfile
from pathlib import Path
import pytest

_test_directory = Path(tempfile.mkdtemp(prefix="red-flag-test-"))
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///" + str(_test_directory / "test.db").replace("\\", "/"),
)
os.environ["APP_ENV"] = "test"
os.environ["TASK_MODE"] = "local"
os.environ["INTERNAL_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
