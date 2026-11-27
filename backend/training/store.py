"""Small versioned registry; transactional updates preserve attempt history."""
from contextlib import contextmanager
import json
import os
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
            db.execute("BEGIN IMMEDIATE")
            versions = [row[0] for row in db.execute("SELECT version FROM schema_version")]
            if versions == [1]:
                db.execute("ALTER TABLE attempts ADD COLUMN curriculum_version TEXT NOT NULL DEFAULT 'legacy'")
                db.execute("UPDATE schema_version SET version=2")
                versions = [2]
            if versions == [2]:
                db.execute("CREATE TABLE path_assignments (learner_id TEXT NOT NULL REFERENCES learners(id), path_id TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(learner_id,path_id))")
                db.execute("CREATE TABLE exams (id TEXT PRIMARY KEY, learner_id TEXT NOT NULL REFERENCES learners(id), path_id TEXT NOT NULL, role TEXT NOT NULL, module TEXT, curriculum_version TEXT NOT NULL, assessment_version TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', blueprint TEXT NOT NULL, answers_draft TEXT NOT NULL DEFAULT '{}', result TEXT NOT NULL DEFAULT '{}', started_at TEXT DEFAULT CURRENT_TIMESTAMP, completed_at TEXT)")
                db.execute("ALTER TABLE learners ADD COLUMN path_id TEXT NOT NULL DEFAULT 'legacy'")
                db.execute("ALTER TABLE attempts ADD COLUMN path_id TEXT NOT NULL DEFAULT 'legacy'")
                db.execute("ALTER TABLE attempts ADD COLUMN exam_id TEXT REFERENCES exams(id)")
                db.execute("UPDATE learners SET path_id='role-'||role")
                db.execute("UPDATE attempts SET path_id='role-'||role")
                db.execute("INSERT INTO path_assignments(learner_id,path_id) SELECT id,path_id FROM learners")
                db.execute("UPDATE schema_version SET version=3")
                versions = [3]
            if versions == [3]:
                db.execute("ALTER TABLE exams ADD COLUMN draft_revision INTEGER NOT NULL DEFAULT 0")
                db.execute("UPDATE schema_version SET version=4")
                versions = [4]
            if versions != [4]:
                raise RuntimeError("Unsupported training registry schema; migration required")
            db.executescript('''
              CREATE UNIQUE INDEX IF NOT EXISTS training_active_exam ON exams(learner_id,path_id,COALESCE(module,'')) WHERE status='active';
              CREATE INDEX IF NOT EXISTS training_exam_history ON exams(learner_id,started_at);
              CREATE INDEX IF NOT EXISTS training_exam_attempts ON attempts(exam_id,lesson_id);
              CREATE INDEX IF NOT EXISTS training_event_attempt_kind ON events(attempt_id,kind,id);
              CREATE INDEX IF NOT EXISTS training_history_learner ON attempts(learner_id,started_at);
            ''')
        if os.name=="posix":self.path.chmod(0o600)

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

    def business_actions(self, attempt_id):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT detail FROM events WHERE attempt_id=? AND kind IN ('business_action','record_read') ORDER BY id", (attempt_id,))]


    def assignments(self, learner_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM path_assignments WHERE learner_id=? ORDER BY created_at,path_id",(learner_id,))]

    def exam(self, learner_id, exam_id):
        with self.connect() as db:
            row=db.execute("SELECT * FROM exams WHERE id=? AND learner_id=?",(exam_id,learner_id)).fetchone()
            return dict(row) if row else None

    def exams(self, learner_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM exams WHERE learner_id=? ORDER BY started_at DESC,rowid DESC",(learner_id,))]
