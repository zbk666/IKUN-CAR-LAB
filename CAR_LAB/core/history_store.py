from __future__ import annotations
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "car_lab_history.db"


class HistoryStore:
    def __init__(self, path: Path | str = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self):
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS experiments(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at REAL NOT NULL,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    vehicle TEXT,
                    notes TEXT,
                    parameters_json TEXT,
                    metrics_json TEXT,
                    samples_json TEXT
                )
                """
            )
            con.execute("CREATE INDEX IF NOT EXISTS idx_experiments_kind_time ON experiments(kind, created_at DESC)")

    def add(self, kind: str, name: str, vehicle: str = "", notes: str = "",
            parameters: dict[str, Any] | None = None,
            metrics: dict[str, Any] | None = None,
            samples: Iterable[dict[str, Any]] | None = None) -> int:
        params = json.dumps(parameters or {}, ensure_ascii=False)
        mets = json.dumps(metrics or {}, ensure_ascii=False)
        sam = json.dumps(list(samples or []), ensure_ascii=False)
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO experiments(created_at,kind,name,vehicle,notes,parameters_json,metrics_json,samples_json) VALUES(?,?,?,?,?,?,?,?)",
                (time.time(), str(kind), str(name), str(vehicle), str(notes), params, mets, sam),
            )
            return int(cur.lastrowid)

    def list(self, kind: str | None = None, limit: int = 300):
        with self._connect() as con:
            if kind:
                rows = con.execute(
                    "SELECT id,created_at,kind,name,vehicle,notes,parameters_json,metrics_json FROM experiments WHERE kind=? ORDER BY id DESC LIMIT ?",
                    (kind, int(limit)),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT id,created_at,kind,name,vehicle,notes,parameters_json,metrics_json FROM experiments ORDER BY id DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
        return [dict(r) for r in rows]

    def get(self, exp_id: int):
        with self._connect() as con:
            row = con.execute("SELECT * FROM experiments WHERE id=?", (int(exp_id),)).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ("parameters_json", "metrics_json", "samples_json"):
            try:
                d[key[:-5]] = json.loads(d.get(key) or "{}")
            except Exception:
                d[key[:-5]] = {} if key != "samples_json" else []
        return d

    def update_notes(self, exp_id: int, notes: str):
        with self._connect() as con:
            con.execute("UPDATE experiments SET notes=? WHERE id=?", (str(notes), int(exp_id)))

    def delete(self, exp_id: int):
        with self._connect() as con:
            con.execute("DELETE FROM experiments WHERE id=?", (int(exp_id),))
