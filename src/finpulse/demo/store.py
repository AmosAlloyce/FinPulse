from __future__ import annotations

import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from finpulse.demo.engine import DemoError, initialize


class WorkspaceStore:
    """One bounded SQLite warehouse per visitor; no shared financial records."""

    def __init__(self, directory: Path, max_sessions: int = 40, ttl: int = 7200):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.max_sessions = max_sessions
        self.ttl = ttl
        self.guard = threading.RLock()
        self.locks: dict[str, threading.Lock] = {}
        self.slots = threading.BoundedSemaphore(8)
        self.ip_windows: dict[str, tuple[float, int]] = {}
        self.index = sqlite3.connect(directory / "sessions.sqlite", check_same_thread=False)
        self.index.execute("PRAGMA journal_mode=WAL")
        self.index.execute(
            "CREATE TABLE IF NOT EXISTS visitors(id TEXT PRIMARY KEY, expires REAL NOT NULL, "
            "window REAL NOT NULL, requests INTEGER NOT NULL DEFAULT 0, "
            "mutations INTEGER NOT NULL DEFAULT 0)"
        )
        self.index.commit()

    def _remove(self, sid: str) -> None:
        for suffix in (".sqlite", ".sqlite-wal", ".sqlite-shm"):
            (self.directory / (sid + suffix)).unlink(missing_ok=True)
        self.index.execute("DELETE FROM visitors WHERE id=?", (sid,))
        self.locks.pop(sid, None)

    def session(self, presented: str | None, ip: str, mutation: bool) -> str:
        with self.guard:
            now = time.time()
            for (sid,) in self.index.execute(
                "SELECT id FROM visitors WHERE expires<=?", (now,)
            ).fetchall():
                lock = self.locks.get(sid)
                if lock and lock.locked():
                    continue
                self._remove(sid)
            sid = presented if presented and re.fullmatch(r"[a-f0-9]{48}", presented) else None
            row = (
                self.index.execute(
                    "SELECT expires,window,requests,mutations FROM visitors WHERE id=?", (sid,)
                ).fetchone()
                if sid
                else None
            )
            if not row:
                self.ip_windows = {
                    key: value for key, value in self.ip_windows.items() if value[0] > now - 60
                }
                since, count = self.ip_windows.get(ip, (now, 0))
                if count >= 10 or (ip not in self.ip_windows and len(self.ip_windows) >= 500):
                    raise DemoError("Too many new demo sessions. Please wait a minute.", 429)
                if (
                    self.index.execute("SELECT COUNT(*) FROM visitors").fetchone()[0]
                    >= self.max_sessions
                ):
                    raise DemoError(
                        "All demo workspaces are currently in use. Please try again later.", 503
                    )
                self.ip_windows[ip] = (since, count + 1)
                sid = secrets.token_hex(24)
                db = sqlite3.connect(self.directory / f"{sid}.sqlite")
                db.row_factory = sqlite3.Row
                try:
                    initialize(db)
                    db.commit()
                except Exception:
                    db.close()
                    self._remove(sid)
                    raise
                finally:
                    db.close()
                self.index.execute(
                    "INSERT INTO visitors VALUES (?,?,?,?,?)", (sid, now + self.ttl, now, 0, 0)
                )
                row = (now + self.ttl, now, 0, 0)
            _, since, requests, mutations = row
            if since <= now - 60:
                since, requests, mutations = now, 0, 0
            if requests >= 150 or (mutation and mutations >= 40):
                raise DemoError(
                    "This workspace is receiving too many requests. Please wait a minute.", 429
                )
            self.index.execute(
                "UPDATE visitors SET expires=?,window=?,requests=?,mutations=? WHERE id=?",
                (now + self.ttl, since, requests + 1, mutations + int(mutation), sid),
            )
            self.index.commit()
            self.locks.setdefault(sid, threading.Lock())
            return sid

    @contextmanager
    def workspace(self, sid: str):
        lock = self.locks.setdefault(sid, threading.Lock())
        if not self.slots.acquire(blocking=False):
            raise DemoError("The demo is processing several requests. Please retry shortly.", 429)
        acquired = lock.acquire(timeout=2)
        if not acquired:
            self.slots.release()
            raise DemoError(
                "This workspace is busy processing another operation. Please retry.", 409
            )
        db = None
        try:
            db = sqlite3.connect(self.directory / f"{sid}.sqlite", timeout=3)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=3000")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            if db:
                db.rollback()
            raise
        finally:
            if db:
                db.close()
            lock.release()
            self.slots.release()

    def close(self) -> None:
        self.index.close()
