import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User

def main():
    with SessionLocal() as db:
        email = settings.bootstrap_owner_email.lower()
        user = db.scalar(select(User).where(User.email == email))
        if user:
            print(f"Owner already exists: {email}")
            return
        db.add(User(email=email, full_name=settings.bootstrap_owner_name, password_hash=hash_password(settings.bootstrap_owner_password), role="owner"))
        db.commit()
        print(f"Created owner: {email}")
if __name__ == "__main__": main()
