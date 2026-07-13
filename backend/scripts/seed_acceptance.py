import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from scripts.seed_demo import main as seed_demo

OWNER_EMAIL = settings.bootstrap_owner_email or "owner@example.com"
OWNER_PASSWORD = settings.bootstrap_owner_password or "password123"


def ensure_owner() -> None:
    with SessionLocal() as db:
        owner = db.scalar(select(User).where(User.email == OWNER_EMAIL.lower()))
        if owner is None:
            db.add(User(email=OWNER_EMAIL.lower(), full_name="Acceptance Owner", password_hash=hash_password(OWNER_PASSWORD), role="owner"))
        else:
            owner.password_hash = hash_password(OWNER_PASSWORD)
            owner.role = "owner"
            owner.is_active = True
        db.commit()


def main() -> None:
    ensure_owner()
    seed_demo()
    client = TestClient(app)
    login = client.post("/api/v1/auth/login", json={"email": OWNER_EMAIL.lower(), "password": OWNER_PASSWORD})
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    items = {row["sku"]: row for row in client.get("/api/v1/items", headers=headers).json()}
    locations = {row["code"]: row for row in client.get("/api/v1/locations", headers=headers).json()}
    main_location = locations["MAIN"]
    receipt = client.post(
        "/api/v1/stock/receipts",
        headers=headers,
        json={
            "location_id": main_location["id"],
            "reference": "ACCEPTANCE-OPENING",
            "notes": "Reusable browser acceptance opening stock",
            "idempotency_key": "acceptance-opening-stock-v1",
            "lines": [
                {"item_id": items["COFFEE-BEAN"]["id"], "quantity": "20", "unit_cost": "650", "reason": "Acceptance opening stock"},
                {"item_id": items["MILK-FRESH"]["id"], "quantity": "30", "unit_cost": "95", "reason": "Acceptance opening stock"},
                {"item_id": items["SUGAR-WHITE"]["id"], "quantity": "15", "unit_cost": "75", "reason": "Acceptance opening stock"},
            ],
        },
    )
    if receipt.status_code not in {200, 201, 409}:
        raise SystemExit(f"Acceptance opening stock failed: {receipt.status_code} {receipt.text}")

    print("Acceptance dataset ready.")


if __name__ == "__main__":
    main()
