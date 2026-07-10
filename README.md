# Hidden Oasis Inventory & Procurement

Pass 1 production-oriented framework for the inventory and procurement system.

## Scope of this pass

- FastAPI backend with PostgreSQL/SQLite support
- SQLAlchemy models and Alembic migration baseline
- JWT authentication and role-based authorization foundation
- Audit log foundation
- Health/readiness endpoints
- Module route shells for Items, Suppliers, Locations, Stock, Purchasing, Receiving, Counts, Reports, and Integrations
- Next.js responsive application shell with login and module pages
- Docker Compose development stack
- Backend tests and frontend lint/typecheck/build configuration
- Architecture, boundaries, data model, integrations, and migration documentation

## Quick start with Docker

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Web: http://localhost:3000
- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/api/v1/health

Default development owner:

- Email: `owner@hiddenoasis.local`
- Password: value of `BOOTSTRAP_OWNER_PASSWORD`

Change all secrets before any production deployment.

## Local backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
alembic upgrade head
uvicorn app.main:app --reload
```

## Local frontend

```bash
cd frontend
npm install
npm run dev
```

## Verification

```bash
cd backend
pytest
python -m compileall -q app tests

cd ../frontend
npm run lint
npm run typecheck
npm run build
```

## Pass status

Pass 1 is complete as a framework. Inventory transactions and procurement workflows are intentionally represented as module contracts and placeholders; their full business logic belongs to Passes 2 and 3.
