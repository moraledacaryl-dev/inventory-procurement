#!/usr/bin/env python3
import argparse
import getpass
import sys
from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def normalize_email(value: str) -> str:
    return value.strip().lower()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or reset the Inventory owner login.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", default="Owner")
    parser.add_argument("--password", help="Avoid this in shell history; omit to be prompted securely.")
    args = parser.parse_args()

    email = normalize_email(args.email)
    password = args.password or getpass.getpass("New password: ")
    if not args.password:
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            print("Passwords do not match.", file=sys.stderr)
            return 2
    if len(password) < 12:
        print("Password must contain at least 12 characters.", file=sys.stderr)
        return 2

    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user is None:
            user = User(
                email=email,
                full_name=args.full_name.strip() or "Owner",
                password_hash=hash_password(password),
                role="owner",
                is_active=True,
            )
            db.add(user)
            action = "created"
        else:
            user.email = email
            user.full_name = args.full_name.strip() or user.full_name
            user.password_hash = hash_password(password)
            user.role = "owner"
            user.is_active = True
            action = "reset"
        db.commit()
        print(f"Owner login {action}: {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
