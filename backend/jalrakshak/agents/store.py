"""SQLite persistence for agent runs, steps and alerts, plus the human approval gate.

Safety gate: agents only ever create alerts in ``pending_approval``. Only ``approve`` by a
named reviewer moves an alert to ``sent``, and only if every guard passed (else
``GateError(409)``). Dispatch is SIMULATED: ``dispatch_log`` records what would be sent.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from jalrakshak.agents.guards import all_passed, run_guards
from jalrakshak.data.cities import get_city
from jalrakshak.models import (
    LANGS,
    AgentRun,
    AgentStep,
    Alert,
    AlertStatus,
    AlertVersion,
    DispatchLogEntry,
    Lang,
)

DEFAULT_DB = Path(__file__).resolve().parents[2] / "var" / "jalrakshak.db"

#: Share of target-ward residents reached per language (SIMULATED estimate). Regional
#: languages outside the five supported ones (Assamese, Telugu, Gujarati, Odia, Malayalam,
#: Kashmiri/Urdu) are future work; Assamese readers are served by the Bengali-script version.
_PRIMARY: dict[str, Lang] = {
    "mumbai": "mr",
    "pune": "mr",
    "chennai": "ta",
    "kolkata": "bn",
    "guwahati": "bn",
    "dibrugarh": "bn",
}
REACH = {"sms": 0.85, "whatsapp": 0.55}


class GateError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def language_shares(city_id: str) -> dict[Lang, float]:
    primary = _PRIMARY.get(city_id, "hi")
    shares: dict[Lang, float] = {lang: 0.05 for lang in LANGS}
    shares["en"] = 0.15
    shares["hi"] = 0.30
    shares[primary] = 0.50 if primary != "hi" else 0.65
    total = sum(shares.values())
    return {k: v / total for k, v in shares.items()}


class Store:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or os.environ.get("JR_DB_PATH") or DEFAULT_DB)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, city_id TEXT, started_at TEXT, data TEXT);
            CREATE TABLE IF NOT EXISTS steps (id TEXT PRIMARY KEY, run_id TEXT, seq INTEGER, ts TEXT, data TEXT);
            CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, run_id TEXT, city_id TEXT, status TEXT,
                created_at TEXT, data TEXT, allowed TEXT, notes TEXT DEFAULT '');
            CREATE INDEX IF NOT EXISTS steps_ts ON steps(ts);
            """
        )

    # ------------------------------------------------------------- runs
    def save_run(self, run: AgentRun) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO runs VALUES (?,?,?,?)",
                (run.id, run.city_id, run.started_at, run.model_dump_json()),
            )
            self._db.executemany(
                "INSERT OR REPLACE INTO steps VALUES (?,?,?,?,?)",
                [(s.id, s.run_id, s.seq, s.ts, s.model_dump_json()) for s in run.steps],
            )

    def get_run(self, run_id: str) -> AgentRun | None:
        row = self._db.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
        return AgentRun.model_validate_json(row[0]) if row else None

    def list_runs(self, city_id: str | None = None, limit: int = 50) -> list[AgentRun]:
        if city_id:
            rows = self._db.execute(
                "SELECT data FROM runs WHERE city_id=? ORDER BY started_at DESC LIMIT ?",
                (city_id, limit),
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT data FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [AgentRun.model_validate_json(r[0]) for r in rows]

    def timeline(self, limit: int = 100) -> list[AgentStep]:
        rows = self._db.execute(
            "SELECT data FROM steps ORDER BY ts DESC, seq DESC LIMIT ?", (limit,)
        ).fetchall()
        return [AgentStep.model_validate_json(r[0]) for r in rows]

    # ------------------------------------------------------------- alerts
    def save_alert(self, alert: Alert, allowed_numbers: set[str] | None = None) -> None:
        with self._lock, self._db:
            existing = self._db.execute(
                "SELECT allowed FROM alerts WHERE id=?", (alert.id,)
            ).fetchone()
            allowed = (
                json.dumps(sorted(allowed_numbers))
                if allowed_numbers is not None
                else (existing[0] if existing else "[]")
            )
            self._db.execute(
                "INSERT OR REPLACE INTO alerts (id, run_id, city_id, status, created_at, data, allowed) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    alert.id,
                    alert.run_id,
                    alert.city_id,
                    alert.status,
                    alert.created_at,
                    alert.model_dump_json(),
                    allowed,
                ),
            )

    def get_alert(self, alert_id: str) -> Alert | None:
        row = self._db.execute("SELECT data FROM alerts WHERE id=?", (alert_id,)).fetchone()
        return Alert.model_validate_json(row[0]) if row else None

    def _allowed(self, alert_id: str) -> set[str]:
        row = self._db.execute("SELECT allowed FROM alerts WHERE id=?", (alert_id,)).fetchone()
        return set(json.loads(row[0])) if row and row[0] else set()

    def list_alerts(self, status: AlertStatus | None = None) -> list[Alert]:
        if status:
            rows = self._db.execute(
                "SELECT data FROM alerts WHERE status=? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = self._db.execute("SELECT data FROM alerts ORDER BY created_at DESC").fetchall()
        return [Alert.model_validate_json(r[0]) for r in rows]

    def _pending(self, alert_id: str) -> Alert:
        alert = self.get_alert(alert_id)
        if alert is None:
            raise GateError(404, f"alert '{alert_id}' not found")
        if alert.status != "pending_approval":
            raise GateError(409, f"alert is already {alert.status}")
        return alert

    @staticmethod
    def _reviewer(reviewer: str) -> str:
        name = (reviewer or "").strip()
        if len(name) < 2:
            raise GateError(422, "a named reviewer is required")
        return name[:80]

    def edit(self, alert_id: str, versions: list[AlertVersion], reviewer: str) -> Alert:
        """Replace the text (human edit); guards are re-run and ``edited`` is set."""
        name = self._reviewer(reviewer)
        alert = self._pending(alert_id)
        by_lang = {v.lang: v for v in alert.versions}
        for v in versions:
            by_lang[v.lang] = v
        new_versions = [by_lang[lang] for lang in LANGS if lang in by_lang]
        guards = run_guards(new_versions, alert.level, self._allowed(alert_id))
        alert = alert.model_copy(
            update={"versions": new_versions, "guards": guards, "edited": True}
        )
        self.save_alert(alert)
        self._note(alert_id, f"edited by {name} at {_now()}")
        return alert

    def approve(self, alert_id: str, reviewer: str) -> Alert:
        """Human approval: only with all guards passing; dispatch is simulated and logged."""
        name = self._reviewer(reviewer)
        alert = self._pending(alert_id)
        if not all_passed(alert.guards):
            failed = [g.name for g in alert.guards if not g.passed]
            raise GateError(409, f"cannot approve: guards failed {failed}; edit the text first")
        ts = _now()
        city = get_city(alert.city_id)
        pop = sum(w.population for w in city.wards if w.id in alert.target_wards) if city else 0
        shares = language_shares(alert.city_id)
        log = [
            DispatchLogEntry(
                ts=ts,
                channel=ch,
                lang=v.lang,
                recipients_estimate=int(pop * shares[v.lang] * REACH[ch]),
            )
            for v in alert.versions
            for ch in ("sms", "whatsapp")
        ]
        alert = alert.model_copy(
            update={"status": "sent", "reviewed_by": name, "reviewed_at": ts, "dispatch_log": log}
        )
        self.save_alert(alert)
        self._note(alert_id, f"approved by {name} at {ts}; dispatch simulated")
        return alert

    def reject(self, alert_id: str, reviewer: str, reason: str = "") -> Alert:
        name = self._reviewer(reviewer)
        alert = self._pending(alert_id)
        ts = _now()
        alert = alert.model_copy(
            update={"status": "rejected", "reviewed_by": name, "reviewed_at": ts}
        )
        self.save_alert(alert)
        self._note(alert_id, f"rejected by {name} at {ts}: {reason[:300]}")
        return alert

    def _note(self, alert_id: str, note: str) -> None:
        with self._lock, self._db:
            self._db.execute(
                "UPDATE alerts SET notes = notes || ? WHERE id=?", (note + "\n", alert_id)
            )

    def close(self) -> None:
        self._db.close()
