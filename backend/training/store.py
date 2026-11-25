"""Small versioned registry; transactional updates preserve attempt history."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / "progress.sqlite"
        if self.path.is_symlink():
            raise RuntimeError("Training registry cannot be a symlink")
        with self.connect() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
              INSERT INTO schema_version SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_version);
              CREATE TABLE IF NOT EXISTS learners (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
                current_attempt TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
              CREATE TABLE IF NOT EXISTS attempts (
                id TEXT PRIMARY KEY, learner_id TEXT NOT NULL REFERENCES learners(id),
                lesson_id TEXT NOT NULL, mode TEXT NOT NULL, role TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active', hints INTEGER NOT NULL DEFAULT 0,
                mistakes INTEGER NOT NULL DEFAULT 0, checkpoint INTEGER NOT NULL DEFAULT 0,
                started_at TEXT DEFAULT CURRENT_TIMESTAMP, completed_at TEXT,
                evidence TEXT NOT NULL DEFAULT '{}');
              CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempts(id),
                kind TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            ''')
            versions = [row[0] for row in db.execute("SELECT version FROM schema_version")]
            if versions == [1]:
                db.execute("ALTER TABLE attempts ADD COLUMN curriculum_version TEXT NOT NULL DEFAULT 'legacy'")
                db.execute("UPDATE schema_version SET version=2")
                versions = [2]
            if versions != [2]:
                raise RuntimeError("Unsupported training registry schema; migration required")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def learner(self, learner_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM learners WHERE id=?", (learner_id,)).fetchone()
            return dict(row) if row else None

    def attempt(self, learner_id):
        with self.connect() as db:
            row = db.execute("SELECT a.* FROM attempts a JOIN learners l ON l.current_attempt=a.id WHERE l.id=? AND a.learner_id=l.id", (learner_id,)).fetchone()
            return dict(row) if row else None

    def event(self, attempt_id, kind, detail):
        with self.connect() as db:
            db.execute("INSERT INTO events(attempt_id,kind,detail) VALUES (?,?,?)", (attempt_id, kind, json.dumps(detail)))

    def history(self, learner_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM attempts WHERE learner_id=? ORDER BY started_at DESC, rowid DESC", (learner_id,))]
