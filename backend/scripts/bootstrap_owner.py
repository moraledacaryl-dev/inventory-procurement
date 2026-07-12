import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User

INSECURE_PASSWORDS = {"", "password", "password123", "change-this-password-now", "changeme"}


def normalize_email(value: str) -> str:
    return value.strip().lower()


def validate_credentials(email: str, password: str) -> None:
    if not email or "@" not in email:
        raise SystemExit("BOOTSTRAP_OWNER_EMAIL must contain a valid email address.")
    if settings.app_env.lower() == "production" and (password.lower() in INSECURE_PASSWORDS or len(password) < 12):
        raise SystemExit("Production BOOTSTRAP_OWNER_PASSWORD must be at least 12 characters and must not be a default password.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the owner account if missing or deliberately reset its password.")
    parser.add_argument("--reset-password", action="store_true", help="Replace the existing owner's password with BOOTSTRAP_OWNER_PASSWORD.")
    args = parser.parse_args()

    email = normalize_email(os.getenv("BOOTSTRAP_OWNER_EMAIL", settings.bootstrap_owner_email))
    name = os.getenv("BOOTSTRAP_OWNER_NAME", settings.bootstrap_owner_name).strip() or "Owner"
    password = os.getenv("BOOTSTRAP_OWNER_PASSWORD", settings.bootstrap_owner_password)
    validate_credentials(email, password)

    with SessionLocal() as db:
        owner = db.scalar(select(User).where(func.lower(User.email) == email))
        if owner is None:
            owner = User(email=email, full_name=name, password_hash=hash_password(password), role="owner", is_active=True)
            db.add(owner)
            action = "created"
        else:
            owner.email = email
            owner.full_name = name
            owner.role = "owner"
            owner.is_active = True
            if args.reset_password:
                owner.password_hash = hash_password(password)
                action = "password reset"
            else:
                action = "verified"
        db.commit()
        print(f"Owner account {action}: {email}")


if __name__ == "__main__":
    main()
