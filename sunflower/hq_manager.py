import aiosqlite
import json
import os
from datetime import datetime
from typing import List, Optional, Dict

class HqManager:
    def __init__(self, db_path: str = "sunflower/hq/hq.db"):
        self.db_path = db_path
        
    async def initialize(self):
        """Create the High-Command ledger tables if they don't exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL, -- queued, planning, executing, pending_review, complete, failed
                    user_id INTEGER NOT NULL,
                    persona_id TEXT DEFAULT 'general',
                    department_id TEXT DEFAULT 'general',
                    parent_id INTEGER, -- For intern/sub-tasks
                    plan_path TEXT,
                    report_path TEXT,
                    quality_score REAL,
                    feedback TEXT,
                    redo_count INTEGER DEFAULT 0,
                    wake_up_at TIMESTAMP, -- For non-blocking wait
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (parent_id) REFERENCES tasks(id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS task_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    result TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    PRIMARY KEY (user_id, key)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    goal TEXT NOT NULL,
                    frequency TEXT NOT NULL, -- daily, weekly, etc.
                    next_run_at TIMESTAMP NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def create_task(self, goal: str, user_id: int, persona_id: str = "general", parent_id: int = None, department_id: str = "general") -> int:
        """Add a new mission to the command ledger."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO tasks (goal, status, user_id, persona_id, parent_id, department_id) VALUES (?, ?, ?, ?, ?, ?)",
                (goal, "queued", user_id, persona_id, parent_id, department_id)
            )
            task_id = cursor.lastrowid
            await db.commit()
            return task_id

    async def get_queued_task(self) -> Optional[Dict]:
        """Fetch the next task that is ready for execution, excluding those waiting to wake up."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # A task is ready if status is 'queued' AND (wake_up_at is NULL OR wake_up_at <= now)
            async with db.execute(
                "SELECT * FROM tasks WHERE status = 'queued' AND (wake_up_at IS NULL OR wake_up_at <= CURRENT_TIMESTAMP) ORDER BY created_at ASC LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_task_status(self, task_id: int, status: str, plan_path: str = None, report_path: str = None, quality_score: float = None, feedback: str = None, wake_up_at: datetime = None):
        """Update the state and metadata of a task."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET status = ?, plan_path = COALESCE(?, plan_path), report_path = COALESCE(?, report_path), quality_score = COALESCE(?, quality_score), feedback = COALESCE(?, feedback), wake_up_at = COALESCE(?, wake_up_at), updated_at = ? WHERE id = ?",
                (status, plan_path, report_path, quality_score, feedback, wake_up_at, datetime.now(), task_id)
            )
            await db.commit()

    async def set_user_setting(self, user_id: int, key: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO user_settings (user_id, key, value) VALUES (?, ?, ?)", (user_id, key, value))
            await db.commit()

    async def get_user_setting(self, user_id: int, key: str, default: str = None) -> Optional[str]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM user_settings WHERE user_id = ? AND key = ?", (user_id, key)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else default

    async def add_schedule(self, user_id: int, goal: str, frequency: str, next_run_at: datetime):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO schedules (user_id, goal, frequency, next_run_at) VALUES (?, ?, ?, ?)", (user_id, goal, frequency, next_run_at))
            await db.commit()

    async def get_due_schedules(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM schedules WHERE is_active = 1 AND next_run_at <= CURRENT_TIMESTAMP") as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def update_schedule_next_run(self, schedule_id: int, next_run_at: datetime):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE schedules SET next_run_at = ? WHERE id = ?", (next_run_at, schedule_id))
            await db.commit()

    async def log_action(self, task_id: int, action: str, result: str = None):
        """Record a step in the audit trail."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO task_logs (task_id, action, result) VALUES (?, ?, ?)",
                (task_id, action, result)
            )
            await db.commit()

    async def get_active_tasks(self, user_id: Optional[int] = None) -> List[Dict]:
        """List current background missions."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM tasks WHERE status NOT IN ('complete', 'failed')"
            params = []
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_task_details(self, task_id: int) -> Optional[Dict]:
        """Fetch full info and logs for a task."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
                task = await cursor.fetchone()
                if not task: return None
                
            async with db.execute("SELECT * FROM task_logs WHERE task_id = ? ORDER BY timestamp ASC", (task_id,)) as cursor:
                logs = await cursor.fetchall()
                
            res = dict(task)
            res['logs'] = [dict(l) for l in logs]
            return res
