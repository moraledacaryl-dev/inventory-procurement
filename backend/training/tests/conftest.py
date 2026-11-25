import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    for key in list(os.environ):
        if key in {"DATABASE_URL", "JWT_SECRET", "BOOTSTRAP_OWNER_PASSWORD", "INTERNAL_API_URL", "NEXT_PUBLIC_API_URL"} or "INTEGRATION" in key:
            os.environ.pop(key)
    os.environ["APP_ENV"] = "training"
    from training.main import create_training_app
    return create_training_app(tmp_path_factory.mktemp("training") / "inventory-training", guard_network=False)


@pytest.fixture
def learner(app):
    client = TestClient(app)
    client.headers["X-Requested-With"] = "HiddenOasisInventory"
    return client


def begin(client, lesson, role="owner", mode="guided"):
    assert client.post("/api/v1/training/enrol", json={"name": "Fictional employee", "role": role}).status_code == 200
    result = client.post("/api/v1/training/start", json={"lesson_id": lesson, "mode": mode})
    assert result.status_code == 200, result.text
    client.headers["X-Training-Attempt"] = result.json()["attempt_id"]
    return result.json()
