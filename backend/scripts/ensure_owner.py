import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def normalize_email(value: str) -> str:
    return value.strip().lower()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or reset the production owner account safely.")
    parser.add_argument("--email", default=os.getenv("OWNER_EMAIL"))
    parser.add_argument("--password", default=os.getenv("OWNER_PASSWORD"))
    parser.add_argument("--name", default=os.getenv("OWNER_NAME", "Hidden Oasis Owner"))
    parser.add_argument("--non-interactive", action="store_true")
    args = parser.parse_args()

    email = normalize_email(args.email or input("Owner email: "))
    password = args.password
    if not password and not args.non_interactive:
        password = getpass.getpass("New owner password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise SystemExit("Passwords do not match.")
    if not password:
        raise SystemExit("A password is required. Set OWNER_PASSWORD or omit --non-interactive.")
    if len(password) < 12:
        raise SystemExit("Owner password must be at least 12 characters.")
    if password.lower() in {"password123", "changeme1234", "admin123456"}:
        raise SystemExit("Refusing a known weak/default password.")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user is None:
            user = User(
                email=email,
                full_name=args.name.strip() or "Hidden Oasis Owner",
                password_hash=hash_password(password),
                role="owner",
                is_active=True,
            )
            db.add(user)
            action = "created"
        else:
            user.email = email
            user.full_name = args.name.strip() or user.full_name
            user.password_hash = hash_password(password)
            user.role = "owner"
            user.is_active = True
            action = "reset"
        db.commit()
        print(f"Owner account {action}: {email}")


if __name__ == "__main__":
    main()
