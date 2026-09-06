import sqlite3
import time
from enum import Enum
from dataclasses import dataclass

class MemoryCategory(Enum):
    SYSTEM_PROFILE = "system_profile"
    PREFERENCES = "preferences"
    FACTS = "facts"
    TASK_HISTORY = "task_history"
    NOTES = "notes"

@dataclass
class MemoryEntry:
    key: str
    value: str
    category: MemoryCategory
    source: str
    created_at: float
    updated_at: float
    confidence: str

class MemoryStore:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY,
                value TEXT,
                category TEXT,
                source TEXT,
                created_at REAL,
                updated_at REAL,
                confidence TEXT
            )
        """)
        self.conn.commit()

    def write(self, entry: MemoryEntry) -> str:
        self.conn.execute("""
            INSERT INTO memory (key, value, category, source, created_at, updated_at, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                category=excluded.category,
                source=excluded.source,
                updated_at=excluded.updated_at,
                confidence=excluded.confidence
        """, (entry.key, entry.value, entry.category.value, entry.source, entry.created_at, entry.updated_at, entry.confidence))
        self.conn.commit()
        return entry.key

    def read(self, key: str) -> MemoryEntry:
        cur = self.conn.execute("SELECT * FROM memory WHERE key = ?", (key,))
        row = cur.fetchone()
        if not row:
            return None
        return MemoryEntry(row[0], row[1], MemoryCategory(row[2]), row[3], row[4], row[5], row[6])

    def search(self, category: MemoryCategory = None, query: str = None) -> list:
        sql = "SELECT * FROM memory WHERE 1=1"
        params = []
        if category:
            sql += " AND category = ?"
            params.append(category.value)
        if query:
            sql += " AND (key LIKE ? OR value LIKE ?)"
            params.append(f"%{query}%")
            params.append(f"%{query}%")
            
        cur = self.conn.execute(sql, params)
        return [MemoryEntry(r[0], r[1], MemoryCategory(r[2]), r[3], r[4], r[5], r[6]) for r in cur.fetchall()]

    def delete(self, key: str) -> bool:
        cur = self.conn.execute("DELETE FROM memory WHERE key = ?", (key,))
        self.conn.commit()
        return cur.rowcount > 0

    def list_pending(self) -> list:
        cur = self.conn.execute("SELECT * FROM memory WHERE confidence = 'pending'")
        return [MemoryEntry(r[0], r[1], MemoryCategory(r[2]), r[3], r[4], r[5], r[6]) for r in cur.fetchall()]

    def close(self):
        self.conn.close()
