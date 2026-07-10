import os
os.environ["DATABASE_URL"] = "sqlite:///./test_inventory.db"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-tests"
import pytest
from fastapi.testclient import TestClient
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.main import app
from app.core.security import hash_password
from app.models.user import User

@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.add(User(email="owner@example.com", full_name="Owner", password_hash=hash_password("password123"), role="owner"))
        db.commit()
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(): return TestClient(app)
