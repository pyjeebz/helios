"""
SQLite storage backend for Helios.

Provides persistent storage for deployments, agents, and metrics using SQLite.
Drop-in replacement for the in-memory stores in db.py.
"""

import sqlite3
import json
import uuid
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).parent.parent / "helios.db"


class SQLiteDeploymentStore:
    """SQLite-backed storage for deployments and agents."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self._db_path = str(db_path)
        self._init_db()
        logger.info(f"SQLite deployment store initialized at {self._db_path}")

    @contextmanager
    def _conn(self):
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS deployments (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT DEFAULT '',
                    environment TEXT DEFAULT 'development',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    deployment_id TEXT NOT NULL,
                    hostname TEXT NOT NULL,
                    platform TEXT DEFAULT 'unknown',
                    agent_version TEXT DEFAULT 'unknown',
                    status TEXT DEFAULT 'online',
                    last_seen TEXT NOT NULL,
                    registered_at TEXT NOT NULL,
                    paused INTEGER DEFAULT 0,
                    collection_interval INTEGER DEFAULT 15,
                    metrics TEXT DEFAULT '[]',
                    metrics_count INTEGER DEFAULT 0,
                    location TEXT,
                    region TEXT,
                    latitude REAL,
                    longitude REAL,
                    ip_address TEXT,
                    FOREIGN KEY (deployment_id) REFERENCES deployments(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_agents_deployment
                    ON agents(deployment_id);
                CREATE INDEX IF NOT EXISTS idx_agents_status
                    ON agents(status);
            """)

            # Migrate: add paused/collection_interval if missing
            try:
                conn.execute("SELECT paused FROM agents LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE agents ADD COLUMN paused INTEGER DEFAULT 0")
                conn.execute("ALTER TABLE agents ADD COLUMN collection_interval INTEGER DEFAULT 15")
                logger.info("Migrated agents table: added paused and collection_interval columns")

            # Ensure default deployment exists
            existing = conn.execute(
                "SELECT id FROM deployments WHERE id = ?", ("default",)
            ).fetchone()
            if not existing:
                now = datetime.utcnow().isoformat()
                conn.execute(
                    """INSERT INTO deployments (id, name, description, environment, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    ("default", "default", "Default deployment", "development", now, now),
                )

    # -------------------------------------------------------------------------
    # Deployments
    # -------------------------------------------------------------------------

    def _row_to_deployment(self, row, conn):
        """Convert a database row to a Deployment model."""
        from ..db import Deployment, Environment

        dep_id = row["id"]
        agents_count = conn.execute(
            "SELECT COUNT(*) FROM agents WHERE deployment_id = ?", (dep_id,)
        ).fetchone()[0]
        agents_online = conn.execute(
            "SELECT COUNT(*) FROM agents WHERE deployment_id = ? AND status = 'online'",
            (dep_id,),
        ).fetchone()[0]
        metrics_count = conn.execute(
            "SELECT COALESCE(SUM(metrics_count), 0) FROM agents WHERE deployment_id = ?",
            (dep_id,),
        ).fetchone()[0]

        return Deployment(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            environment=Environment(row["environment"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            agents_count=agents_count,
            agents_online=agents_online,
            metrics_count=metrics_count,
        )

    def list_deployments(self):
        """List all deployments with computed fields."""
        with self._conn() as conn:
            self._update_agent_statuses(conn)
            rows = conn.execute("SELECT * FROM deployments ORDER BY created_at").fetchall()
            return [self._row_to_deployment(row, conn) for row in rows]

    def get_deployment(self, deployment_id: str):
        """Get a deployment by ID."""
        with self._conn() as conn:
            self._update_agent_statuses(conn)
            row = conn.execute(
                "SELECT * FROM deployments WHERE id = ?", (deployment_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_deployment(row, conn)

    def create_deployment(self, data):
        """Create a new deployment."""
        from ..db import Deployment

        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id FROM deployments WHERE name = ?", (data.name,)
            ).fetchone()
            if existing:
                raise ValueError(f"Deployment with name '{data.name}' already exists")

            dep_id = str(uuid.uuid4())[:8]
            now = datetime.utcnow().isoformat()
            conn.execute(
                """INSERT INTO deployments (id, name, description, environment, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (dep_id, data.name, data.description, data.environment.value, now, now),
            )

            return Deployment(
                id=dep_id,
                name=data.name,
                description=data.description,
                environment=data.environment,
                created_at=datetime.fromisoformat(now),
                updated_at=datetime.fromisoformat(now),
            )

    def update_deployment(self, deployment_id: str, data):
        """Update a deployment."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM deployments WHERE id = ?", (deployment_id,)
            ).fetchone()
            if not row:
                return None

            updates = []
            params = []

            if data.name is not None:
                dup = conn.execute(
                    "SELECT id FROM deployments WHERE name = ? AND id != ?",
                    (data.name, deployment_id),
                ).fetchone()
                if dup:
                    raise ValueError(f"Deployment with name '{data.name}' already exists")
                updates.append("name = ?")
                params.append(data.name)

            if data.description is not None:
                updates.append("description = ?")
                params.append(data.description)

            if data.environment is not None:
                updates.append("environment = ?")
                params.append(data.environment.value)

            if updates:
                updates.append("updated_at = ?")
                params.append(datetime.utcnow().isoformat())
                params.append(deployment_id)
                conn.execute(
                    f"UPDATE deployments SET {', '.join(updates)} WHERE id = ?", params
                )

            return self.get_deployment(deployment_id)

    def delete_deployment(self, deployment_id: str) -> bool:
        """Delete a deployment and its agents (CASCADE)."""
        with self._conn() as conn:
            # Delete agents first (for SQLite versions without FK cascade)
            conn.execute("DELETE FROM agents WHERE deployment_id = ?", (deployment_id,))
            cursor = conn.execute("DELETE FROM deployments WHERE id = ?", (deployment_id,))
            return cursor.rowcount > 0

    # -------------------------------------------------------------------------
    # Agents
    # -------------------------------------------------------------------------

    def _row_to_agent(self, row):
        """Convert a database row to an Agent model."""
        from ..db import Agent, AgentStatus

        return Agent(
            id=row["id"],
            deployment_id=row["deployment_id"],
            hostname=row["hostname"],
            platform=row["platform"] or "unknown",
            agent_version=row["agent_version"] or "unknown",
            status=AgentStatus(row["status"]),
            last_seen=datetime.fromisoformat(row["last_seen"]),
            registered_at=datetime.fromisoformat(row["registered_at"]),
            paused=bool(row["paused"]) if row["paused"] is not None else False,
            collection_interval=row["collection_interval"] or 15,
            metrics=json.loads(row["metrics"]) if row["metrics"] else [],
            metrics_count=row["metrics_count"] or 0,
            location=row["location"],
            region=row["region"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            ip_address=row["ip_address"],
        )

    def list_agents(self, deployment_id: Optional[str] = None):
        """List agents, optionally filtered by deployment."""
        with self._conn() as conn:
            self._update_agent_statuses(conn)
            if deployment_id:
                rows = conn.execute(
                    "SELECT * FROM agents WHERE deployment_id = ?", (deployment_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM agents").fetchall()
            return [self._row_to_agent(row) for row in rows]

    def get_agent(self, agent_id: str):
        """Get an agent by ID."""
        with self._conn() as conn:
            self._update_agent_statuses(conn)
            row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
            if not row:
                return None
            return self._row_to_agent(row)

    def register_agent(self, deployment_id: str, data):
        """Register a new agent or update existing."""
        with self._conn() as conn:
            # Verify deployment exists, create if not
            dep = conn.execute(
                "SELECT id FROM deployments WHERE id = ?", (deployment_id,)
            ).fetchone()
            if not dep:
                now = datetime.utcnow().isoformat()
                conn.execute(
                    """INSERT INTO deployments (id, name, description, environment, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (deployment_id, deployment_id, "Auto-created deployment", "development", now, now),
                )

            agent_id = data.agent_id or f"{data.hostname[:8]}-{str(uuid.uuid4())[:4]}"
            now = datetime.utcnow().isoformat()
            metrics_json = json.dumps(data.metrics)

            existing = conn.execute(
                "SELECT id FROM agents WHERE id = ?", (agent_id,)
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE agents SET
                        hostname = ?, platform = ?, agent_version = ?,
                        status = 'online', last_seen = ?,
                        metrics = ?, location = ?, region = ?, ip_address = ?
                       WHERE id = ?""",
                    (
                        data.hostname, data.platform, data.agent_version,
                        now, metrics_json,
                        data.location, data.region, data.ip_address,
                        agent_id,
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO agents
                       (id, deployment_id, hostname, platform, agent_version,
                        status, last_seen, registered_at, metrics, metrics_count,
                        location, region, ip_address)
                       VALUES (?, ?, ?, ?, ?, 'online', ?, ?, ?, 0, ?, ?, ?)""",
                    (
                        agent_id, deployment_id, data.hostname,
                        data.platform, data.agent_version,
                        now, now, metrics_json,
                        data.location, data.region, data.ip_address,
                    ),
                )

            row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
            return self._row_to_agent(row)

    def heartbeat_agent(self, agent_id: str, data):
        """Update agent heartbeat."""
        with self._conn() as conn:
            row = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
            if not row:
                return None

            now = datetime.utcnow().isoformat()
            metrics_json = json.dumps(data.metrics) if data.metrics else None

            if metrics_json:
                conn.execute(
                    """UPDATE agents SET last_seen = ?, status = 'online',
                       metrics_count = ?, metrics = ? WHERE id = ?""",
                    (now, data.metrics_count, metrics_json, agent_id),
                )
            else:
                conn.execute(
                    """UPDATE agents SET last_seen = ?, status = 'online',
                       metrics_count = ? WHERE id = ?""",
                    (now, data.metrics_count, agent_id),
                )

            return self.get_agent(agent_id)

    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            return cursor.rowcount > 0

    def get_deployment_metrics(self, deployment_id: str) -> list[str]:
        """Get unique metrics available in a deployment."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT metrics FROM agents WHERE deployment_id = ?", (deployment_id,)
            ).fetchall()
            all_metrics = set()
            for row in rows:
                metrics = json.loads(row["metrics"]) if row["metrics"] else []
                all_metrics.update(metrics)
            return sorted(all_metrics)

    def _update_agent_statuses(self, conn):
        """Update agent statuses based on last_seen time."""
        now = datetime.utcnow()
        warning_cutoff = (now - timedelta(minutes=2)).isoformat()
        offline_cutoff = (now - timedelta(minutes=5)).isoformat()

        conn.execute(
            "UPDATE agents SET status = 'offline' WHERE last_seen < ? AND status != 'paused'",
            (offline_cutoff,),
        )
        conn.execute(
            "UPDATE agents SET status = 'warning' WHERE last_seen >= ? AND last_seen < ? AND status != 'paused'",
            (offline_cutoff, warning_cutoff),
        )

    def update_agent_config(self, agent_id: str, data):
        """Update agent configuration (pause/resume, interval)."""
        with self._conn() as conn:
            row = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
            if not row:
                return None

            updates = []
            params = []

            if data.paused is not None:
                updates.append("paused = ?")
                params.append(1 if data.paused else 0)

            if data.collection_interval is not None:
                updates.append("collection_interval = ?")
                params.append(data.collection_interval)

            if updates:
                params.append(agent_id)
                conn.execute(
                    f"UPDATE agents SET {', '.join(updates)} WHERE id = ?", params
                )

        # Read back after first connection is closed/committed
        return self.get_agent(agent_id)

    def get_agent_config(self, agent_id: str):
        """Get agent control config (for the agent to poll)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT paused, collection_interval FROM agents WHERE id = ?",
                (agent_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "paused": bool(row["paused"]),
                "collection_interval": row["collection_interval"] or 15,
            }


class SQLiteMetricsStore:
    """SQLite-backed time-series metrics storage."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH, max_points: int = 100000):
        self._db_path = str(db_path)
        self._max_points = max_points
        self._init_db()
        logger.info(f"SQLite metrics store initialized at {self._db_path}")

    @contextmanager
    def _conn(self):
        """Get a database connection."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Create metrics table."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    value REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    labels TEXT DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_metrics_name
                    ON metrics(name);
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
                    ON metrics(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_metrics_name_ts
                    ON metrics(name, timestamp DESC);
            """)

    def add_metric(self, name: str, value: float, timestamp: datetime, labels: dict):
        """Add a metric point."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO metrics (name, value, timestamp, labels) VALUES (?, ?, ?, ?)",
                (name, value, timestamp.isoformat(), json.dumps(labels)),
            )
            self._trim(conn)

    def add_metrics(self, metrics: list[dict]):
        """Add multiple metrics from ingest payload."""
        with self._conn() as conn:
            for m in metrics:
                timestamp = m.get("timestamp")
                if isinstance(timestamp, str):
                    try:
                        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    except Exception:
                        timestamp = datetime.utcnow().isoformat()
                elif timestamp is None:
                    timestamp = datetime.utcnow().isoformat()
                else:
                    timestamp = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)

                conn.execute(
                    "INSERT INTO metrics (name, value, timestamp, labels) VALUES (?, ?, ?, ?)",
                    (
                        m.get("name", "unknown"),
                        float(m.get("value", 0)),
                        timestamp,
                        json.dumps(m.get("labels", {})),
                    ),
                )
            self._trim(conn)

    def get_metrics(
        self,
        name: str,
        deployment_id: Optional[str] = None,
        hours: int = 24,
        limit: int = 100,
    ) -> list[dict]:
        """Get metrics for a specific metric name."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        with self._conn() as conn:
            if deployment_id:
                rows = conn.execute(
                    """SELECT value, timestamp, labels FROM metrics
                       WHERE name = ? AND timestamp > ?
                       AND json_extract(labels, '$.deployment') = ?
                       ORDER BY timestamp ASC
                       LIMIT ?""",
                    (name, cutoff, deployment_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT value, timestamp, labels FROM metrics
                       WHERE name = ? AND timestamp > ?
                       ORDER BY timestamp ASC
                       LIMIT ?""",
                    (name, cutoff, limit),
                ).fetchall()

            return [
                {
                    "value": row["value"],
                    "timestamp": row["timestamp"],
                    "labels": json.loads(row["labels"]) if row["labels"] else {},
                }
                for row in rows
            ]

    def get_latest(self, name: str, deployment_id: Optional[str] = None):
        """Get the latest value for a metric."""
        with self._conn() as conn:
            if deployment_id:
                row = conn.execute(
                    """SELECT value, timestamp, labels FROM metrics
                       WHERE name = ? AND json_extract(labels, '$.deployment') = ?
                       ORDER BY timestamp DESC LIMIT 1""",
                    (name, deployment_id),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT value, timestamp, labels FROM metrics
                       WHERE name = ?
                       ORDER BY timestamp DESC LIMIT 1""",
                    (name,),
                ).fetchone()

            if not row:
                return None
            return {
                "value": row["value"],
                "timestamp": row["timestamp"],
                "labels": json.loads(row["labels"]) if row["labels"] else {},
            }

    def get_metric_names(self, deployment_id: Optional[str] = None) -> list[str]:
        """Get unique metric names."""
        with self._conn() as conn:
            if deployment_id:
                rows = conn.execute(
                    """SELECT DISTINCT name FROM metrics
                       WHERE json_extract(labels, '$.deployment') = ?
                       ORDER BY name""",
                    (deployment_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT DISTINCT name FROM metrics ORDER BY name"
                ).fetchall()
            return [row["name"] for row in rows]

    def _trim(self, conn):
        """Remove oldest metrics if over the limit."""
        count = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
        if count > self._max_points:
            excess = count - self._max_points
            conn.execute(
                """DELETE FROM metrics WHERE id IN (
                       SELECT id FROM metrics ORDER BY timestamp ASC LIMIT ?
                   )""",
                (excess,),
            )
